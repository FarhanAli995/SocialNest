from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.models import blocked_user_ids, users_blocked

from .models import ChatRoom, Message


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
                queryset=user_model.objects.all(),
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

    return JsonResponse({
        'messages': [
            {
                'id': message.pk,
                'sender_id': message.sender_id,
                'sender': message.sender.get_username(),
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_read': message.is_read,
            }
            for message in older_messages
        ],
        'has_more': has_more,
    })
