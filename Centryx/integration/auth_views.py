from dj_rest_auth.views import LoginView
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from trench.utils import get_mfa_model, user_token_generator

User = get_user_model()


class MFALoginView(LoginView):
    """
    Custom login view that handles MFA/2FA flow.

    If user has MFA enabled:
        - Returns ephemeral_token instead of access/refresh tokens
        - User must then verify with TOTP code

    If user doesn't have MFA:
        - Returns normal access/refresh tokens
    """

    def post(self, request, *args, **kwargs):
        # Validate credentials using dj-rest-auth serializer
        self.request = request
        self.serializer = self.get_serializer(data=self.request.data)

        if not self.serializer.is_valid():
            return Response(
                self.serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get username/email and password from validated data
        username = self.serializer.validated_data.get(
            'username') or self.serializer.validated_data.get('email')
        password = self.serializer.validated_data.get('password')

        # Authenticate user
        user = authenticate(
            request=request,
            username=username,
            password=password)

        if user is None:
            return Response(
                {'non_field_errors': [
                    'Unable to log in with provided credentials.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user has active MFA methods
        MFAMethod = get_mfa_model()
        active_methods = MFAMethod.objects.filter(
            user=user,
            is_active=True,
            is_primary=True
        )

        if active_methods.exists():
            # User has MFA enabled - return ephemeral token
            ephemeral_token = user_token_generator.make_token(user)

            return Response({
                'ephemeral_token': ephemeral_token,
                'method': 'app',  # The MFA method to use
            }, status=status.HTTP_200_OK)

        else:
            # No MFA enabled - proceed with normal login
            # Manually set user for dj-rest-auth login flow
            self.user = user
            return super().post(request, *args, **kwargs)


class DeleteUserView(APIView):
    """
    Delete a user by ID. Admin only.
    Prevents admins from deleting themselves.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, user_id):
        # Get the user or return 404
        user = get_object_or_404(User, id=user_id)

        # Prevent self-deletion
        if user.id == request.user.id:
            return Response(
                {"error": "Cannot delete yourself"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delete the user
        user.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
