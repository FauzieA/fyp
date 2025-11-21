from rest_framework.generics import ListAPIView
from lights.models import LightBrand
from lights.serializers import LightBrandSerializer


class LightBrandListView(ListAPIView):
    """
    GET: List all smart light brands.
    """
    queryset = LightBrand.objects.all()
    serializer_class = LightBrandSerializer
