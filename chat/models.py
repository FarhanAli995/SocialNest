from django.conf import settings
from django.db import models

from accounts.models import users_blocked


class ChatRoom(models.Model):
    name = models.CharField(max_length=255, blank=True)
    is_group = models.BooleanField(default=False)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chat_rooms',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_or_create_direct(cls, user_a, user_b):
        if users_blocked(user_a, user_b):
            raise ValueError('Cannot create a chat room between blocked users.')

        room = (
            cls.objects.filter(is_group=False, participants=user_a)
            .filter(participants=user_b)
            .first()
        )
        if room is not None:
            return room

        room = cls.objects.create(is_group=False)
        room.participants.add(user_a, user_b)
        return room

    def other_user(self, user):
        return self.participants.exclude(pk=user.pk).first()

    def __str__(self):
        return self.name or f'Chat room {self.pk}'


class Message(models.Model):
    TEXT = 'text'
    VOICE = 'voice'
    MESSAGE_TYPE_CHOICES = [
        (TEXT, 'Text'),
        (VOICE, 'Voice'),
    ]

    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default=TEXT,
    )
    audio_file = models.FileField(
        upload_to='chat/voice/',
        blank=True,
    )
    audio_duration = models.PositiveIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['room', 'timestamp'], name='chat_msg_room_ts_idx'),
        ]
        ordering = ['timestamp']

    def __str__(self):
        return f'Message in room {self.room_id} from {self.sender_id}'


class MessageReaction(models.Model):
    LIKE = 'like'
    DISLIKE = 'dislike'
    REACTION_CHOICES = [
        (LIKE, 'Like'),
        (DISLIKE, 'Dislike'),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reactions',
    )
    reaction = models.CharField(max_length=7, choices=REACTION_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'user'],
                name='chat_unique_message_reaction',
            ),
        ]

    def __str__(self):
        return f'{self.reaction} on message {self.message_id} by {self.user_id}'


class Call(models.Model):
    RINGING = 'ringing'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    ENDED = 'ended'
    MISSED = 'missed'
    STATUS_CHOICES = [
        (RINGING, 'Ringing'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
        (ENDED, 'Ended'),
        (MISSED, 'Missed'),
    ]

    call_type = models.CharField(max_length=10, default='video')
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='calls',
    )
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calls_made',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calls_received',
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=RINGING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Call {self.pk} ({self.status})'
