from django.urls import path

from .call_consumers import CallConsumer
from .consumers import ChatConsumer


websocket_urlpatterns = [
    path('ws/chat/<int:room_id>/', ChatConsumer.as_asgi()),
    path('ws/calls/<int:call_id>/', CallConsumer.as_asgi()),
]
