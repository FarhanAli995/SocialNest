import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserBlock

from .models import ChatRoom, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close(code=4403)
            return

        self.room_id = self.scope['url_route']['kwargs']['room_id']
        if not await self._is_room_participant(user.pk, self.room_id):
            await self.close(code=4403)
            return

        self.user = user
        self.group_name = f'chat_{self.room_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        if not await self._is_room_participant(self.user.pk, self.room_id):
            await self.close(code=4403)
            return

        if text_data is None:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON.')
            return

        if not isinstance(data, dict):
            await self._send_error('Expected a JSON object.')
            return

        message_type = data.get('type')
        if message_type == 'message':
            await self._receive_message(data)
        elif message_type == 'typing':
            await self._receive_typing(data)
        elif message_type == 'read':
            await self._receive_read()

    async def _receive_message(self, data):
        content = data.get('message', data.get('content'))
        if not isinstance(content, str):
            await self._send_error('Message content must be text.')
            return

        content = content.strip()
        if not content:
            return
        if len(content) > 2000:
            await self._send_error('Message cannot exceed 2000 characters.')
            return

        message_data = await self._create_message(content)
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.message',
                'message': message_data,
            },
        )

    async def _receive_typing(self, data):
        is_typing = data.get('is_typing', True)
        if not isinstance(is_typing, bool):
            await self._send_error('is_typing must be a boolean.')
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.typing',
                'user_id': self.user.pk,
                'is_typing': is_typing,
            },
        )

    async def _receive_read(self):
        await self._mark_other_messages_read()
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.read',
                'user_id': self.user.pk,
                'room_id': self.room_id,
                'read_at': timezone.now().isoformat(),
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def chat_typing(self, event):
        if event['user_id'] == self.user.pk:
            return

        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'is_typing': event['is_typing'],
        }))

    async def chat_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'user_id': event['user_id'],
            'room_id': event['room_id'],
            'read_at': event['read_at'],
        }))

    async def _send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
        }))

    @database_sync_to_async
    def _is_room_participant(self, user_id, room_id):
        room = ChatRoom.objects.filter(
            pk=room_id,
            is_group=False,
            participants__pk=user_id,
        ).first()
        if room is None:
            return False

        other_user_ids = list(
            room.participants.exclude(pk=user_id).values_list('pk', flat=True)
        )
        return not UserBlock.objects.filter(
            Q(blocker_id=user_id, blocked_id__in=other_user_ids)
            | Q(blocked_id=user_id, blocker_id__in=other_user_ids)
        ).exists()

    @database_sync_to_async
    def _create_message(self, content):
        with transaction.atomic():
            message = Message.objects.create(
                room_id=self.room_id,
                sender_id=self.user.pk,
                content=content,
            )
            ChatRoom.objects.filter(pk=self.room_id).update(
                updated_at=timezone.now(),
            )

        return {
            'id': message.pk,
            'sender_id': message.sender_id,
            'sender': self.user.get_username(),
            'content': message.content,
            'timestamp': message.timestamp.isoformat(),
        }

    @database_sync_to_async
    def _mark_other_messages_read(self):
        return Message.objects.filter(
            room_id=self.room_id,
            is_read=False,
        ).exclude(
            sender_id=self.user.pk,
        ).update(is_read=True)
