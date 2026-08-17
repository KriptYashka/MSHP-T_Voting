from django.urls import path

from .consumers import VotingConsumer

websocket_urlpatterns = [
    path('ws/voting/', VotingConsumer.as_asgi()),
]
