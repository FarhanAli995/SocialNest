from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import blocked_user_ids, users_blocked

from .models import Call, ChatRoom, Message, MessageReaction


def _add_reaction_data(messages, user):
    message_ids = [message.pk for message in messages]
    counts = {
        row['message_id']: row
        for row in MessageReaction.objects.filter(
            message_id__in=message_ids,
        ).values('message_id').annotate(
            like_count=Count('pk', filter=Q(reaction=MessageReaction.LIKE)),
            dislike_count=Count('pk', filter=Q(reaction=MessageReaction.DISLIKE)),
        )
    }
    user_reactions = dict(
        MessageReaction.objects.filter(
            message_id__in=message_ids,
            user=user,
        ).values_list('message_id', 'reaction')
    )
    for message in messages:
        message_counts = counts.get(message.pk, {})
        message.like_count = message_counts.get('like_count', 0)
        message.dislike_count = message_counts.get('dislike_count', 0)
        message.user_reaction = user_reactions.get(message.pk)


def _serialize_message_reactions(message):
    return {
        'like_count': message.like_count,
        'dislike_count': message.dislike_count,
        'user_reaction': message.user_reaction,
    }


def serialize_message(message):
    """Shared payload for WebSocket broadcasts and HTTP responses."""
    payload = {
        'id': message.pk,
        'sender_id': message.sender_id,
        'sender': message.sender.get_username(),
        'content': message.content,
        'message_type': message.message_type,
        'timestamp': message.timestamp.isoformat(),
        'is_read': message.is_read,
    }
    if message.message_type == Message.VOICE and message.audio_file:
        payload['audio_url'] = message.audio_file.url
        payload['audio_duration'] = message.audio_duration
    return payload


@login_required
def inbox(request):
    user_model = get_user_model()
    rooms = (
        ChatRoom.objects.filter(participants=request.user, is_group=False)
        .exclude(participants__id__in=blocked_user_ids(request.user))
        .annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False)
                & ~Q(messages__sender=request.user),
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                'participants',
                queryset=user_model.objects.select_related('profile'),
                to_attr='chat_participants',
            ),
            Prefetch(
                'messages',
                queryset=Message.objects.select_related('sender').order_by(
                    '-timestamp',
                    '-pk',
                )[:1],
                to_attr='latest_messages',
            ),
        )
        .order_by('-updated_at', '-pk')
        .distinct()
    )

    conversations = []
    for room in rooms:
        other = next(
            (
                participant
                for participant in room.chat_participants
                if participant.pk != request.user.pk
            ),
            None,
        )
        last = (
            room.latest_messages[0] if room.latest_messages else None
        )
        conversations.append({
            'room': room,
            'other': other,
            'last': last,
            'unread': room.unread_count,
        })

    return render(request, 'chat/inbox.html', {'conversations': conversations})


@login_required
def start_chat(request, user_id):
    user_model = get_user_model()
    other_user = get_object_or_404(user_model, pk=user_id)
    if other_user.pk == request.user.pk:
        messages.error(request, 'You cannot start a chat with yourself.')
        return redirect('chat:inbox')
    if users_blocked(request.user, other_user):
        messages.error(request, 'You cannot message this user.')
        return redirect('chat:inbox')

    room = ChatRoom.get_or_create_direct(request.user, other_user)
    return redirect('chat:room', room_id=room.pk)


@login_required
def room(request, room_id):
    chat_room = get_object_or_404(
        ChatRoom.objects.prefetch_related('participants'),
        pk=room_id,
        participants=request.user,
    )
    if any(
        users_blocked(request.user, participant)
        for participant in chat_room.participants.all()
        if participant.pk != request.user.pk
    ):
        raise Http404

    chat_room.messages.filter(
        is_read=False,
    ).exclude(
        sender=request.user,
    ).update(is_read=True)

    room_messages = list(
        chat_room.messages.select_related('sender').order_by(
            '-timestamp',
            '-pk',
        )[:30]
    )
    room_messages.reverse()
    _add_reaction_data(room_messages, request.user)

    return render(request, 'chat/room.html', {
        'room': chat_room,
        'other_user': chat_room.other_user(request.user),
        'chat_messages': room_messages,
        'ice_servers': settings.WEBRTC_ICE_SERVERS,
    })


ALLOWED_AUDIO_TYPES = {
    'audio/webm',
    'audio/ogg',
    'audio/mpeg',
    'audio/mp4',
    'audio/wav',
    'audio/x-wav',
    'audio/x-m4a',
    'audio/aac',
}
MAX_VOICE_BYTES = 10 * 1024 * 1024


CALL_RING_TIMEOUT_SECONDS = 45
CALL_START_MIN_INTERVAL_SECONDS = 15


def _expire_stale_calls():
    cutoff = timezone.now() - timedelta(seconds=CALL_RING_TIMEOUT_SECONDS)
    stale = Call.objects.filter(status=Call.RINGING, created_at__lt=cutoff)
    for call in stale:
        call.status = Call.MISSED
        call.ended_at = timezone.now()
        call.save(update_fields=['status', 'ended_at'])
        _broadcast_call(call.room_id, {
            'event': 'call_missed',
            'call': _serialize_call(call),
        })


def _call_room_for_user(request, room_id):
    chat_room = get_object_or_404(
        ChatRoom.objects.prefetch_related('participants'),
        pk=room_id,
        participants=request.user,
        is_group=False,
    )
    other = chat_room.other_user(request.user)
    if other is None or users_blocked(request.user, other):
        raise Http404
    return chat_room, other


def _broadcast_call(room_id, payload):
    async_to_sync(get_channel_layer().group_send)(
        f'chat_{room_id}',
        {'type': 'chat.call', 'call': payload},
    )


def _serialize_call(call):
    return {
        'id': call.pk,
        'room_id': call.room_id,
        'caller_id': call.caller_id,
        'caller': call.caller.get_username(),
        'receiver_id': call.receiver_id,
        'receiver': call.receiver.get_username(),
        'status': call.status,
        'call_type': call.call_type,
        'created_at': call.created_at.isoformat(),
    }


@login_required
@require_POST
def start_call(request, room_id):
    chat_room, other = _call_room_for_user(request, room_id)
    _expire_stale_calls()

    recent_cutoff = timezone.now() - timedelta(seconds=CALL_START_MIN_INTERVAL_SECONDS)
    if Call.objects.filter(caller=request.user, created_at__gte=recent_cutoff).exists():
        return JsonResponse({'error': 'Please wait before starting another call.'}, status=429)

    active = Call.objects.filter(
        room=chat_room,
        status=Call.RINGING,
    ).first()
    if active is not None:
        active.status = Call.MISSED
        active.ended_at = timezone.now()
        active.save(update_fields=['status', 'ended_at'])

    call = Call.objects.create(
        room=chat_room,
        caller=request.user,
        receiver=other,
        status=Call.RINGING,
        call_type='video',
    )
    _broadcast_call(chat_room.pk, {
        'event': 'incoming_call',
        'call': _serialize_call(call),
    })
    return JsonResponse({'call': _serialize_call(call)}, status=201)


@login_required
@require_POST
def update_call(request, call_id, action):
    call = get_object_or_404(
        Call.objects.select_related('caller', 'receiver'),
        pk=call_id,
    )
    if request.user.pk not in (call.caller_id, call.receiver_id):
        raise Http404

    if action == 'accept' and request.user.pk == call.receiver_id and call.status == Call.RINGING:
        call.status = Call.ACCEPTED
        call.started_at = timezone.now()
    elif action == 'reject' and request.user.pk == call.receiver_id and call.status == Call.RINGING:
        call.status = Call.REJECTED
        call.ended_at = timezone.now()
    elif action == 'end' and call.status in (Call.RINGING, Call.ACCEPTED):
        now = timezone.now()
        call.status = Call.ENDED
        call.ended_at = now
        if call.started_at:
            call.duration = int((now - call.started_at).total_seconds())
    else:
        return JsonResponse({
            'call': _serialize_call(call),
            'noop': True,
        })

    call.save()
    _expire_stale_calls()
    event_name = {
        'accept': 'call_accepted',
        'reject': 'call_rejected',
        'end': 'call_ended',
    }[action]
    _broadcast_call(call.room_id, {
        'event': event_name,
        'call': _serialize_call(call),
    })
    return JsonResponse({'call': _serialize_call(call)})


@login_required
@require_POST
def voice_upload(request, room_id):
    chat_room = get_object_or_404(
        ChatRoom.objects.prefetch_related('participants'),
        pk=room_id,
        participants=request.user,
        is_group=False,
    )
    if any(
        users_blocked(request.user, participant)
        for participant in chat_room.participants.all()
        if participant.pk != request.user.pk
    ):
        raise Http404

    audio = request.FILES.get('audio')
    if audio is None:
        return HttpResponseBadRequest('No audio file provided.')
    if audio.size == 0:
        return HttpResponseBadRequest('Audio file is empty.')
    if audio.size > MAX_VOICE_BYTES:
        return HttpResponseBadRequest('Audio file is too large (max 10 MB).')
    content_type = (audio.content_type or '').split(';')[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        return HttpResponseBadRequest('Unsupported audio format.')

    try:
        duration = int(float(request.POST.get('duration', '0')))
    except (TypeError, ValueError):
        duration = 0
    duration = max(0, min(duration, 600))

    with transaction.atomic():
        message = Message.objects.create(
            room=chat_room,
            sender=request.user,
            content='',
            message_type=Message.VOICE,
            audio_file=audio,
            audio_duration=duration,
        )
        ChatRoom.objects.filter(pk=chat_room.pk).update(updated_at=timezone.now())

    payload = serialize_message(message)
    async_to_sync(get_channel_layer().group_send)(
        f'chat_{chat_room.pk}',
        {
            'type': 'chat.message',
            'message': payload,
        },
    )
    return JsonResponse({'message': payload}, status=201)


@login_required
@require_GET
def call_history(request):
    calls = (
        Call.objects.filter(Q(caller=request.user) | Q(receiver=request.user))
        .select_related('caller', 'receiver', 'room')
        .order_by('-created_at')[:50]
    )
    return render(request, 'chat/call_history.html', {
        'calls': calls,
        'me': request.user,
    })


@login_required
@require_GET
def history(request, room_id):
    chat_room = get_object_or_404(
        ChatRoom,
        pk=room_id,
        participants=request.user,
    )
    other_participants = chat_room.participants.exclude(pk=request.user.pk)
    if any(users_blocked(request.user, participant) for participant in other_participants):
        raise Http404

    before = request.GET.get('before')
    if before is None:
        return HttpResponseBadRequest("'before' query parameter is required.")
    try:
        before_id = int(before)
    except ValueError:
        return HttpResponseBadRequest("'before' must be a positive message ID.")
    if before_id <= 0:
        return HttpResponseBadRequest("'before' must be a positive message ID.")

    older_messages = list(
        chat_room.messages.filter(pk__lt=before_id)
        .select_related('sender')
        .order_by('-timestamp', '-pk')[:31]
    )
    has_more = len(older_messages) > 30
    older_messages = older_messages[:30]
    older_messages.reverse()
    _add_reaction_data(older_messages, request.user)

    return JsonResponse({
        'messages': [
            {
                **serialize_message(message),
                **_serialize_message_reactions(message),
            }
            for message in older_messages
        ],
        'has_more': has_more,
    })


@login_required
@require_POST
def react(request, room_id, message_id):
    chat_room = get_object_or_404(
        ChatRoom,
        pk=room_id,
        participants=request.user,
    )
    other_participants = chat_room.participants.exclude(pk=request.user.pk)
    if any(users_blocked(request.user, participant) for participant in other_participants):
        raise Http404

    message = get_object_or_404(Message, pk=message_id, room=chat_room)
    requested_reaction = request.POST.get('reaction')
    if requested_reaction not in (MessageReaction.LIKE, MessageReaction.DISLIKE):
        return HttpResponseBadRequest("'reaction' must be 'like' or 'dislike'.")

    with transaction.atomic():
        Message.objects.select_for_update().get(pk=message.pk)
        current_reaction = MessageReaction.objects.filter(
            message=message,
            user=request.user,
        ).first()
        if current_reaction and current_reaction.reaction == requested_reaction:
            current_reaction.delete()
            user_reaction = None
        elif current_reaction:
            current_reaction.reaction = requested_reaction
            current_reaction.save(update_fields=['reaction'])
            user_reaction = requested_reaction
        else:
            MessageReaction.objects.create(
                message=message,
                user=request.user,
                reaction=requested_reaction,
            )
            user_reaction = requested_reaction

        like_count = MessageReaction.objects.filter(
            message=message,
            reaction=MessageReaction.LIKE,
        ).count()
        dislike_count = MessageReaction.objects.filter(
            message=message,
            reaction=MessageReaction.DISLIKE,
        ).count()

    reaction_data = {
        'message_id': message.pk,
        'user_id': request.user.pk,
        'user_reaction': user_reaction,
        'like_count': like_count,
        'dislike_count': dislike_count,
    }
    async_to_sync(get_channel_layer().group_send)(
        f'chat_{chat_room.pk}',
        {
            'type': 'chat.reaction',
            'reaction': reaction_data,
        },
    )
    return JsonResponse(reaction_data)
