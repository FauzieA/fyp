from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
import json


class GetDahuaMotionStatusView(APIView):
    """
    Endpoint to receive motion detection events (start/stop) from DoLynk.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            event_type = data.get("eventType")
            device_id = data.get("deviceId")
            motion_status = data.get("status")
            if event_type == "motionDetect":
                if motion_status == "start":
                    # Turn on all lights linked to this device
                    pass
                elif motion_status == "stop":
                    # Turn off all lights linked to this device
                    pass
                else:
                    pass
                return Response({"message": "Event received"},
                                status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
