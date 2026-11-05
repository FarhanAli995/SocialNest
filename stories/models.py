from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


STORY_LIFETIME = timedelta(hours=24)


class Story(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stories',
    )
    image = models.ImageField(upload_to='stories/images/', blank=True)
    video = models.FileField(upload_to='stories/videos/', blank=True)
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + STORY_LIFETIME
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @classmethod
    def active(cls):
        return cls.objects.filter(expires_at__gt=timezone.now())

    def __str__(self):
        return f'Story {self.pk} by {self.author_id}'


class StoryView(models.Model):
    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE,
        related_name='views',
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='story_views',
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['story', 'viewer'],
                name='unique_story_view',
            ),
        ]

    def __str__(self):
        return f'{self.viewer_id} viewed story {self.story_id}'
