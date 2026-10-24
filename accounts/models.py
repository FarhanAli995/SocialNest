from django.conf import settings
from django.db import models


class Profile(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('moderator', 'Moderator'), ('admin', 'Admin')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png')
    cover_image = models.ImageField(upload_to='covers/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} profile'


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blocked_users',
        on_delete=models.CASCADE,
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blocked_by_users',
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['blocker', 'blocked'],
                name='unique_user_block',
            ),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F('blocked')),
                name='no_self_user_block',
            ),
        ]

    def __str__(self):
        return f'{self.blocker} blocks {self.blocked}'


def users_blocked(user_a, user_b):
    return UserBlock.objects.filter(
        models.Q(blocker=user_a, blocked=user_b)
        | models.Q(blocker=user_b, blocked=user_a)
    ).exists()


def blocked_user_ids(user):
    blocked_ids = UserBlock.objects.filter(
        blocker=user,
    ).values_list('blocked_id', flat=True)
    blocker_ids = UserBlock.objects.filter(
        blocked=user,
    ).values_list('blocker_id', flat=True)
    return set(blocked_ids) | set(blocker_ids)
