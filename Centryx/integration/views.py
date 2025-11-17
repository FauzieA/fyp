import json
import threading

from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
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


class ListUsersView(generics.ListAPIView):
    """API view to list users with search and pagination support."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    pagination_class = PageNumberPagination
    pagination_class.page_size = 1
    ordering = ['date_joined']  # Use a valid field
    filter_backends = [SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
