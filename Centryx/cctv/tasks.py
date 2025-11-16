import time
import logging

from celery import shared_task
from django.core.cache import cache
from django_redis import get_redis_connection

from cctv.models import Camera
from cctv.serializers import CameraLiveUrlSerializer

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def populate_live_urls_cache(self, cache_key: str, ttl: int = 60 * 5, rate_delay: float = 0.21, lock_ttl: int = 60 * 5):
    """
    Populate the cache_key with a mapping of location -> live_url for all cameras.

    - Uses a simple cache.add lock to avoid duplicate refreshers.
    - Throttles external calls using `rate_delay` to respect external API limits.
    - Writes cache only on successful completion.
    """
    lock_key = f"{cache_key}:lock"
    # Try to acquire lock; cache.add returns True if key was set (i.e., lock acquired)
    got_lock = False
    try:
        got_lock = cache.add(lock_key, "1", lock_ttl)
    except Exception as e:
        # If cache backend doesn't support add or fails, log and continue (best-effort)
        logger.exception("Failed to acquire lock via cache.add: %s", e)

    if not got_lock:
        logger.info("populate_live_urls_cache: another worker is already refreshing cache %s", cache_key)
        return {"skipped": True}

    try:
        cameras = Camera.objects.all().select_related("model__brand")

        result = {}
        # Helper: acquire a token from a simple Redis per-second counter.
        # This paces calls across all workers sharing the same Redis instance.
        def _acquire_rate_token(limit_per_second: int = 5, sleep_interval: float = 0.05):
            """Try to acquire a slot allowing up to `limit_per_second` calls per wall-second.

            Uses a per-second Redis key (e.g. rate:camera_api:TIMESTAMP). The counter
            is incremented atomically and expires shortly after to avoid stale keys.
            """
            try:
                redis = get_redis_connection("default")
                while True:
                    now = int(time.time())
                    key = f"rate:camera_api:{now}"
                    current = redis.incr(key)
                    if current == 1:
                        # first increment in this second: set short expiry
                        redis.expire(key, 2)
                    if current <= limit_per_second:
                        return True
                    time.sleep(sleep_interval)
            except Exception:
                # If Redis is unavailable, fall back to a conservative sleep
                time.sleep(rate_delay)
                return True

        # Iterate cameras and call serializer per-object to give us control over pacing
        for camera in cameras:
            try:
                # Wait for a rate slot before calling external clients
                _acquire_rate_token(limit_per_second=max(1, int(1.0 / max(0.0001, rate_delay))))

                serializer = CameraLiveUrlSerializer(camera)
                data = serializer.data
                location = data.get("location") or "Unknown Location"
                result[location] = data.get("live_url")
            except Exception:
                # Don't fail the whole task for a single camera; log and continue
                logger.exception("Error fetching live URL for camera %s", getattr(camera, "identifier", "?"))
                result[getattr(camera, "location", "Unknown Location")] = None
            

        # Write final payload to cache
        try:
            cache.set(cache_key, result, ttl)
        except Exception:
            logger.exception("Failed to set cache for key %s", cache_key)
            return {"cached": False, "count": len(result)}

        return {"cached": True, "count": len(result)}
    finally:
        # release lock
        try:
            cache.delete(lock_key)
        except Exception:
            logger.exception("Failed to release lock %s", lock_key)
