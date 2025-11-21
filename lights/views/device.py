from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from lights.models import SmartLight, DeviceAudit
from lights.serializers import SmartLightSerializer
from lights.api.lifx_api import LIFXApi, LifxApiError


class SmartLightListView(APIView):
    """
    GET: List all locally registered SmartLight devices.
    """
    def get(self, request):
        lights = SmartLight.objects.select_related("model__brand").all()
        return Response(SmartLightSerializer(lights, many=True).data)


class SmartLightControlView(APIView):
    """
    POST controls:
        action=power, value=on/off
        action=brightness, value=float(0.0–1.0)
    """
    def post(self, request, pk):
        light = get_object_or_404(SmartLight, pk=pk)
        action = request.data.get("action")
        value = request.data.get("value")

        api = LIFXApi()

        try:
            if action == "power":
                is_on = str(value).lower() in ("on", "1", "true")
                if is_on:
                    result = api.power_on(light.cloud_device_id)
                else:
                    result = api.power_off(light.cloud_device_id)

                light.is_on = is_on
                light.save()

            elif action == "brightness":
                b = float(value)
                if not (0.0 <= b <= 1.0):
                    return Response({"detail": "brightness must be 0.0–1.0"}, status=400)

                result = api.set_brightness(light.cloud_device_id, b)

                light.brightness = b
                light.save()

            else:
                return Response({"detail": "Unsupported action"}, status=400)

            DeviceAudit.objects.create(
                device=light, action=action,
                payload={"value": value}, result={"resp": result}
            )

            return Response({"ok": True, "result": result})

        except LifxApiError as e:
            return Response({"detail": str(e)}, status=401)
