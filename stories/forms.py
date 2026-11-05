from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Story


class StoryForm(forms.ModelForm):
    class Meta:
        model = Story
        fields = ('image', 'video', 'caption')
        widgets = {
            'caption': forms.TextInput(attrs={
                'placeholder': 'Add a caption (optional)',
                'maxlength': '200',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get('image')
        video = cleaned_data.get('video')
        if not image and not video:
            raise forms.ValidationError('A story must contain an image or a video.')
        if image and video:
            raise forms.ValidationError('Upload either an image or a video, not both.')
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
