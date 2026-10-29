from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import blocked_user_ids, users_blocked

from .models import ChatRoom, Message, MessageReaction


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
                'id': message.pk,
                'sender_id': message.sender_id,
                'sender': message.sender.get_username(),
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_read': message.is_read,
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
