"""
URL configuration for socialNest project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.views.generic import TemplateView

urlpatterns = [
    path(
        'favicon.ico',
        RedirectView.as_view(
            url=f'/{settings.STATIC_URL.lstrip("/")}'
            'icons/image_82559b-generate-this-same-image-in-hd.ico',
            permanent=False,
        ),
    ),
    path('admin/', admin.site.urls),
    path('landing/', TemplateView.as_view(template_name='landing.html'), name='landing'),
    path('', include('posts.urls')),
    path('accounts/', include('accounts.urls')),
    path('chat/', include('chat.urls')),
    path('stories/', include('stories.urls')),
    path('notifications/', include('notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
