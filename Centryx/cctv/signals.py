from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Camera
from .tasks import populate_live_urls_cache, update_camera_statistics_cache


# Canonical cache key used for aggregated live URLs
CACHE_KEY = "cameras:live_urls:all"
# Never expire by default; refreshes are triggered via tasks/signals
CACHE_TTL = None



@receiver(post_save, sender=Camera)
@receiver(post_delete, sender=Camera)
def refresh_live_urls_on_camera_change(sender, instance, **kwargs):
    """
    Enqueue background refresh of live-urls cache and statistics cache when Camera changes.
    """
    try:
        populate_live_urls_cache.delay(cache_key=CACHE_KEY, ttl=CACHE_TTL)
        update_camera_statistics_cache.delay()
    except Exception:
        # Don't let signal handlers raise; log elsewhere if needed
        pass
