import asyncio
# cctv/consumers.py
import json

import jwt
import redis.asyncio as redis
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


class CameraStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # JWT authentication: support token in query param or header
        token = None
        # Try to get token from query string
        query_string = self.scope.get('query_string', b'').decode()
        if query_string:
            import urllib.parse
            params = urllib.parse.parse_qs(query_string)
            token_list = params.get('token')
            if token_list:
                token = token_list[0]
        # Try to get token from headers
        if not token:
            headers = dict((k.decode(), v.decode())
                           for k, v in self.scope.get('headers', []))
            auth_header = headers.get('authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]
        # Validate token
        if not token:
            await self.close()
            return
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"])
            self.scope['user_id'] = payload.get('user_id')
        except Exception:
            await self.close()
            return

        await self.accept()
        self.redis = redis.Redis(host='localhost', port=6379, db=0)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe('camera_statistics')
        self.pubsub_task = asyncio.create_task(self.listen_redis())
        # Send initial status
        try:
            stats = await self.redis.get('camera_statistics')
            if stats:
                stats = json.loads(stats)
            else:
                stats = {'total': 0, 'online': 0, 'offline': 0}
        except Exception:
            stats = {'total': 0, 'online': 0, 'offline': 0}
        await self.send(text_data=json.dumps(stats))

    async def disconnect(self, close_code):
        self.pubsub_task.cancel()
        await self.pubsub.unsubscribe('camera_statistics')
        await self.pubsub.close()
        await self.redis.close()

    async def listen_redis(self):
        try:
            while True:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        stats = json.loads(message['data'])
                    except Exception:
                        stats = {'total': 0, 'online': 0, 'offline': 0}
                    await self.send(text_data=json.dumps(stats))
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass


class AutomationStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # JWT authentication: support token in query param or header
        token = None
        # Try to get token from query string
        query_string = self.scope.get('query_string', b'').decode()
        if query_string:
            import urllib.parse
            params = urllib.parse.parse_qs(query_string)
            token_list = params.get('token')
            if token_list:
                token = token_list[0]
        # Try to get token from headers
        if not token:
            headers = dict((k.decode(), v.decode())
                           for k, v in self.scope.get('headers', []))
            auth_header = headers.get('authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]
        # Validate token
        if not token:
            await self.close()
            return
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"])
            self.scope['user_id'] = payload.get('user_id')
        except Exception:
            await self.close()
            return

        await self.accept()
        self.redis = redis.Redis(host='localhost', port=6379, db=0)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe('automation_status')
        self.pubsub_task = asyncio.create_task(self.listen_redis())
        # Send initial status
        try:
            status = await self.redis.get('automation_status')
            status = status.decode() if status else 'unknown'
        except Exception:
            status = 'unknown'
        await self.send(text_data=json.dumps({
            'automation_status': status
        }))

    async def disconnect(self, close_code):
        self.pubsub_task.cancel()
        await self.pubsub.unsubscribe('automation_status')
        await self.pubsub.close()
        await self.redis.close()

    async def listen_redis(self):
        try:
            while True:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    status = await self.redis.get('automation_status')
                    status = status.decode() if status else 'unknown'
                    await self.send(text_data=json.dumps({
                        'automation_status': status
                    }))
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
