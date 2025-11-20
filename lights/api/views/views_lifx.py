# lights/views_lifx.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from .api.lifx_api import LIFXApi, LifxApiError
from .serializers import (
    LifxCloudDeviceSerializer,
    SmartLightCreateSerializer,
    SmartLightSerializer,
)
from .models import LightBrand, LightModel, SmartLight, DeviceAudit


class LifxCloudListView(APIView):
    """
    GET: list all lights from the account's LIFX Cloud (so admin can pick from UI).
    """
    def get(self, request):
        api = LIFXApi()
        try:
            devices = api.list_all_lights()
        except LifxApiError as e:
            return Response({"detail": str(e)}, status=401)
        # map to DTO
        out = []
        for d in devices:
            dto = {
                "id": d.get("id"),
                "label": d.get("label") or d.get("user_supplied_name") or d.get("name"),
                "product": d.get("product", {}),
                "power": d.get("power"),
                "brightness": d.get("brightness"),
            }
            out.append(dto)
        return Response(out)


class LifxRegisterDeviceView(APIView):
    """
    POST: Register selected LIFX cloud device into our DB.
    Body: { cloud_device_id, model_name, name?, location? }
    Backend will validate that the device exists on LIFX cloud and then create
    or reuse LightModel (auto-create) under brand 'LIFX'.
    """
    def post(self, request):
        serializer = SmartLightCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        api = LIFXApi()
        metadata = api.get_light(data["cloud_device_id"])
        if not metadata:
            return Response({"detail": "Device not found in LIFX account"}, status=404)

        # ensure LIFX brand exists
        brand, _ = LightBrand.objects.get_or_create(name="LIFX")

        # auto-create model
        model_name = data["model_name"]
        model, _ = LightModel.objects.get_or_create(
            name=model_name,
            brand=brand,
            defaults={"capabilities": {"color": metadata.get("product", {}).get("capabilities", {}).get("color", False),
                                        "brightness": True}},
        )

        # choose name: provided or from LIFX metadata label
        name = data.get("name") or metadata.get("label") or metadata.get("user_supplied_name") or f"{brand.name} {model_name}"

        with transaction.atomic():
            # check uniqueness
            if SmartLight.objects.filter(cloud_device_id=data["cloud_device_id"]).exists():
                return Response({"detail": "Device already registered"}, status=400)

            light = SmartLight.objects.create(
                name=name,
                location=data.get("location", ""),
                model=model,
                cloud_device_id=data["cloud_device_id"],
                is_on=(metadata.get("power") == "on"),
                brightness=metadata.get("brightness"),
                raw_meta=metadata,
            )

            DeviceAudit.objects.create(device=light, action="register", payload={"metadata": metadata}, result={"ok": True})

        return Response(SmartLightSerializer(light).data, status=201)


class SmartLightListView(APIView):
    def get(self, request):
        queryset = SmartLight.objects.select_related("model__brand").all()
        return Response(SmartLightSerializer(queryset, many=True).data)


class SmartLightControlView(APIView):
    """
    Control endpoint. POST actions:
      - action=power, value=on/off
      - action=brightness, value=float(0.0-1.0)
    """
    def post(self, request, pk):
        light = get_object_or_404(SmartLight, pk=pk)
        action = request.data.get("action")
        value = request.data.get("value")
        api = LIFXApi()
        try:
            if action == "power":
                if str(value).lower() in ("on", "true", "1"):
                    result = api.power_on(light.cloud_device_id)
                    light.is_on = True
                else:
                    result = api.power_off(light.cloud_device_id)
                    light.is_on = False
                light.save()
                DeviceAudit.objects.create(device=light, action="power", payload={"value": value}, result={"resp": result})
                return Response({"ok": True, "result": result})

            elif action == "brightness":
                b = float(value)
                if b < 0.0 or b > 1.0:
                    return Response({"detail": "brightness must be 0.0-1.0"}, status=400)
                result = api.set_brightness(light.cloud_device_id, b)
                light.brightness = b
                light.save()
                DeviceAudit.objects.create(device=light, action="brightness", payload={"value": b}, result={"resp": result})
                return Response({"ok": True, "result": result})

            else:
                return Response({"detail": "Unsupported action"}, status=400)

        except LifxApiError as e:
            return Response({"detail": str(e)}, status=401)
        except Exception as e:
            DeviceAudit.objects.create(device=light, action="control_error", payload={"action": action, "value": value}, result={"error": str(e)})
            return Response({"detail": str(e)}, status=500)
