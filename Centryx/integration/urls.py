from django.urls import path

from integration.auth_views import DeleteUserView
from integration.views import GetDahuaMotionStatusView, ListUsersView

urlpatterns = [
    path(
        'motion-callback/',
        GetDahuaMotionStatusView.as_view(),
        name='motion-callback'),
    path(
        'users/',
        ListUsersView.as_view(),
        name='list-users'),
    path(
        'users/<int:user_id>/',
        DeleteUserView.as_view(),
        name='delete-user'),
]
