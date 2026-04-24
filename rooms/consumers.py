# rooms/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Room, RoomMember, Message


class RoomConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_id    = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'room_{self.room_id}'
        self.user       = self.scope['user']

        if isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        if not await self.check_membership():
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(self.room_group, {
            'type':      'member_joined',
            'user_id':   str(self.user.id),
            'user_name': self.user.name,
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            # ✅ Only broadcast DISCONNECTED if user is still a member
            # If they sent LEAVE_ROOM first, they're already removed — skip disconnect broadcast
            # This prevents graceful leave from pausing the video for everyone
            still_member = await self.check_membership()
            if still_member:
                await self.channel_layer.group_send(self.room_group, {
                    'type':      'member_disconnected',
                    'user_id':   str(self.user.id),
                    'user_name': self.user.name,
                })
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        data      = json.loads(text_data)
        event     = data.get('type')
        user_name = self.user.name
        user_id   = str(self.user.id)

        if   event == 'CHAT':           await self.handle_chat(data, user_id, user_name)
        elif event == 'READY':          await self.handle_ready(data, user_id, user_name)
        elif event == 'PLAY':           await self.handle_play(data, user_id, user_name)
        elif event == 'PAUSE':          await self.handle_pause(data, user_id, user_name)
        elif event == 'SEEK':           await self.handle_seek(data, user_id, user_name)
        elif event == 'NETWORK_WAIT':   await self.handle_network_wait(data, user_id, user_name)
        elif event == 'NETWORK_RESUME': await self.handle_network_ready(data, user_id, user_name)
        elif event == 'VIDEO_SELECTED': await self.handle_video_selected(data, user_id, user_name)
        elif event == 'SYNC_TIME':     await self.handle_sync_time(data, user_id, user_name)
        elif event == 'LEAVE_ROOM':     await self.handle_leave_room(data, user_id, user_name)
        elif event == 'SYNC_STATE':     await self.handle_sync_state(data, user_id, user_name)
        elif event == 'VOICE_JOIN':    await self.handle_voice_join(data, user_id, user_name)
        elif event == 'VOICE_LEAVE':   await self.handle_voice_leave(data, user_id, user_name)
        elif event in ('WEBRTC_OFFER', 'WEBRTC_ANSWER', 'WEBRTC_ICE'):
            await self.handle_webrtc_signal(data, user_id, user_name)

    # ── Handlers ───────────────────────────────────────────────
    async def handle_chat(self, data, user_id, user_name):
        text = data.get('text', '').strip()
        if not text:
            return
        await self.save_message(text)
        await self.channel_layer.group_send(self.room_group, {
            'type': 'chat_message', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name, 'text': text,
        })

    async def handle_ready(self, data, user_id, user_name):
        is_ready, all_ready = await self.toggle_ready()
        await self.channel_layer.group_send(self.room_group, {
            'type': 'ready_update', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name,
            'is_ready': is_ready, 'all_ready': all_ready,
        })

    async def handle_play(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'playback_play', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name,
            'timestamp': data.get('timestamp', 0),
        })

    async def handle_pause(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'playback_pause', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name,
            'timestamp': data.get('timestamp', 0),
        })

    async def handle_seek(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'playback_seek', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name,
            'timestamp': data.get('timestamp', 0),
        })

    async def handle_network_wait(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'network_wait', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name,
        })

    async def handle_network_ready(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'network_resume', 'sender_id': user_id,
            'user_id': user_id, 'user_name': user_name,
        })

    async def handle_sync_time(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type':      'sync_time',
            'sender_id': user_id,
            'timestamp': data.get('timestamp', 0),
        })

    async def handle_leave_room(self, data, user_id, user_name):
        """Member voluntarily leaving — broadcast MEMBER_LEFT to others"""
        await self.channel_layer.group_send(self.room_group, {
            'type':      'member_left',
            'user_id':   user_id,
            'user_name': user_name,
        })

    async def handle_video_selected(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'video_selected', 'sender_id': user_id, 'user_name': user_name,
        })

    async def handle_sync_state(self, data, user_id, user_name):
        """Broadcast current playback state — triggered when new member joins"""
        await self.channel_layer.group_send(self.room_group, {
            'type':       'sync_state',
            'sender_id':  user_id,
            'timestamp':  data.get('timestamp', 0),
            'is_playing': data.get('is_playing', False),
        })

    async def handle_voice_join(self, data, user_id, user_name):
        """Broadcast that a user joined the voice call — others create peer connections"""
        await self.channel_layer.group_send(self.room_group, {
            'type':      'voice_join',
            'user_id':   user_id,
            'user_name': user_name,
        })

    async def handle_voice_leave(self, data, user_id, user_name):
        """Broadcast that a user left the voice call"""
        await self.channel_layer.group_send(self.room_group, {
            'type':      'voice_leave',
            'user_id':   user_id,
            'user_name': user_name,
        })

    async def handle_webrtc_signal(self, data, user_id, user_name):
        await self.channel_layer.group_send(self.room_group, {
            'type': 'webrtc_signal', 'sender': user_id,
            'target': data.get('target'), 'signal_type': data.get('type'),
            'sdp': data.get('sdp'), 'candidate': data.get('candidate'),
        })

    # ── Broadcast handlers ─────────────────────────────────────
    async def member_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'MEMBER_JOINED',
            'user_id': event['user_id'], 'user_name': event['user_name'],
        }))

    async def sync_time(self, event):
        await self.send(text_data=json.dumps({
            'type':      'SYNC_TIME',
            'sender_id': event['sender_id'],
            'timestamp': event['timestamp'],
        }))

    async def member_left(self, event):
        await self.send(text_data=json.dumps({
            'type':      'MEMBER_LEFT',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    async def member_disconnected(self, event):
        await self.send(text_data=json.dumps({
            'type': 'MEMBER_DISCONNECTED',
            'user_id': event['user_id'], 'user_name': event['user_name'],
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'CHAT', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
            'text': event['text'],
        }))

    async def ready_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'READY', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
            'is_ready': event['is_ready'], 'all_ready': event['all_ready'],
        }))

    async def playback_play(self, event):
        await self.send(text_data=json.dumps({
            'type': 'PLAY', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
            'timestamp': event['timestamp'],
        }))

    async def playback_pause(self, event):
        await self.send(text_data=json.dumps({
            'type': 'PAUSE', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
            'timestamp': event['timestamp'],
        }))

    async def playback_seek(self, event):
        await self.send(text_data=json.dumps({
            'type': 'SEEK', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
            'timestamp': event['timestamp'],
        }))

    async def network_wait(self, event):
        await self.send(text_data=json.dumps({
            'type': 'NETWORK_WAIT', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
        }))

    async def network_resume(self, event):
        await self.send(text_data=json.dumps({
            'type': 'NETWORK_RESUME', 'sender_id': event['sender_id'],
            'user_id': event['user_id'], 'user_name': event['user_name'],
        }))

    async def video_selected(self, event):
        await self.send(text_data=json.dumps({
            'type': 'VIDEO_SELECTED',
            'sender_id': event['sender_id'], 'user_name': event['user_name'],
        }))

    async def sync_state(self, event):
        await self.send(text_data=json.dumps({
            'type':       'SYNC_STATE',
            'sender_id':  event['sender_id'],
            'timestamp':  event['timestamp'],
            'is_playing': event['is_playing'],
        }))

    async def voice_join(self, event):
        await self.send(text_data=json.dumps({
            'type':      'VOICE_JOIN',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    async def voice_leave(self, event):
        await self.send(text_data=json.dumps({
            'type':      'VOICE_LEAVE',
            'user_id':   event['user_id'],
            'user_name': event['user_name'],
        }))

    async def webrtc_signal(self, event):
        await self.send(text_data=json.dumps({
            'type': event['signal_type'], 'sender': event['sender'],
            'target': event['target'], 'sdp': event.get('sdp'),
            'candidate': event.get('candidate'),
        }))

    # ── DB helpers ──────────────────────────────────────────────
    @database_sync_to_async
    def check_membership(self):
        return RoomMember.objects.filter(room_id=self.room_id, user=self.user).exists()

    @database_sync_to_async
    def is_host(self):
        return Room.objects.filter(id=self.room_id, host=self.user).exists()

    @database_sync_to_async
    def toggle_ready(self):
        from django.db import transaction
        with transaction.atomic():
            member = RoomMember.objects.select_for_update().get(
                room_id=self.room_id, user=self.user
            )
            member.is_ready = not member.is_ready
            member.save()
            all_ready = not RoomMember.objects.filter(
                room_id=self.room_id, is_ready=False
            ).exists()
        return member.is_ready, all_ready

    @database_sync_to_async
    def save_message(self, text):
        return Message.objects.create(room_id=self.room_id, sender=self.user, text=text)
    
