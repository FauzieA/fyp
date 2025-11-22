# lights/views/device.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import ValidationError
from lights.models import SmartLight
from lights.serializers import SmartLightSerializer
from lights.services.lifx_service import LIFXService, LifxApiError  
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.core.cache import cache


# List + search + filter + pagination handled with ListAPIView (uses DRF pagination)
class SmartLightListView(ListAPIView):
    serializer_class = SmartLightSerializer
    queryset = SmartLight.objects.select_related("model__brand").all()
    permission_classes = [IsAuthenticated]  # enforce JWT auth and admin only
    # simple search by name/location via query param ?search=
    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("search", "").strip()
        status_filter = self.request.query_params.get("status")  # on|off
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q))
        if status_filter == "on":
            qs = qs.filter(is_on=True)
        elif status_filter == "off":
            qs = qs.filter(is_on=False)
        return qs

    def list(self, request, *args, **kwargs):
        # return lights list + summary for the returned subset
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            lights_data = serializer.data
            total = queryset.count()
            on_count = queryset.filter(is_on=True).count()
            off_count = total - on_count
            return self.get_paginated_response({
                "lights": lights_data,
                "summary": {"total": total, "on": on_count, "off": off_count}
            })
        serializer = self.get_serializer(queryset, many=True)
        total = queryset.count()
        on_count = queryset.filter(is_on=True).count()
        off_count = total - on_count
        return Response({"lights": serializer.data, "summary": {"total": total, "on": on_count, "off": off_count}})


class SmartLightControlView(APIView):
    """
    POST /lights/devices/<uuid:pk>/control/
    Handles turning lights on/off, setting brightness, etc.
    """
    permission_classes = [IsAuthenticated]  # enforce JWT auth


    def post(self, request, pk):
        try:
            light = SmartLight.objects.get(pk=pk)
        except SmartLight.DoesNotExist:
            return Response({"error": "Light not found"}, status=status.HTTP_404_NOT_FOUND)

        service = LIFXService()

        # Build kwargs safely
        state_kwargs = {}

        # Power
        power = request.data.get("power")
        if power is not None:
            if power not in ["on", "off"]:
                return Response({"error": "Invalid power value"}, status=status.HTTP_400_BAD_REQUEST)
            state_kwargs["power"] = power

        # Brightness
        brightness = request.data.get("brightness")
        if brightness is not None:
            try:
                b = float(brightness)
                if not (0 <= b <= 1):
                    return Response({"error": "Brightness must be between 0 and 1"}, status=status.HTTP_400_BAD_REQUEST)
                state_kwargs["brightness"] = b
            except (ValueError, TypeError):
                return Response({"error": "Brightness must be a number"}, status=status.HTTP_400_BAD_REQUEST)

        # Optionally, add other fields (color, color_temp, etc.) here

        if not state_kwargs:
            return Response({"error": "No valid control parameters provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Call LIFXService
        try:
            result = service.control_light(light, **state_kwargs)
        except ValidationError as e:
            return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"success": True, "result": result}, status=status.HTTP_200_OK)

class SmartLightDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]  # enforce JWT auth

    def delete(self, request, pk):
        light = get_object_or_404(SmartLight, pk=pk)
        # audit before delete (optional)
        from lights.models import DeviceAudit
        DeviceAudit.objects.create(device=light, action="delete", payload={}, result={"ok": True})
        light.delete()
        return Response({"detail": "Device deleted"}, status=200)


class SmartLightStatsView(APIView):

    """
    GET /lights/stats/  -> return total, online, offline counts (online/offline based on status field)
    """
    permission_classes = [IsAuthenticated]  # enforce JWT auth

    def get(self, request):
        total = SmartLight.objects.count()
        online = SmartLight.objects.filter(status__in=["ok"]).count()
        offline = SmartLight.objects.filter(status__in=["offline"]).count()
        # treat timed_out/unknown as neither online nor offline (or change logic as needed)
        return Response({"total": total, "online": online, "offline": offline})


class BulkControlView(APIView):
    """
    POST /lights/bulk_control/ 
    Body: { "action": "all_on" | "all_off" | "day_mode" | "night_mode" | "eco_mode" }
    """
    permission_classes = [IsAuthenticated]  # enforce JWT auth

    def post(self, request):
        action = request.data.get("action")
        lights = SmartLight.objects.all()
        service = LIFXService()
        mapping = {
            "all_on": {"power": "on", "brightness": 1.0},
            "all_off": {"power": "off"},
            "day_mode": {"power": "on", "brightness": 0.8},
            "night_mode": {"power": "on", "brightness": 0.3},
            "eco_mode": {"power": "on", "brightness": 0.5},
        }
        if action not in mapping:
            return Response({"detail": "Unsupported bulk action"}, status=400)

        state = mapping[action]
        results = []
        for light in lights:
            # If action includes brightness but the light should only be set if currently on,
            # you may check light.is_on here; frontend described "all turned on lights will be at X".
            if action in ("day_mode", "night_mode", "eco_mode"):
                # only apply brightness to lights currently on
                if not light.is_on:
                    continue
                r = service.control_light(light, **{k: v for k, v in state.items()})
            else:
                r = service.control_light(light, **{k: v for k, v in state.items()})
            results.append({"id": str(light.id), "result": r})
        return Response({"ok": True, "results": results})
