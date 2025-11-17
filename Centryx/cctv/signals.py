from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Camera
import logging
from .tasks import populate_live_urls_cache, update_camera_statistics_cache

# Helper to build cache key pattern for stream URLs

def invalidate_stream_url_cache():
    # Remove all keys starting with 'stream_url:'
    # This works for locmem and Redis cache backends that support
    # .delete_pattern()
    try:
        # For Redis backend
        cache.delete_pattern('stream_url:*')
    except AttributeError:
        # For locmem or other backends, fallback to manual deletion
        # This is not efficient for large caches
        if hasattr(cache, 'keys'):
            for key in cache.keys('*'):
                if key.startswith('stream_url:'):
                    cache.delete(key)


@receiver(post_save, sender=Camera)
def camera_created_or_updated(sender, instance, **kwargs):
    invalidate_stream_url_cache()


@receiver(post_delete, sender=Camera)
def camera_deleted(sender, instance, **kwargs):
    invalidate_stream_url_cache()


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
    logger = logging.getLogger(__name__)
    try:
        if kwargs.get('created', None) is not None:
            logger.info(
                f"Camera save detected (created={
                    kwargs['created']}): {instance}. Triggering cache update tasks.")
        else:
            logger.info(
                f"Camera delete detected: {instance}. Triggering cache update tasks.")
        populate_live_urls_cache.delay(cache_key=CACHE_KEY, ttl=CACHE_TTL)
        logger.info("populate_live_urls_cache task queued.")
        update_camera_statistics_cache.delay()
        logger.info("update_camera_statistics_cache task queued.")
    except Exception as e:
        logger.error(f"Signal handler error: {e}")
