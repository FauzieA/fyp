from rest_framework import serializers

from cctv.models import Brand, Camera, CCTVModel


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
    """Serializer for creating Camera with existing brand and new/existing model"""
    brand = serializers.CharField(write_only=True)
    model_name = serializers.CharField(write_only=True)

    class Meta:
        model = Camera
        fields = ['id', 'identifier', 'brand', 'model_name', 'location']

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
