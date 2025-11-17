import re

from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from integration.services.cctv_services import (get_dahua_client,
                                                get_hikvision_client)
from rest_framework import filters, generics, status
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cctv.decorators import cache_post
from cctv.models import Automation, Brand, Camera
from cctv.serializers import (AutomationSerializer, BrandSerializer,
                              CameraCreateSerializer, CameraDetailsSerializer,
                              CameraLiveUrlSerializer,
                              CameraRecordingUrlSerializer,
                              CameraWithLiveUrlSerializer)
from cctv.tasks import populate_live_urls_cache

dahua = get_dahua_client()
hikvision = get_hikvision_client()
brands = {'dahua': dahua, 'hikvision': hikvision}


class AddCCTVView(APIView):
    """
    Add a new CCTV device.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = request.data
        brand = data.get("brand", "").lower()
        response = ""

        try:
            match brand:
                # ----------------------------
                #  Dahua
                # ----------------------------
                case "dahua":
                    try:
                        response = brands["dahua"].add_device(
                            device_id=data.get("identifier"),
                            dev_account=data.get("username"),
                            dev_password=data.get("dev_password"),
                            category_code=data.get("category_code"),
                        )
                        if response.get("code") != "200":
                            return Response(
                                {"error": response.get("message")},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                    except Exception as e:
                        return Response(
                            {"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # ----------------------------
                #  Hikvision
                # ----------------------------
                case "hikvision":
                    try:
                        ezviz_serial_no = data.get("ezviz_serial_no")
                        ezviz_verify_code = data.get("ezviz_verify_code")

                        response = brands["hikvision"].add_device(
                            name=data.get("name"),
                            ezviz_serial_no=ezviz_serial_no,
                            ezviz_verify_code=ezviz_verify_code,
                        )
                        if response.get("errorCode") not in ("0", 0):
                            return Response(
                                {
                                    "error": response.get("message")},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        data['identifier'] = response.get("deviceID")
                    except Exception as e:
                        return Response(
                            {"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                case _:
                    raise ValueError("Unsupported brand")

            # Save to database if API succeeded
            serializer = CameraCreateSerializer(data=data)
            try:
                error_text = serializer.is_valid(raise_exception=True)
            except Exception as e:
                try:
                    error_text = str(e)
                    match = re.search(r"string='([^']+)'", error_text)
                    message = match.group(1) if match else error_text
                except Exception:
                    message = "An unexpected error occurred."

                return Response(
                    {"error": message},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer.save()

            return Response(
                {"message": response.get("message")},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class DeleteCCTVView(APIView):
    """
    Delete a CCTV device.
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
                # ----------------------------
                #  Dahua
                # ----------------------------
                case 'dahua':
                    response = dahua.delete_device(device_id=identifier)
                    if response.get("code") != "200":
                        return Response(
                            {"error": "Device could not be deleted."}, status=status.HTTP_400_BAD_REQUEST)

                # ----------------------------
                #  Hikvision
                # ----------------------------
                case 'hikvision':
                    response = hikvision.delete_device(device_id=identifier)
                    if response.get("errorCode") != "0":
                        return Response(
                            {"error": "Device could not be deleted."}, status=status.HTTP_400_BAD_REQUEST)
                case _:
                    raise ValueError("Unsupported brand")

            # Delete camera from database
            camera.delete()

            return Response(
                {"message": "CCTV device deleted successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class GetStreamUrlView(APIView):
    """
    Retrieve live stream or recording playback URLs for CCTV device (One device).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get the stream URL for a CCTV device.
        """
        brand_name = request.query_params.get('brand')
        identifier = request.query_params.get('identifier')

        if not brand_name or not identifier:
            return Response(
                {"error": "Missing brand or identifier"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            match brand_name.lower():
                # ----------------------------
                #  Dahua
                # ----------------------------
                case 'dahua':
                    response = ""
                    business_type = request.query_params.get(
                        'business_type', 'real')
                    if business_type == 'real':
                        response = dahua.get_hls_live_list(
                            device_id=identifier
                        )
                    elif business_type == "playback":

                        begin_time = request.query_params.get('begin_time')
                        end_time = request.query_params.get('end_time')
                        if not begin_time or not end_time:
                            return Response(
                                {"error": "Missing begin_time or end_time for playback"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        response = dahua.get_hls_playback_list(
                            device_id=identifier,
                            begin_time=begin_time,
                            end_time=end_time
                        )

                    else:
                        return Response(
                            {"error": f"Unsupported business_type '{business_type}'"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    if str(response.get("code")) != "200":
                        return Response(
                            {"error": response.get(
                                "message", "Failed to get stream URL")},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Success — standardize output
                    return Response({
                        "device_id": identifier,
                        "stream_url": response.get("url")
                    })

                # ----------------------------
                #  Hikvision
                # ----------------------------
                case 'hikvision':
                    # Call Hikvision api
                    s_type = request.query_params.get('type')
                    start_time: str = request.query_params.get(
                        'start_time', "")
                    stop_time: str = request.query_params.get('stop_time', "")

                    response = hikvision.get_stream(device_id=identifier,
                                                    type_=s_type,
                                                    start_time=start_time,
                                                    stop_time=stop_time,
                                                    expire_time=600
                                                    )
                    if response.get("errorCode") != "0":
                        return Response(
                            {"error": response.get(
                                "message", "Failed to get stream URL")},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    return Response({
                        "device_id": identifier,
                        "stream_url": response.get("stream_url")
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


class GetDeviceStatusView(APIView):
    """
    Retrieve online/offline status for Hikvision CCTV device.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get the device status for a CCTV device.
        """
        brand_name = request.query_params.get('brand')
        identifier = request.query_params.get('identifier')

        if not brand_name:
            return Response(
                {"error": "Missing brand"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not identifier:
            return Response(
                {"error": "Missing identifier"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            match brand_name.lower():
                # ----------------------------
                #  Hikvision
                # ----------------------------
                case 'hikvision':
                    camera = Camera.objects.filter(
                        identifier=identifier,
                        model__brand__name__iexact='hikvision'
                    ).first()
                    if camera is None:
                        return Response(
                            {"error": "Camera not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    name = camera.name if camera else ""
                    data = hikvision.list_devices_with_status(name=name)
                    return Response({"identifier": identifier,
                                    "Status": data[0].get("status")})

                # ----------------------------
                #  Dahua
                # ----------------------------
                case 'dahua':
                    camera = Camera.objects.filter(
                        identifier=identifier,
                        model__brand__name__iexact='hikvision'
                    ).first()
                    if camera is None:
                        return Response(
                            {"error": "Camera not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    data = dahua.get_device_status(device_id=identifier)
                    return Response({"Identifier": identifier,
                                    "Status": data.get("status")})
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
    List all CCTV brands.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CursorPagination
    pagination_class.page_size = 20
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class BrandModelListView(APIView):
    """
    List all CCTV models for a specific brand.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @method_decorator(cache_page(60 * 60 * 24 * 30, key_prefix="brand_models"))
    def get(self, request, brand_name):
        try:
            models = brands[brand_name.lower()].get_camera_models()
            return Response(models)
        except Exception as e:
            return Response({"error": "An error occurred"},
                            status=status.HTTP_400_BAD_REQUEST)


@method_decorator(cache_page(60 * 60 * 24 * 30,
                  key_prefix='cameras_details'), name='dispatch')
class CameraDetailsView(generics.ListAPIView):
    """Get the details of cameras (name, brand, model, location)"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CursorPagination
    pagination_class.page_size = 15
    serializer_class = CameraDetailsSerializer
    queryset = Camera.objects.all().select_related('model__brand')


@method_decorator(cache_page(60 * 60 * 24 * 30,
                             key_prefix='cameras_details_with_live_url'),
                  name='dispatch')
class CameraWithLiveUrlView(generics.ListAPIView):
    """Get the details of cameras with live streaming URL"""
    permission_classes = [IsAuthenticated]
    pagination_class = CursorPagination
    pagination_class.page_size = 12
    serializer_class = CameraWithLiveUrlSerializer
    search_fields = ['name', 'location']
    filter_backends = [filters.SearchFilter]
    queryset = Camera.objects.all().select_related('model__brand')


class CameraLiveUrlView(APIView):
    """Get live streaming URLs for all cameras (GET, no request body).

    Uses a canonical cache key and a stale-while-revalidate strategy:
    - If cached payload exists: return it immediately (200) and enqueue
      a background refresh (the task will no-op if another refresh is running).
    - If no cache exists: enqueue background population and return 202 Accepted.
    """
    permission_classes = [IsAuthenticated]

    CACHE_KEY = "cameras:live_urls:all"
    # Never expire by default; we refresh on Camera changes via signals/tasks.
    CACHE_TTL = None

    def get(self, request):
        # Try to return cached payload immediately
        cached = None
        try:
            cached = cache.get(self.CACHE_KEY)
        except Exception:
            cached = None

        # Enqueue background refresh in any case (task will skip if lock present)
        try:
            populate_live_urls_cache.delay(
                cache_key=self.CACHE_KEY, ttl=self.CACHE_TTL)
        except Exception:
            # Don't fail the request if task enqueueing fails
            pass

        if cached is not None:
            # Always return a list of {location, live_url} objects
            result = []
            if isinstance(cached, dict):
                for cam in cached.values():
                    if isinstance(cam, dict):
                        result.append({
                            'location': cam.get('location'),
                            'live_url': cam.get('live_url')
                        })
            elif isinstance(cached, list):
                for cam in cached:
                    if isinstance(cam, dict):
                        result.append({
                            'location': cam.get('location'),
                            'live_url': cam.get('live_url')
                        })
            # If not a dict or list, just return as-is
            if result:
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(cached, status=status.HTTP_200_OK)

        # No cache yet — tell client we've accepted the request and are populating
        return Response({"message": "Live URLs are being populated. Try again shortly."},
                        status=status.HTTP_202_ACCEPTED)


class CameraRecordingUrlView(generics.ListAPIView):
    """Get recording playback URLs for user's cameras with pagination
    Query params: start_time, end_time, page (optional)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CameraRecordingUrlSerializer
    pagination_class = PageNumberPagination
    pagination_class.page_size = 9

    def get_queryset(self):
        """
        Returns all cameras with their related brand information.
        Optimized with select_related to prevent N+1 queries.
        All users see the same cameras - no user-specific filtering.
        """
        return Camera.objects.all().select_related('model__brand')

    def get_serializer_context(self):
        """Pass time parameters to serializer via context"""
        context = super().get_serializer_context()
        context['start_time'] = self.request.query_params.get('start_time')
        context['end_time'] = self.request.query_params.get('end_time')
        return context

    def list(self, request, *args, **kwargs):
        """Override list to validate time parameters"""
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')

        if not start_time or not end_time:
            return Response(
                {"error": "start_time and end_time query parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Build queryset and paginate (so we don't call external APIs for all cameras at once)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            results = [{'name': item.get('name'), 'recording_url': item.get(
                'recording_url')} for item in serializer.data]
            return self.get_paginated_response(results)

        # Not paginated - serialize full queryset
        serializer = self.get_serializer(queryset, many=True)
        results = [{'name': item.get('name'), 'recording_url': item.get(
            'recording_url')} for item in serializer.data]
        return Response(results, status=status.HTTP_200_OK)


class CameraStatisticsView(APIView):
    """Get camera statistics: total, online, and offline counts

    Returns:
    {
        "total": 10,
        "online": 7,
        "offline": 3
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache
        stats = cache.get('camera_statistics')
        if stats is None:
            # If cache is missing, return default empty stats
            stats = {"total": 0, "online": 0, "offline": 0}
        return Response(stats, status=status.HTTP_200_OK)


class AutomationListView(generics.RetrieveUpdateAPIView):
    """Get and update Automation status."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Automation.objects.all()
    serializer_class = AutomationSerializer

    def get_object(self):
        """Return the first (singleton) automation record"""
        obj, created = Automation.objects.get_or_create(id=Automation.objects.first(
        ).id if Automation.objects.exists() else None, defaults={'active': True})
        return obj
