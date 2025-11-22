# lights/serializers.py
from rest_framework import serializers
from .models import LightBrand, LightModel, SmartLight, DeviceAudit

class LightBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = LightBrand
        fields = ["id", "name", "created"]


class LightModelSerializer(serializers.ModelSerializer):
    brand = LightBrandSerializer(read_only=True)
    brand_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = LightModel
        fields = ["id", "name", "brand", "brand_id", "capabilities", "created"]


class SmartLightSerializer(serializers.ModelSerializer):
    model = LightModelSerializer(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = SmartLight
        fields = [
            "id",
            "name",
            "location",
            "model",
            "cloud_device_id",
            "local_ip",
            "is_on",
            "brightness",
            "status",
            "raw_meta",
            "created",
        ]


class SmartLightCreateSerializer(serializers.Serializer):
    """
    Data expected when registering a device from cloud:
    - cloud_device_id: taken from LIFX list
    - model_name: text input (will auto-create model)
    - name: local display name (optional, default from LIFX)
    - location: optional
    """
    cloud_device_id = serializers.CharField()
    model_name = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)


class LifxCloudDeviceSerializer(serializers.Serializer):
    """
    DTO for devices returned by LIFX list endpoint (subset)
    """
    id = serializers.CharField()
    label = serializers.CharField(required=False, allow_null=True)
    product = serializers.DictField(required=False)
    power = serializers.CharField(required=False)
    brightness = serializers.FloatField(required=False)
    connected = serializers.BooleanField(required=False)
    
