from django.urls import path

from cctv.views import (AddCCTVView, BrandListView, BrandModelListView,
                        DeleteCCTVView, GetStreamUrlView)

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
]
