# lights/urls.py
from django.urls import path

from lights.views.brand import LightBrandListView
from lights.views.lifx import LifxCloudListView, LifxRegisterView
from lights.views.device import (
    SmartLightListView, SmartLightControlView, SmartLightDeleteView,
    SmartLightStatsView, BulkControlView
)

urlpatterns = [
    # brand
    path("brands/", LightBrandListView.as_view(), name="lights-brands"),

    # LIFX cloud
    path("cloud/list/", LifxCloudListView.as_view(), name="lifx-cloud-list"),
    path("register/", LifxRegisterView.as_view(), name="lifx-register"),

    # local SmartLight devices
    path("devices/", SmartLightListView.as_view(), name="lights-device-list"),
    path("devices/<uuid:pk>/control/", SmartLightControlView.as_view(), name="lights-device-control"),
    path("devices/<uuid:pk>/", SmartLightDeleteView.as_view(), name="lights-device-delete"),

    # stats / bulk actions
    path("stats/", SmartLightStatsView.as_view(), name="lights-stats"),
    path("bulk_control/", BulkControlView.as_view(), name="lights-bulk-control"),
]
