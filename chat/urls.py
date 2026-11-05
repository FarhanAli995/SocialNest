from django.urls import path

from . import views


app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('calls/history/', views.call_history, name='call_history'),
    path('start_chat/<int:user_id>/', views.start_chat, name='start'),
    path('room/<int:room_id>/', views.room, name='room'),
    path('room/<int:room_id>/history/', views.history, name='history'),
    path('room/<int:room_id>/voice/', views.voice_upload, name='voice_upload'),
    path('room/<int:room_id>/call/start/', views.start_call, name='start_call'),
    path('calls/<int:call_id>/<str:action>/', views.update_call, name='update_call'),
    path(
        'room/<int:room_id>/message/<int:message_id>/react/',
        views.react,
        name='react',
    ),
]
