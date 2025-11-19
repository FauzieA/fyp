# cctv/routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/cctv/status/$", consumers.CameraStatusConsumer.as_asgi()),
    re_path(r"ws/automation/status/$",
            consumers.AutomationStatusConsumer.as_asgi()),
]
