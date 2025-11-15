import re

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from integration.services.cctv_services import (get_dahua_client,
                                                get_hikvision_client)
from rest_framework import generics, status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cctv.decorators import cache_post
from cctv.models import Automation, Brand, Camera
from cctv.serializers import (AutomationSerializer, BrandSerializer,
                              CameraCreateSerializer, CameraDetailsSerializer,
                              CameraWithLiveUrlSerializer)

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
                    if not identifier:
                        return Response(
                            {"error": "Missing identifier"},
                            status=status.HTTP_400_BAD_REQUEST
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
    queryset = Camera.objects.all().select_related('model__brand')


class CameraLiveUrlView(APIView):
    """Get live streaming URLs for specified devices (Multiple devices)
    """
    permission_classes = [IsAuthenticated]

    @cache_post(timeout=60 * 60 * 24 * 30, key_prefix="cameras_live_urls")
    def post(self, request):
        devices = request.data.get('devices', [])

        if not devices:
            return Response(
                {"error": "No devices provided. Send 'devices' array with brand, identifier, and location."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = {}

        for device in devices:
            brand_name = device.get('brand', '').lower()
            identifier = device.get('identifier')
            location = device.get('location', 'Unknown Location')

            if not brand_name or not identifier:
                result[location] = None
                continue

            try:
                # ----------------------------
                #  Dahua
                # ----------------------------
                if brand_name == 'dahua':
                    response = brands['dahua'].get_hls_live_list(
                        device_id=identifier)
                    if str(response.get("code")) == "200":
                        result[location] = response.get("url")
                    else:
                        result[location] = None

                # ----------------------------
                #  Hikvision
                # ----------------------------
                elif brand_name == 'hikvision':
                    response = brands['hikvision'].get_stream(
                        device_id=identifier,
                        type_='1',
                        expire_time=600
                    )
                    if response.get("errorCode") == "0":
                        result[location] = response.get("stream_url")
                    else:
                        result[location] = None
                else:
                    result[location] = None

            except Exception as e:
                result[location] = None

        return Response(result, status=status.HTTP_200_OK)


class CameraRecordingUrlView(APIView):
    """Get recording playback URLs for specified devices (Multiple devices)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        devices = request.data.get('devices', [])

        if not devices:
            return Response(
                {"error": "No devices provided. Send 'devices' array with brand, identifier, location, and time range."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = {}

        for device in devices:
            brand_name = device.get('brand', '').lower()
            identifier = device.get('identifier')
            location = device.get('location', 'Unknown Location')

            if not brand_name or not identifier:
                result[location] = None
                continue

            try:
                # ----------------------------
                #  Dahua
                # ----------------------------
                if brand_name == 'dahua':
                    begin_time = device.get('begin_time')
                    end_time = device.get('end_time')

                    if not begin_time or not end_time:
                        result[location] = None
                        continue

                    # Convert ISO format to Dahua format if needed
                    # ISO: 2025-11-12T10:00:00 -> Dahua: 2025-11-12 10:00:00
                    begin_time = begin_time.replace('T', ' ')
                    end_time = end_time.replace('T', ' ')

                    response = brands['dahua'].get_hls_playback_list(
                        device_id=identifier,
                        begin_time=begin_time,
                        end_time=end_time
                    )
                    if str(response.get("code")) == "200":
                        result[location] = response.get("url")
                    else:
                        result[location] = None

                # ----------------------------
                #  Hikvision
                # ----------------------------
                elif brand_name == 'hikvision':
                    start_time = device.get('start_time')
                    stop_time = device.get('stop_time')

                    if not start_time or not stop_time:
                        result[location] = None
                        continue

                    response = brands['hikvision'].get_stream(
                        device_id=identifier,
                        type_='2',
                        start_time=start_time,
                        stop_time=stop_time,
                        expire_time=600
                    )
                    if response.get("errorCode") == "0":
                        result[location] = response.get("stream_url")
                    else:
                        result[location] = None

                else:
                    result[location] = None

            except Exception as e:
                result[location] = None

        return Response(result, status=status.HTTP_200_OK)


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
        # Get all cameras with their brand information
        cameras = Camera.objects.select_related('model__brand').all()

        total_cameras = cameras.count()
        online_count = 0
        offline_count = 0

        for camera in cameras:
            brand_name = camera.model.brand.name.lower()
            identifier = camera.identifier

            try:
                # ----------------------------
                #  Dahua
                # ----------------------------
                if brand_name == 'dahua':
                    response = brands['dahua'].get_device_status(
                        device_id=identifier)
                    if response.get("code") == "200":
                        status_value = response.get("status", "").lower()
                        if status_value == "online":
                            online_count += 1
                        else:
                            offline_count += 1
                    else:
                        offline_count += 1

                # ----------------------------
                #  Hikvision
                # ----------------------------
                elif brand_name == 'hikvision':
                    # Hikvision returns list of all devices with status
                    response = brands['hikvision'].list_devices_with_status()

                    # Find this specific device in the response
                    device_found = False
                    if isinstance(response, list):
                        for device in response:
                            if device.get("deviceName") == camera.name:
                                device_found = True
                                if device.get("status") == "Online":
                                    online_count += 1
                                else:
                                    offline_count += 1
                                break

                    if not device_found:
                        offline_count += 1

                else:
                    # Unsupported brand, count as offline
                    offline_count += 1

            except Exception as e:
                offline_count += 1
                pass

        return Response({
            "total": total_cameras,
            "online": online_count,
            "offline": offline_count
        }, status=status.HTTP_200_OK)


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
