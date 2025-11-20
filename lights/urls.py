# lights/urls.py
from django.urls import path
from . import views_lifx as lifx_views
from .views_brand import LightBrandListView

urlpatterns = [
    # brand list 
    path("brands/", LightBrandListView.as_view(), name="lights-brand-list"),

    # LIFX cloud
    path("cloud/list/", lifx_views.LifxCloudListView.as_view(), name="lifx-cloud-list"),
    path("register/", lifx_views.LifxRegisterDeviceView.as_view(), name="lights-register"),

    # local DB devices
    path("devices/", lifx_views.SmartLightListView.as_view(), name="lights-device-list"),
    path("devices/<uuid:pk>/control/", lifx_views.SmartLightControlView.as_view(), name="lights-device-control"),
]
