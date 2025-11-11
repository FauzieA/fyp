from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver


class Profile(models.Model):
    """Simple user profile attached to the project's User model.

    This keeps the default AUTH_USER_MODEL unchanged and stores extra
    per-user information (phone number and profile image) here.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_image = models.ImageField(
        upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        # Use username if available, fallback to pk
        uname = getattr(self.user, 'username', None)
        return f"{uname or self.user.pk} Profile"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Ensure a Profile exists for each user.

    - On create: create a new Profile.
    - On save: ensure a Profile exists (get_or_create) so existing users
      also get a profile if they don't already have one.
    """
    if created:
        Profile.objects.create(user=instance)
    else:
        # Ensure profile exists for users created before this code
        Profile.objects.get_or_create(user=instance)


# Clean up profile images from storage when replaced or when the Profile
# is deleted.
@receiver(pre_save, sender=Profile)
def auto_delete_old_profile_image(sender, instance, **kwargs):
    """Delete old profile image file from storage when a new one is uploaded.

    This avoids leaving orphaned files on disk when users update their
    profile image. It only runs when updating an existing Profile (instance.pk
    present) and when the image field actually changes.
    """
    # Nothing to do for new objects
    if not instance.pk:
        return

    try:
        old = Profile.objects.get(pk=instance.pk)
    except Profile.DoesNotExist:
        return

    old_file = old.profile_image
    new_file = instance.profile_image
    # If there was an old file and it's different from the new one, delete it
    if old_file and old_file != new_file:
        try:
            if old_file.storage.exists(old_file.name):
                old_file.delete(save=False)
        except Exception:
            # Fail silently; don't block the save if deletion fails
            pass


@receiver(post_delete, sender=Profile)
def auto_delete_profile_image_on_delete(sender, instance, **kwargs):
    """Delete profile image file from storage when Profile object is deleted."""
    file = instance.profile_image
    if file:
        try:
            if file.storage.exists(file.name):
                file.delete(save=False)
        except Exception:
            # Fail silently; deletion errors shouldn't prevent DB deletes
            pass
