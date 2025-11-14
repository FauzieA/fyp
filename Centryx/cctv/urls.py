from django.urls import path

from cctv.views import (AddCCTVView, BrandListView, BrandModelListView,
                        CameraDetailsView, CameraLiveUrlView,
                        CameraRecordingUrlView, CameraStatisticsView,
                        CameraWithLiveUrlView, DeleteCCTVView,
                        GetDeviceStatusView, GetStreamUrlView)

urlpatterns = [
    path(
        'add_device/',
        AddCCTVView.as_view(),
        name='add_cctv_device'),
    path(
        'delete_device/',
        DeleteCCTVView.as_view(),
        name='delete_cctv_device'),
    path(
        'get_stream_url/',
        GetStreamUrlView.as_view(),
        name='get_stream_url'),
    path(
        'get_brands/',
        BrandListView.as_view(),
        name='get_brands'),
    path(
        'get_models/<str:brand_name>/',
        BrandModelListView.as_view(),
        name='get_cctv_models'),
    path('get_device_status/',
         GetDeviceStatusView.as_view(),
         name='get_device_status'),
    path(
        'cameras/',
        CameraDetailsView.as_view(),
        name='camera_details'),
    path(
        'cameras/monitoring/',
        CameraWithLiveUrlView.as_view(),
        name='camera_live_urls'),
    path(
        'cameras/live_urls/',
        CameraLiveUrlView.as_view(),
        name='camera_live_urls'),
    path(
        'cameras/recording_urls/',
        CameraRecordingUrlView.as_view(),
        name='camera_recording_urls'),
    path(
        'cameras/statistics/',
        CameraStatisticsView.as_view(),
        name='camera_statistics'),
]
