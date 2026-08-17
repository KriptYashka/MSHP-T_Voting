from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .state import get_state_dict

VOTING_GROUP = 'voting'


def broadcast_voting():
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(
            VOTING_GROUP,
            {'type': 'voting.changed'},
        )


class VotingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(VOTING_GROUP, self.channel_name)
        await self.accept()
        await self.send_state()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(VOTING_GROUP, self.channel_name)

    @database_sync_to_async
    def get_state(self):
        return get_state_dict(self.scope.get('user'))

    async def send_state(self, event=None):
        state = await self.get_state()
        await self.send_json({'type': 'state', 'data': state})

    async def voting_changed(self, event):
        await self.send_state()
