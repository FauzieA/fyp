from rest_framework.generics import ListAPIView
from lights.models import LightBrand
from lights.serializers import LightBrandSerializer
from rest_framework.permissions import IsAuthenticated, IsAdminUser


class LightBrandListView(ListAPIView):
    """
    GET: List all smart light brands.
    """
    queryset = LightBrand.objects.all()
    serializer_class = LightBrandSerializer
    permission_classes = [IsAuthenticated,IsAdminUser]  # enforce JWT auth and admin only
