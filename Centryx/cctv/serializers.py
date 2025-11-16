from integration.services.cctv_services import (get_dahua_client,
                                                get_hikvision_client)
from rest_framework import serializers

from cctv.models import Automation, Brand, Camera, CCTVModel

dahua = get_dahua_client()
hikvision = get_hikvision_client()
brands = {'dahua': dahua, 'hikvision': hikvision}


class BrandSerializer(serializers.ModelSerializer):
    """Brand Model Serializer"""
    class Meta:
        model = Brand
        fields = ['id', 'name']


class CCTVModelSerializer(serializers.ModelSerializer):
    """CCTV Model Serializer"""
    brand = BrandSerializer(read_only=True)

    class Meta:
        model = CCTVModel
        fields = ['id', 'name', 'brand']


class CameraSerializer(serializers.ModelSerializer):
    """Camera Model Serializer"""
    model = CCTVModelSerializer(read_only=True)

    class Meta:
        model = Camera
        fields = ['id', 'identifier', 'model', 'location', 'created_at']


class CameraCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Camera with existing
    brand and new/existing model
    """
    brand = serializers.CharField(write_only=True)
    model_name = serializers.CharField(write_only=True)

    class Meta:
        model = Camera
        fields = [
            'id',
            'identifier',
            'brand',
            'model_name',
            'location',
            'name']

    def create(self, validated_data):
        brand_name = validated_data.pop('brand')
        model_name = validated_data.pop('model_name')

        # Get existing brand (error if not found)
        try:
            brand = Brand.objects.get(name=brand_name)
        except Brand.DoesNotExist:
            raise serializers.ValidationError(
                {"brand": "This brand does not exist."})

        # Get or create model under that brand
        model, _ = CCTVModel.objects.get_or_create(
            name=model_name, brand=brand)

        # Create camera
        camera = Camera.objects.create(model=model, **validated_data)
        return camera


class BrandListSerializer(serializers.ModelSerializer):
    """Serializer for listing Brands"""
    class Meta:
        model = Brand
        fields = ['name']


class CameraDetailsSerializer(serializers.ModelSerializer):
    """Serializer that returns camera name, brand, model, and location"""
    brand = serializers.CharField(source='model.brand.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)

    class Meta:
        model = Camera
        fields = ['identifier', 'name', 'brand', 'model_name', 'location']


class CameraWithLiveUrlSerializer(serializers.ModelSerializer):
    """Serializer that returns camera details with live streaming URL"""
    brand = serializers.CharField(source='model.brand.name', read_only=True)
    live_url = serializers.SerializerMethodField()

    class Meta:
        model = Camera
        fields = ['identifier', 'name', 'location', 'brand', 'live_url']

    def get_live_url(self, obj):
        """Fetch live stream URL from the appropriate API based on brand"""
        brand_name = obj.model.brand.name.lower()
        identifier = obj.identifier

        try:
            # ----------------------------
            #  Dahua
            # ----------------------------
            if brand_name == 'dahua':
                response = brands['dahua'].get_hls_live_list(
                    device_id=identifier)
                if str(response.get("code")) == "200":
                    return response.get("url")
                return None

            # ----------------------------
            #  Hikvision
            # ----------------------------
            elif brand_name == 'hikvision':
                response = brands['hikvision'].get_stream(
                    device_id=identifier,
                    type_="1")
                if response.get("errorCode") == "0":
                    return response.get("url")
                return None

            # ------------------------------
            #  Other brands start from here
            # ------------------------------

            else:
                return None

        except Exception as e:
            # Return None if there's an error fetching the URL
            return None


class CameraLiveUrlSerializer(serializers.ModelSerializer):
    """Serializer that returns camera details with live streaming URL.
    This serializer returns the exact keys as used by the previous
    POST-based implementation: Dahua -> `url`, Hikvision -> `stream_url`.
    """
    brand = serializers.CharField(source='model.brand.name', read_only=True)
    live_url = serializers.SerializerMethodField()

    class Meta:
        model = Camera
        fields = ['identifier', 'name', 'location', 'brand', 'live_url']

    def get_live_url(self, obj):
        brand_name = obj.model.brand.name.lower()
        identifier = obj.identifier
        try:
            if brand_name == 'dahua':
                response = brands['dahua'].get_hls_live_list(device_id=identifier)
                if str(response.get('code')) == '200':
                    # return same key as previous implementation
                    return response.get('url')
                return None

            elif brand_name == 'hikvision':
                response = brands['hikvision'].get_stream(
                    device_id=identifier, type_='1', expire_time=600)
                if response.get('errorCode') == '0':
                    # previous implementation returned `stream_url` for POST
                    return response.get('stream_url')
                return None

            else:
                return None
        except Exception:
            return None


class AutomationSerializer(serializers.ModelSerializer):
    """Serializer for Automation Model"""
    class Meta:
        model = Automation
        fields = ['active']


class CameraRecordingUrlSerializer(serializers.ModelSerializer):
    """Serializer that returns camera details with recording playback URL"""
    brand = serializers.CharField(source='model.brand.name', read_only=True)
    recording_url = serializers.SerializerMethodField()

    class Meta:
        model = Camera
        fields = ['identifier', 'name', 'location', 'brand', 'recording_url']

    def get_recording_url(self, obj):
        """Fetch recording playback URL from the appropriate API based on brand"""
        brand_name = obj.model.brand.name.lower()
        identifier = obj.identifier
        
        # Get time parameters from context
        context = self.context
        start_time = context.get('start_time')
        end_time = context.get('end_time')
        
        if not start_time or not end_time:
            return None

        try:
            # ----------------------------
            #  Dahua
            # ----------------------------
            if brand_name == 'dahua':
                # Convert ISO format to Dahua format
                # ISO: 2025-11-12T10:00:00 -> Dahua: 2025-11-12 10:00:00
                begin_time = start_time.replace('T', ' ')
                end_time_formatted = end_time.replace('T', ' ')
                
                response = brands['dahua'].get_hls_playback_list(
                    device_id=identifier,
                    begin_time=begin_time,
                    end_time=end_time_formatted
                )
                if str(response.get("code")) == "200":
                    return response.get("url")
                return None

            # ----------------------------
            #  Hikvision
            # ----------------------------
            elif brand_name == 'hikvision':
                response = brands['hikvision'].get_stream(
                    device_id=identifier,
                    type_='2',
                    start_time=start_time,
                    stop_time=end_time,
                    expire_time=600
                )
                if response.get("errorCode") == "0":
                    return response.get("stream_url")
                return None

            # ------------------------------
            #  Other brands start from here
            # ------------------------------
            else:
                return None

        except Exception as e:
            # Return None if there's an error fetching the URL
            return None
