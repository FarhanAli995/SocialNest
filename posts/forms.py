from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Comment, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('text', 'image', 'video')
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': "What's on your mind?"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get('text')
        text = text.strip() if text else ''
        image = cleaned_data.get('image')
        video = cleaned_data.get('video')

        if not text and not image and not video:
            raise forms.ValidationError('A post must contain text, an image, or a video.')
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if isinstance(image, UploadedFile) and image.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Image file size cannot exceed 10 MB.')
        return image

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if isinstance(video, UploadedFile) and video.size > 50 * 1024 * 1024:
            raise forms.ValidationError('Video file size cannot exceed 50 MB.')
        return video


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Write a comment...'}),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text', '').strip()
        if not text:
            raise forms.ValidationError('Comment cannot be empty.')
        return text
