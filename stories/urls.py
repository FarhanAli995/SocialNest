from django.urls import path

from . import views

app_name = 'stories'

urlpatterns = [
    path('bar/', views.story_bar, name='bar'),
    path('create/', views.story_create, name='create'),
    path('view/<int:user_id>/', views.story_viewer, name='viewer'),
    path('<int:story_id>/viewed/', views.mark_viewed, name='mark_viewed'),
    path('<int:story_id>/delete/', views.story_delete, name='delete'),
    path('<int:story_id>/viewers/', views.story_viewers, name='viewers'),
]
