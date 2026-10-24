from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserBlock
from posts.models import Follow


class FollowBackTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.viewer = user_model.objects.create_user(
            username='followback-viewer',
            password='test-password',
        )
        self.follower = user_model.objects.create_user(
            username='followback-follower',
            password='test-password',
        )
        Follow.objects.create(follower=self.follower, following=self.viewer)
        self.client.force_login(self.viewer)

    def test_profile_shows_follow_back_when_profile_user_follows_viewer(self):
        response = self.client.get(
            '/accounts/profile/followback-follower/',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Follow Back')

    def test_follow_back_creates_reciprocal_follow(self):
        response = self.client.post(
            '/accounts/profile/followback-follower/follow/',
        )

        self.assertRedirects(
            response,
            '/accounts/profile/followback-follower/',
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Follow.objects.filter(
                follower=self.viewer,
                following=self.follower,
            ).exists()
        )

    def test_block_removes_both_follow_directions(self):
        Follow.objects.create(follower=self.viewer, following=self.follower)

        response = self.client.post(
            '/accounts/profile/followback-follower/block/',
        )

        self.assertRedirects(
            response,
            '/accounts/profile/',
            fetch_redirect_response=False,
        )
        self.assertTrue(
            UserBlock.objects.filter(
                blocker=self.viewer,
                blocked=self.follower,
            ).exists()
        )
        self.assertFalse(
            Follow.objects.filter(
                follower__in=[self.viewer, self.follower],
                following__in=[self.viewer, self.follower],
            ).exists()
        )

    def test_block_hides_profile_and_can_be_reversed(self):
        self.client.post('/accounts/profile/followback-follower/block/')

        profile_response = self.client.get(
            '/accounts/profile/followback-follower/',
        )
        self.assertRedirects(
            profile_response,
            '/',
            fetch_redirect_response=False,
        )

        unblock_response = self.client.post(
            '/accounts/profile/followback-follower/block/',
        )
        self.assertRedirects(
            unblock_response,
            '/accounts/blocked/',
            fetch_redirect_response=False,
        )
        self.assertFalse(
            UserBlock.objects.filter(
                blocker=self.viewer,
                blocked=self.follower,
            ).exists()
        )
