from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from integration.services.cctv_services import get_dahua_client
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cctv.models import Brand, Camera
from cctv.serializers import BrandSerializer, CameraCreateSerializer

dahua = get_dahua_client()
brands = {'dahua': dahua}


class AddCCTVView(APIView):
    """
    View to add a new CCTV device.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = request.data
        try:
            match data['brand'].lower():
                case 'dahua':
                    response = brands['dahua'].add_device(
                        device_id=data['identifier'],
                        dev_account=data['username'],
                        dev_password=data['dev_password']
                    )
                    if response.get("code") != "200":
                        return Response({"error": response.get(
                            "message")}, status=status.HTTP_400_BAD_REQUEST)
                case _:
                    raise ValueError("Unsupported brand")
            serializer = CameraCreateSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {"message": "CCTV device added successfully."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class DeleteCCTVView(APIView):
    """
    View to delete a CCTV device.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = request.data
        try:
            identifier = data.get('identifier')
            brand_name = data.get('brand')

            if not identifier or not brand_name:
                return Response(
                    {"error": "Missing brand or identifier"}, status=status.HTTP_400_BAD_REQUEST)

            # Find the camera
            camera = Camera.objects.filter(
                identifier=identifier,
                model__brand__name=brand_name).first()
            if not camera:
                return Response({"error": "Camera not found"},
                                status=status.HTTP_404_NOT_FOUND)

            # Call brand-specific deletion logic
            match brand_name.lower():
                case 'dahua':
                    response = dahua.delete_device(device_id=identifier)
                    if response.get("code") != "200":
                        return Response({"error": response.get(
                            "msg")}, status=status.HTTP_400_BAD_REQUEST)
                case _:
                    raise ValueError("Unsupported brand")

            # Delete camera from database
            camera.delete()

            return Response(
                {"message": "CCTV device deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class GetStreamUrlView(APIView):
    """
    API endpoint to retrieve live stream or recording playback URLs for CCTV devices.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get the stream URL for a CCTV device.
        """
        brand_name = request.query_params.get('brand')
        identifier = request.query_params.get('identifier')
        business_type = request.query_params.get('business_type', 'real')
        begin_time = request.query_params.get('begin_time')
        end_time = request.query_params.get('end_time')

        if not brand_name or not identifier:
            return Response(
                {"error": "Missing brand or identifier"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            match brand_name.lower():
                case 'dahua':
                    # For playback, times are required
                    if business_type in ['localRecord', 'cloudRecord']:
                        if not begin_time or not end_time:
                            return Response(
                                {"error": "begin_time and end_time required for recordings"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Call Dahua SDK
                    response = dahua.get_stream_url(
                        device_id=identifier,
                        business_type=business_type,
                        begin_time=begin_time,
                        end_time=end_time
                    )

                    # Handle API failure
                    if response.get("code") != "200":
                        return Response(
                            {"error": response.get("msg", "Failed to get stream URL")},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Success — standardize output
                    return Response({
                        "brand": brand_name,
                        "type": business_type,
                        "stream_url": response.get("url")
                    })

                case _:
                    return Response(
                        {"error": f"Unsupported brand '{brand_name}'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BrandListView(generics.ListAPIView):
    """
    View to list all CCTV brands.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class BrandModelListView(APIView):
    """
    View to list all CCTV models for a specific brand.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @method_decorator(cache_page(60 * 60 * 24 * 30, key_prefix="brand_models"))
    @method_decorator(vary_on_headers("Authorization"))
    def get(self, request, brand_name):
        try:
            models = brands[brand_name.lower()].get_camera_models()
            return Response(models)
        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
