from .models import Message


def chat_unread(request):
    if not request.user.is_authenticated:
        return {'chat_unread': 0}

    unread_count = Message.objects.filter(
        room__participants=request.user,
        is_read=False,
    ).exclude(
        sender=request.user,
    ).count()
    return {'chat_unread': unread_count}
