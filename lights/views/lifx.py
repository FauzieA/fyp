from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from lights.serializers import (
    SmartLightCreateSerializer,
    LifxCloudDeviceSerializer
)
from lights.models import LightBrand, LightModel, SmartLight, DeviceAudit
from lights.api.lifx_api import LIFXApi, LifxApiError


class LifxCloudListView(APIView):
    """
    GET: List all LIFX Cloud devices for this account.
    """
    def get(self, request):
        api = LIFXApi()
        try:
            devices = api.list_all_lights()
        except LifxApiError as e:
            return Response({"detail": str(e)}, status=401)

        out = [LifxCloudDeviceSerializer(d).data for d in devices]
        return Response(out)


class LifxRegisterDeviceView(APIView):
    """
    POST: Register a cloud LIFX device to the local DB.

    Body:
    {
        "cloud_device_id": "...",
        "model_name": "...",
        "name": "...",
        "location": "..."
    }
    """
    def post(self, request):
        serializer = SmartLightCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        api = LIFXApi()

        # Verify device exists in cloud account
        try:
            metadata = api.get_light(data["cloud_device_id"])
        except LifxApiError as e:
            return Response({"detail": str(e)}, status=404)

        # Ensure brand exists
        brand, _ = LightBrand.objects.get_or_create(name="LIFX")

        # Auto-create model
        model, _ = LightModel.objects.get_or_create(
            name=data["model_name"],
            brand=brand,
            defaults={"capabilities": metadata.get("product", {}).get("capabilities", {})},
        )

        # Determine final device name
        name = (
            data.get("name")
            or metadata.get("label")
            or metadata.get("user_supplied_name")
            or f"{brand.name} {data['model_name']}"
        )

        # Create SmartLight entry
        with transaction.atomic():
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

            DeviceAudit.objects.create(
                device=light, action="register",
                payload={"metadata": metadata}, result={"ok": True}
            )

        from lights.serializers import SmartLightSerializer
        return Response(SmartLightSerializer(light).data, status=201)
