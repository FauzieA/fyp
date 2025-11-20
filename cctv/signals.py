from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Brand, Camera, CCTVModel


def delete_cache_pattern(pattern):
    """Delete cache keys matching a pattern"""
    try:
        keys = cache.keys(pattern)
        if keys:
            cache.delete_many(keys)
    except AttributeError:
        # Fallback for backends that don't support keys()
        # Need to track specific cache keys or use cache versioning
        pass


@receiver(post_save, sender=Camera)
@receiver(post_delete, sender=Camera)
def invalidate_camera_cache(sender, instance, **kwargs):
    """Invalidate cache with 'camera_' prefix when Camera model changes"""
    delete_cache_pattern('*cameras_live_urls*')
    delete_cache_pattern('*cameras_details*')
    delete_cache_pattern('*cameras_details_with_live_url*')
