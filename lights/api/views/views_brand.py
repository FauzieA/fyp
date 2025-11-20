# lights/views_brand.py
from rest_framework import generics
from lights.models import LightBrand
from lights.serializers import LightBrandSerializer

class LightBrandListView(generics.ListAPIView):
    queryset = LightBrand.objects.all().order_by("name")
    serializer_class = LightBrandSerializer
