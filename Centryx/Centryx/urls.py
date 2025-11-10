"""
URL configuration for Centryx project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from dj_rest_auth.jwt_auth import get_refresh_view
from dj_rest_auth.views import (LogoutView, PasswordChangeView,
                                PasswordResetConfirmView, PasswordResetView,
                                UserDetailsView)
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)
from integration.auth_views import MFALoginView
from rest_framework_simplejwt.views import TokenVerifyView

urlpatterns = [
    path("admin/", admin.site.urls),

    # OpenAPI schema and docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/",
         SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/",
         SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Custom MFA-protected login endpoint (MUST come before other auth
    # endpoints)
    path("auth/login/", MFALoginView.as_view(), name="rest_login"),

    # JWT token endpoints (refresh and verify)
    path(
        "auth/token/refresh/",
        get_refresh_view().as_view(),
        name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # Other dj-rest-auth endpoints (logout, user details, password change/reset)
    # NOTE: Login is explicitly excluded to prevent bypassing MFA
    path("auth/logout/", LogoutView.as_view(), name="rest_logout"),
    path("auth/user/", UserDetailsView.as_view(), name="rest_user_details"),
    path("auth/password/change/",
         PasswordChangeView.as_view(),
         name="rest_password_change"),
    path(
        "auth/password/reset/",
        PasswordResetView.as_view(),
        name="rest_password_reset"),
    path("auth/password/reset/confirm/",
         PasswordResetConfirmView.as_view(),
         name="rest_password_reset_confirm"),

    # Registration endpoints
    path("auth/registration/", include("dj_rest_auth.registration.urls")),

    # MFA/2FA endpoints (django-trench)
    path('auth/mfa/', include('trench.urls')),

    # Password reset confirm URL (required by dj-rest-auth for email
    # generation)
    path("password-reset-confirm/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),

    # App endpoints
    path("cctv/", include("cctv.urls")),
    path("integration/", include("integration.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
