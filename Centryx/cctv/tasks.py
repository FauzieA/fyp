
import time
import logging
from typing import Optional
from celery import shared_task, group
from django.core.cache import cache
from django_redis import get_redis_connection
from django.conf import settings
from integration.services.cctv_services import get_dahua_client, get_hikvision_client
from cctv.models import Brand, Camera
from cctv.serializers import CameraLiveUrlSerializer

logger = logging.getLogger(__name__)

# Helper to get all brand clients dynamically
def get_all_brand_clients():
    return {
        'dahua': get_dahua_client(),
        'hikvision': get_hikvision_client(),
    }


# Subtask for brand status check
@shared_task
def get_brand_status(brand_name):
    brand_clients = get_all_brand_clients()
    client = brand_clients.get(brand_name)
    total = online = offline = 0
    try:
        if brand_name == 'dahua':
            devices = client.get_all_device_statuses()
            print(devices)
            logger.info(f"Dahua devices found: {devices}")
            total = len(devices)
            for device in devices:
                if device.get('deviceStatus', '').lower() == 'online':
                    online += 1
                else:
                    offline += 1
        elif brand_name == 'hikvision':
            devices = client.list_devices_with_status(page_size=500)
            logger.info(f"Hikvision devices found: {devices}")
            total = len(devices)
            for device in devices:
                if device.get('status', '').lower() == 'online':
                    online += 1
                else:
                    offline += 1
        # Add more brand logic here as needed
    except Exception as e:
        logger.exception(f"Error updating statistics for brand {brand_name}: {e}")
    return {'brand': brand_name, 'total': total, 'online': online, 'offline': offline}

# Main periodic task

from celery import chord

@shared_task
def update_camera_statistics_cache():
    brand_names = list(get_all_brand_clients().keys())
    header = [get_brand_status.s(name) for name in brand_names]
    chord(header)(aggregate_camera_statistics_cache.s())


# Callback for chord to aggregate results and update cache
@shared_task
def aggregate_camera_statistics_cache(results):
    total = sum(r['total'] for r in results)
    online = sum(r['online'] for r in results)
    offline = sum(r['offline'] for r in results)
    stats = {"total": total, "online": online, "offline": offline}
    logger.info(f"Setting camera_statistics cache: {stats}")
    cache.set('camera_statistics', stats, timeout=300)
    return stats



@shared_task(bind=True)
def populate_live_urls_cache(self, cache_key: str, ttl: Optional[int] = None, rate_delay: float = 0.21, lock_ttl: int = 60 * 5):
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

        # Build aggregate keyed by camera id to ensure uniqueness even if locations repeat.
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
                cid = str(camera.id)
                result[cid] = {"camera_id": cid, "location": location, "live_url": data.get("live_url")}
            except Exception:
                # Don't fail the whole task for a single camera; log and continue
                logger.exception("Error fetching live URL for camera %s", getattr(camera, "identifier", "?"))
                result[getattr(camera, "location", "Unknown Location")] = None
            

        # Write final payload to cache (ttl=None => no expiry)
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
