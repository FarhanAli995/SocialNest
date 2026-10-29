from django.urls import path

from . import views


app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start_chat/<int:user_id>/', views.start_chat, name='start'),
    path('room/<int:room_id>/', views.room, name='room'),
    path('room/<int:room_id>/history/', views.history, name='history'),
    path(
        'room/<int:room_id>/message/<int:message_id>/react/',
        views.react,
        name='react',
    ),
]
