from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
import traceback


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, ObjectDoesNotExist):
        return Response(
            {"detail": "Refresh token invalid or expired."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Print the full error traceback for debugging
    print(f"\n{'=' * 80}")
    print(f"EXCEPTION: {type(exc).__name__}: {exc}")
    print(f"{'=' * 80}")
    traceback.print_exc()
    print(f"{'=' * 80}\n")

    return Response({"detail": "Internal server error."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)
