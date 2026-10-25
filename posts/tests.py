from django.test import TestCase
from django.urls import reverse


class LoginRequiredPageTests(TestCase):
    def test_app_pages_redirect_anonymous_visitors_to_login(self):
        protected_urls = [
            reverse('posts:feed'),
            reverse('posts:explore'),
            reverse('posts:post_detail', args=[1]),
            reverse('chat:inbox'),
            reverse('chat:room', args=[1]),
            reverse('notifications:list'),
            reverse('accounts:own_profile'),
            reverse('accounts:edit_profile'),
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.url,
                    f'{reverse("accounts:login")}?next={url}',
                )

    def test_login_and_registration_remain_public(self):
        for url in (
            reverse('accounts:login'),
            reverse('accounts:register'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
