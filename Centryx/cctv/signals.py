from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Camera
from .tasks import populate_live_urls_cache


# Canonical cache key used for aggregated live URLs
CACHE_KEY = "cameras:live_urls:all"
CACHE_TTL = 60 * 5  # 5 minutes


@receiver(post_save, sender=Camera)
@receiver(post_delete, sender=Camera)
def refresh_live_urls_on_camera_change(sender, instance, **kwargs):
    """Enqueue background refresh of live-urls cache when Camera changes.

    We intentionally DO NOT delete the existing cache here (stale-while-revalidate).
    """
    try:
        populate_live_urls_cache.delay(cache_key=CACHE_KEY, ttl=CACHE_TTL)
    except Exception:
        # Don't let signal handlers raise; log elsewhere if needed
        pass
