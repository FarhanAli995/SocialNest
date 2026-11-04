import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserBlock

from .models import Call


class CallConsumer(AsyncWebsocketConsumer):
    """Relays WebRTC signaling (SDP offer/answer + ICE) between the two
    participants of a Call. Only the caller and receiver may connect, and
    signaling is forwarded only to the other participant."""

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close(code=4403)
            return

        self.call_id = self.scope['url_route']['kwargs']['call_id']
        call = await self._get_call(self.call_id)
        if call is None or user.pk not in (call['caller_id'], call['receiver_id']):
            await self.close(code=4403)
            return
        if await self._participants_blocked(call['caller_id'], call['receiver_id']):
            await self.close(code=4403)
            return

        self.user = user
        self.other_user_id = (
            call['receiver_id'] if user.pk == call['caller_id'] else call['caller_id']
        )
        self.group_name = f'call_{self.call_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return

        event_type = data.get('type')
        # Only relay signaling event types; never echo back to sender.
        if event_type not in (
            'webrtc_offer', 'webrtc_answer', 'ice_candidate',
            'call_ended', 'receiver_ready',
        ):
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'call.signal',
                'sender_id': self.user.pk,
                'event_type': event_type,
                'payload': data.get('payload'),
            },
        )

    async def call_signal(self, event):
        # Only deliver to the other participant.
        if event['sender_id'] == self.user.pk:
            return
        await self.send(text_data=json.dumps({
            'type': event['event_type'],
            'sender_id': event['sender_id'],
            'payload': event['payload'],
        }))

    @database_sync_to_async
    def _get_call(self, call_id):
        call = Call.objects.filter(pk=call_id).values(
            'caller_id', 'receiver_id', 'status',
        ).first()
        return call

    @database_sync_to_async
    def _participants_blocked(self, caller_id, receiver_id):
        return UserBlock.objects.filter(
            Q(blocker_id=caller_id, blocked_id=receiver_id)
            | Q(blocker_id=receiver_id, blocked_id=caller_id)
        ).exists()
