# rooms/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Room, RoomMember, Message


class RoomConsumer(AsyncWebsocketConsumer):

    # ── Connection ────────────────────────────────────────────
    async def connect(self):
        self.room_id   = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'room_{self.room_id}'
        self.user      = self.scope['user']

        # Reject unauthenticated connections
        if isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        # Verify user is a member of this room
        is_member = await self.check_membership()
        if not is_member:
            await self.close(code=4003)
            return

        # Join the room's channel group
        await self.channel_layer.group_add(
            self.room_group,
            self.channel_name
        )
        await self.accept()

        # Notify others that this user joined
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'member_joined',
                'user_id':   str(self.user.id),
                'user_name': self.user.name,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            # Notify others this user left
            await self.channel_layer.group_send(
                self.room_group,
                {
                    'type':      'member_left',
                    'user_id':   str(self.user.id),
                    'user_name': self.user.name,
                }
            )
            await self.channel_layer.group_discard(
                self.room_group,
                self.channel_name
            )

    # ── Receive from client ───────────────────────────────────
    async def receive(self, text_data):
        data      = json.loads(text_data)
        event     = data.get('type')
        user_name = self.user.name
        user_id   = str(self.user.id)

        # Route to correct handler based on event type
        if event == 'CHAT':
            await self.handle_chat(data, user_id, user_name)

        elif event == 'READY':
            await self.handle_ready(data, user_id, user_name)

        elif event == 'PAUSE':
            await self.handle_pause(data, user_id, user_name)

        elif event == 'SEEK':
            await self.handle_seek(data, user_id, user_name)

        elif event == 'NETWORK_WAIT':
            await self.handle_network_wait(data, user_id, user_name)

        elif event == 'NETWORK_READY':
            await self.handle_network_ready(data, user_id, user_name)

    # ── Event Handlers ────────────────────────────────────────
    async def handle_chat(self, data, user_id, user_name):
        text = data.get('text', '').strip()
        if not text:
            return

        # Save message to database
        await self.save_message(text)

        # Broadcast to all room members
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'chat_message',
                'user_id':   user_id,
                'user_name': user_name,
                'text':      text,
            }
        )

    async def handle_ready(self, data, user_id, user_name):
        # Toggle ready state in DB
        is_ready, all_ready = await self.toggle_ready()

        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'ready_update',
                'user_id':   user_id,
                'user_name': user_name,
                'is_ready':  is_ready,
                'all_ready': all_ready,
            }
        )

    async def handle_pause(self, data, user_id, user_name):
        """Only host can pause/play — broadcast pause + who did it"""
        if not await self.is_host():
            return

        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'playback_pause',
                'user_id':   user_id,
                'user_name': user_name,
                'timestamp': data.get('timestamp', 0),
            }
        )

    async def handle_seek(self, data, user_id, user_name):
        """Only host can seek"""
        if not await self.is_host():
            return

        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'playback_seek',
                'user_id':   user_id,
                'user_name': user_name,
                'timestamp': data.get('timestamp', 0),
            }
        )

    async def handle_network_wait(self, data, user_id, user_name):
        """Member is buffering — pause everyone"""
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'network_wait',
                'user_id':   user_id,
                'user_name': user_name,
            }
        )

    async def handle_network_ready(self, data, user_id, user_name):
        """Member finished buffering — resume everyone"""
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':      'network_resume',
                'user_id':   user_id,
                'user_name': user_name,
            }
        )

    # ── Broadcast handlers (group_send → send to client) ─────
    # These methods are called by group_send and forward to WebSocket

    async def member_joined(self, event):
        await self.send(text_data=json.dumps({
            'type':      'MEMBER_JOINED',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    async def member_left(self, event):
        await self.send(text_data=json.dumps({
            'type':      'MEMBER_LEFT',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':      'CHAT',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
            'text':      event['text'],
        }))

    async def ready_update(self, event):
        await self.send(text_data=json.dumps({
            'type':      'READY',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
            'is_ready':  event['is_ready'],
            'all_ready': event['all_ready'],
        }))

    async def playback_pause(self, event):
        await self.send(text_data=json.dumps({
            'type':      'PAUSE',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp'],
        }))

    async def playback_seek(self, event):
        await self.send(text_data=json.dumps({
            'type':      'SEEK',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp'],
        }))

    async def network_wait(self, event):
        await self.send(text_data=json.dumps({
            'type':      'NETWORK_WAIT',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    async def network_resume(self, event):
        await self.send(text_data=json.dumps({
            'type':      'NETWORK_RESUME',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    # ── Database helpers ──────────────────────────────────────
    @database_sync_to_async
    def check_membership(self):
        return RoomMember.objects.filter(
            room_id=self.room_id,
            user=self.user
        ).exists()

    @database_sync_to_async
    def is_host(self):
        return Room.objects.filter(
            id=self.room_id,
            host=self.user
        ).exists()

    @database_sync_to_async
    def toggle_ready(self):
        member = RoomMember.objects.get(
            room_id=self.room_id,
            user=self.user
        )
        member.is_ready = not member.is_ready
        member.save()

        all_ready = not RoomMember.objects.filter(
            room_id=self.room_id,
            is_ready=False
        ).exists()

        return member.is_ready, all_ready

    @database_sync_to_async
    def save_message(self, text):
        return Message.objects.create(
            room_id=self.room_id,
            sender=self.user,
            text=text
        )
        
