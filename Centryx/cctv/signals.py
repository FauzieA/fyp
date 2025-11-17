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
    import logging
    logger = logging.getLogger(__name__)
    try:
        if kwargs.get('created', None) is not None:
            logger.info(f"Camera save detected (created={kwargs['created']}): {instance}. Triggering cache update tasks.")
        else:
            logger.info(f"Camera delete detected: {instance}. Triggering cache update tasks.")
        populate_live_urls_cache.delay(cache_key=CACHE_KEY, ttl=CACHE_TTL)
        logger.info("populate_live_urls_cache task queued.")
        update_camera_statistics_cache.delay()
        logger.info("update_camera_statistics_cache task queued.")
    except Exception as e:
        logger.error(f"Signal handler error: {e}")
