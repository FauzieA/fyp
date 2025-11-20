from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SmartLight, LightBrand
from .serializers import (
    SmartLightSerializer,
    SmartLightCreateSerializer,
    LightBrandSerializer,
)
from .services.lifx_service import LIFXService


class LightBrandListView(generics.ListAPIView):
    queryset = LightBrand.objects.all()
    serializer_class = LightBrandSerializer


class SmartLightListCreateView(APIView):
    def get(self, request):
        lights = SmartLight.objects.all()
        return Response(SmartLightSerializer(lights, many=True).data)

    def post(self, request):
        serializer = SmartLightCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = LIFXService()
        light = service.register_device(**serializer.validated_data)

        return Response(SmartLightSerializer(light).data, status=201)


class SmartLightControlView(APIView):
    def post(self, request, pk):
        action = request.data.get("action")
        light = SmartLight.objects.get(id=pk)

        service = LIFXService()

        if action == "on":
            result = service.turn_on(light)
        elif action == "off":
            result = service.turn_off(light)
        elif action == "brightness":
            brightness = float(request.data.get("brightness"))
            result = service.set_brightness(light, brightness)
        else:
            return Response({"error": "Invalid action"}, status=400)

        return Response({"status": "ok", "result": result})
