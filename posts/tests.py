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


class PostFormAndLikeTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from posts.models import Post
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='testauthor',
            password='testpassword123',
        )
        self.post = Post.objects.create(author=self.user, text='Hello SocialNest')
        self.client.force_login(self.user)

    def test_post_form_rejects_empty_content(self):
        from posts.forms import PostForm
        form = PostForm(data={'text': '   '})
        self.assertFalse(form.is_valid())
        self.assertIn('A post must contain text, an image, or a video.', form.errors['__all__'])

    def test_post_form_accepts_valid_text(self):
        from posts.forms import PostForm
        form = PostForm(data={'text': 'Valid content'})
        self.assertTrue(form.is_valid())

    def test_like_toggle_via_ajax_returns_json(self):
        url = reverse('posts:like_toggle', args=[self.post.pk])
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['likes_count'], 1)

        # Unlike via AJAX
        response2 = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertFalse(data2['liked'])
        self.assertEqual(data2['likes_count'], 0)

    def test_like_toggle_redirects_to_referer_when_present(self):
        url = reverse('posts:like_toggle', args=[self.post.pk])
        feed_url = reverse('posts:feed')
        response = self.client.post(url, HTTP_REFERER=feed_url)
        self.assertRedirects(response, feed_url, fetch_redirect_response=False)
