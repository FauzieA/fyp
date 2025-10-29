from django.urls import path

from integration.views import GetDahuaMotionStatusView

urlpatterns = [
    path(
        'motion-callback/',
        GetDahuaMotionStatusView.as_view(),
        name='motion-callback'),
]
