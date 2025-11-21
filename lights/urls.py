from django.urls import path

from lights.views.brand import LightBrandListView
from lights.views.lifx import LifxCloudListView, LifxRegisterDeviceView
from lights.views.device import SmartLightListView, SmartLightControlView

urlpatterns = [
    # brand
    path("brands/", LightBrandListView.as_view(), name="lights-brands"),

    # LIFX cloud
    path("cloud/list/", LifxCloudListView.as_view(), name="lifx-cloud-list"),
    path("register/", LifxRegisterDeviceView.as_view(), name="lifx-register"),

    # local SmartLight devices
    path("devices/", SmartLightListView.as_view(), name="lights-device-list"),
    path("devices/<uuid:pk>/control/", SmartLightControlView.as_view(), name="lights-device-control"),
]
