from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, ObjectDoesNotExist):
        return Response(
            {"detail": "Refresh token invalid or expired."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return Response({"detail": "Internal server error."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)
