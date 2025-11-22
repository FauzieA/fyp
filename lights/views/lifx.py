# lights/api/views/lifx.py

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from lights.services.lifx_service import LIFXService, LifxApiError
from lights.serializers import LifxCloudDeviceSerializer, SmartLightSerializer
from lights.models import SmartLight, LightBrand, LightModel, DeviceAudit
from rest_framework.permissions import IsAuthenticated, IsAdminUser

logger = logging.getLogger(__name__)


class LifxCloudListView(APIView):
    """
    GET /lifx/cloud/list/?exclude_registered=1
    Returns all LIFX cloud devices, optionally excluding ones already registered locally.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]  # enforce JWT auth
    service = LIFXService()

    def get(self, request):
        exclude_registered = request.GET.get("exclude_registered") == "1"

        cloud_devices = self.service.fetch_all_cloud_lights()
        out = []

        # Fetch all registered cloud_device_ids in one query for optimization
        registered_ids = set()
        if exclude_registered:
            registered_ids = set(
                SmartLight.objects.values_list('cloud_device_id', flat=True)
            )

        for device in cloud_devices:
            cloud_id = device.get("id")
            device["status"] = self.service.map_lifx_status_to_field(device)

            if exclude_registered and cloud_id in registered_ids:
                continue

            out.append(LifxCloudDeviceSerializer(device).data)

        return Response({"results": out})


class LifxRegisterView(APIView):
    """
    POST /lights/register/
    User selects a cloud device from the list; only inputs name and location.
    
    """
    permission_classes = [IsAuthenticated, IsAdminUser]  # enforce JWT auth


    def post(self, request):
        cloud_device_id = request.data.get("cloud_device_id")
        name = request.data.get("name")
        location = request.data.get("location", "")

        if not cloud_device_id or not name:
            return Response(
                {"error": "cloud_device_id and name are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = LIFXService()

        # fetch cloud metadata
        try:
            cloud_meta = service.fetch_single_cloud_light(cloud_device_id)
            if not cloud_meta:
                return Response(
                    {"error": "Cloud device not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        except LifxApiError as e:
            return Response(
                {"error": f"Failed to fetch cloud device: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Prevent duplicate registration
        if SmartLight.objects.filter(cloud_device_id=cloud_device_id).exists():
            return Response(
                {"error": "This device is already registered"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Brand and Model setup
        brand_name = "LIFX"  # fixed by developer
        model_name = cloud_meta.get("product", {}).get("name", "Default Model")

        brand, _ = LightBrand.objects.get_or_create(name=brand_name)
        model, _ = LightModel.objects.get_or_create(name=model_name, brand=brand)

        # Create SmartLight
        light = SmartLight.objects.create(
            name=name,
            location=location,
            model=model,
            cloud_device_id=cloud_device_id,
            is_on=cloud_meta.get("power") == "on",
            brightness=cloud_meta.get("brightness", 1.0),
            status=service.map_lifx_status_to_field(cloud_meta),
            raw_meta=cloud_meta
        )

        # Audit
        DeviceAudit.objects.create(
            device=light,
            action="register",
            payload={"cloud_device_id": cloud_device_id, "name": name, "location": location, "cloud_meta": cloud_meta}
        )

        return Response(
            {"success": True, "light_id": str(light.id)},
            status=status.HTTP_201_CREATED
        )

class LifxControlView(APIView):
    """
    POST /lifx/<pk>/control/
    { "power": "on", "brightness": 0.5 }
    """
    permission_classes = [IsAuthenticated]  # enforce JWT auth
    service = LIFXService()

    def post(self, request, pk):
        try:
            light = SmartLight.objects.get(pk=pk, brand="lifx")
        except SmartLight.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            response = self.service.control_light(light, **request.data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("LIFX control error")
            return Response({"error": "internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"ok": True, "response": response})
