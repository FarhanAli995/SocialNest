from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from accounts.models import UserBlock
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import ChatRoom, Message, MessageReaction
from .routing import websocket_urlpatterns


class UserScopeMiddleware:
    def __init__(self, application, user):
        self.application = application
        self.user = user

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope['user'] = self.user
        await self.application(scope, receive, send)


class ChatConsumerTests(TransactionTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.member = user_model.objects.create_user(
            username='chat-member',
            password='test-password',
        )
        self.other_member = user_model.objects.create_user(
            username='chat-other-member',
            password='test-password',
        )
        self.non_member = user_model.objects.create_user(
            username='chat-non-member',
            password='test-password',
        )
        self.room = ChatRoom.objects.create(is_group=False)
        self.room.participants.add(self.member, self.other_member)

    def communicator_for(self, user):
        application = UserScopeMiddleware(
            URLRouter(websocket_urlpatterns),
            user,
        )
        return WebsocketCommunicator(
            application,
            f'/ws/chat/{self.room.pk}/',
        )

    async def test_member_can_send_and_other_member_receives_message(self):
        sender = self.communicator_for(self.member)
        receiver = self.communicator_for(self.other_member)

        sender_connected, _ = await sender.connect()
        receiver_connected, _ = await receiver.connect()
        self.assertTrue(sender_connected)
        self.assertTrue(receiver_connected)

        try:
            await sender.send_json_to({
                'type': 'message',
                'message': 'Hello from the chat test',
            })

            received = await receiver.receive_json_from(timeout=2)
            self.assertEqual(received['type'], 'message')
            self.assertEqual(received['message']['content'], 'Hello from the chat test')
            self.assertEqual(received['message']['sender_id'], self.member.pk)

            saved_message = await database_sync_to_async(
                Message.objects.get
            )(room=self.room, sender=self.member)
            self.assertEqual(saved_message.content, 'Hello from the chat test')
        finally:
            await sender.disconnect()
            await receiver.disconnect()

    async def test_non_member_connection_is_rejected(self):
        communicator = self.communicator_for(self.non_member)

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, 4403)

    async def test_blocked_participant_connection_is_rejected(self):
        await database_sync_to_async(UserBlock.objects.create)(
            blocker=self.member,
            blocked=self.other_member,
        )
        communicator = self.communicator_for(self.member)

        connected, close_code = await communicator.connect()

        self.assertFalse(connected)
        self.assertEqual(close_code, 4403)

    async def test_whitespace_only_message_is_ignored(self):
        sender = self.communicator_for(self.member)
        receiver = self.communicator_for(self.other_member)

        sender_connected, _ = await sender.connect()
        receiver_connected, _ = await receiver.connect()
        self.assertTrue(sender_connected)
        self.assertTrue(receiver_connected)

        try:
            await sender.send_json_to({
                'type': 'message',
                'message': ' \t\n ',
            })

            self.assertTrue(await sender.receive_nothing(timeout=0.1))
            self.assertTrue(await receiver.receive_nothing(timeout=0.1))
            message_count = await database_sync_to_async(
                Message.objects.filter(room=self.room).count
            )()
            self.assertEqual(message_count, 0)
        finally:
            await sender.disconnect()
            await receiver.disconnect()


class DirectRoomTests(TestCase):
    def test_get_or_create_direct_reuses_room_regardless_of_argument_order(self):
        user_model = get_user_model()
        first_user = user_model.objects.create_user(
            username='direct-first',
            password='test-password',
        )
        second_user = user_model.objects.create_user(
            username='direct-second',
            password='test-password',
        )

        room = ChatRoom.get_or_create_direct(first_user, second_user)
        reversed_room = ChatRoom.get_or_create_direct(second_user, first_user)

        self.assertEqual(reversed_room.pk, room.pk)
        self.assertEqual(
            ChatRoom.objects.filter(is_group=False).count(),
            1,
        )


class MessageReactionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.member = user_model.objects.create_user(
            username='reaction-member',
            password='test-password',
        )
        self.other_member = user_model.objects.create_user(
            username='reaction-other-member',
            password='test-password',
        )
        self.non_member = user_model.objects.create_user(
            username='reaction-non-member',
            password='test-password',
        )
        self.room = ChatRoom.objects.create(is_group=False)
        self.room.participants.add(self.member, self.other_member)
        self.message = Message.objects.create(
            room=self.room,
            sender=self.other_member,
            content='React to this message',
        )
        self.client.force_login(self.member)
        self.url = reverse(
            'chat:react',
            args=[self.room.pk, self.message.pk],
        )

    def post_reaction(self, reaction):
        return self.client.post(self.url, {'reaction': reaction})

    def test_like_can_be_undone(self):
        like_response = self.post_reaction(MessageReaction.LIKE)
        undo_response = self.post_reaction(MessageReaction.LIKE)

        self.assertEqual(like_response.status_code, 200)
        self.assertEqual(like_response.json()['user_reaction'], 'like')
        self.assertEqual(like_response.json()['like_count'], 1)
        self.assertEqual(undo_response.status_code, 200)
        self.assertIsNone(undo_response.json()['user_reaction'])
        self.assertEqual(undo_response.json()['like_count'], 0)
        self.assertFalse(MessageReaction.objects.filter(message=self.message).exists())

    def test_reaction_can_switch_between_like_and_dislike(self):
        self.post_reaction(MessageReaction.LIKE)
        response = self.post_reaction(MessageReaction.DISLIKE)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user_reaction'], 'dislike')
        self.assertEqual(response.json()['like_count'], 0)
        self.assertEqual(response.json()['dislike_count'], 1)
        self.assertEqual(
            MessageReaction.objects.filter(message=self.message).count(),
            1,
        )

    def test_non_member_cannot_react(self):
        self.client.force_login(self.non_member)

        response = self.post_reaction(MessageReaction.LIKE)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(MessageReaction.objects.filter(message=self.message).exists())

    def test_invalid_reaction_is_rejected(self):
        response = self.post_reaction('love')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MessageReaction.objects.filter(message=self.message).exists())

    def test_room_and_history_include_reaction_state(self):
        MessageReaction.objects.create(
            message=self.message,
            user=self.member,
            reaction=MessageReaction.LIKE,
        )

        room_response = self.client.get(
            reverse('chat:room', args=[self.room.pk]),
        )
        history_response = self.client.get(
            reverse('chat:history', args=[self.room.pk]),
            {'before': self.message.pk + 1},
        )

        self.assertEqual(room_response.status_code, 200)
        self.assertContains(room_response, 'aria-pressed="true"')
        self.assertContains(room_response, 'fa-solid fa-heart')
        self.assertNotContains(room_response, 'fa-thumbs-up')
        self.assertNotContains(room_response, 'fa-thumbs-down')
        self.assertEqual(history_response.status_code, 200)
        history_message = history_response.json()['messages'][0]
        self.assertEqual(history_message['like_count'], 1)
        self.assertEqual(history_message['dislike_count'], 0)
        self.assertEqual(history_message['user_reaction'], 'like')
