import json
import threading

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integration.serializers import CustomUserSerializer

User = get_user_model()


class GetDahuaMotionStatusView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            print(data)
            # Handle both event formats
            event_type = data.get("msgType")
            device_id = data.get("deviceId")
            action = data.get("action")

            # Motion or Smart Motion Detection
            if event_type == "videoMotion":
                if action == "start":
                    # Get all lights associated with this device and turn on
                    pass

                elif action == "stop":
                    # Get all lights associated with this device and turn off
                    pass
                return Response({"message": "Event received"},
                                status=status.HTTP_200_OK)

            elif event_type == "offline":
                # Send Notfication to admin that device is offline
                return Response({"message": "Offline event received"},
                                status=status.HTTP_200_OK)

            return Response({"message": f"Unknown event type: {event_type}"},
                            status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class ListUsersView(APIView):
    """
    List all users - admin only endpoint
    GET /integration/users/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        users = User.objects.all()
        serializer = CustomUserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
