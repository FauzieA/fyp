from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    """Nested profile serializer that returns absolute image URLs when possible."""

    profile_image = serializers.SerializerMethodField()

    def get_profile_image(self, obj):
        request = self.context.get("request")
        if obj.profile_image:
            url = obj.profile_image.url
            return request.build_absolute_uri(url) if request else url
        return None

    class Meta:
        model = Profile
        fields = ("phone_number", "profile_image")


class CustomUserSerializer(UserDetailsSerializer):
    """Extends dj-rest-auth's UserDetailsSerializer to include flattened Profile fields.

    Supports reading and writing phone_number and profile_image.
    """

    phone_number = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)

    class Meta(UserDetailsSerializer.Meta):
        model = User
        fields = UserDetailsSerializer.Meta.fields + \
            ("first_name", "last_name", "phone_number",
             "profile_image", "is_active", "is_superuser")
        read_only_fields = UserDetailsSerializer.Meta.read_only_fields

    def to_representation(self, instance):
        """Custom serialization: return absolute URL for profile_image."""
        ret = super().to_representation(instance)

        # Replace profile_image with absolute URL or null
        request = self.context.get("request")
        if hasattr(instance, 'profile') and instance.profile.profile_image:
            url = instance.profile.profile_image.url
            ret['profile_image'] = request.build_absolute_uri(
                url) if request else url
        else:
            ret['profile_image'] = None

        # Get phone_number from profile
        if hasattr(instance, 'profile'):
            ret['phone_number'] = instance.profile.phone_number
        else:
            ret['phone_number'] = None

        return ret

    def update(self, instance, validated_data):
        """Custom update: handle profile fields separately."""
        phone_number = validated_data.pop('phone_number', None)
        profile_image = validated_data.pop('profile_image', None)

        # Update user fields
        instance = super().update(instance, validated_data)

        # Update or create profile
        profile, _ = Profile.objects.get_or_create(user=instance)

        if phone_number is not None:
            profile.phone_number = phone_number

        if profile_image is not None:
            profile.profile_image = profile_image

        profile.save()

        return instance


class CustomRegisterSerializer(RegisterSerializer):
    """Custom registration serializer that handles profile fields during signup.

    Accepts phone_number and profile_image during user registration.
    Enforces email uniqueness.
    """

    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)

    def validate_email(self, email):
        """Ensure email is unique."""
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user is already registered with this e-mail address."
            )
        return email

    def get_cleaned_data(self):
        """Include custom fields in cleaned data."""
        data = super().get_cleaned_data()
        data['first_name'] = self.validated_data.get('first_name', '')
        data['last_name'] = self.validated_data.get('last_name', '')
        data['phone_number'] = self.validated_data.get('phone_number', '')
        data['profile_image'] = self.validated_data.get('profile_image', None)
        return data

    def save(self, request):
        """Create user and associated profile with custom fields."""
        user = super().save(request)

        # Get profile fields from cleaned data
        phone_number = self.validated_data.get('phone_number', '')
        profile_image = self.validated_data.get('profile_image', None)
        first_name = self.validated_data.get('first_name', '')
        last_name = self.validated_data.get('last_name', '')

        # Update user's name fields
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save()

        # Create or update profile
        profile, _ = Profile.objects.get_or_create(user=user)
        if phone_number:
            profile.phone_number = phone_number
        if profile_image:
            profile.profile_image = profile_image
        profile.save()

        return user
