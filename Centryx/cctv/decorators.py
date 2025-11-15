import hashlib
import json
from functools import wraps

from django.core.cache import cache
from rest_framework.response import Response


def cache_post(timeout=60 * 60 * 24, key_prefix="post_cache_"):
    """Cache POST requests by hashing request body"""
    def decorator(func):
        @wraps(func)
        def wrapped(view, request, *args, **kwargs):
            try:
                # Serialize the body and create a hash
                body_bytes = json.dumps(
                    request.data, sort_keys=True).encode('utf-8')
                key_hash = hashlib.sha256(body_bytes).hexdigest()
                cache_key = f"{key_prefix}{key_hash}"

                # Try to get cached response
                cached_response = cache.get(cache_key)
                if cached_response is not None:
                    return Response(cached_response)

                # Call the original view
                response = func(view, request, *args, **kwargs)

                # Store response in cache if successful (2xx status codes)
                if 200 <= response.status_code < 300:
                    cache.set(cache_key, response.data, timeout=timeout)

                return response
            except (TypeError, ValueError):
                # If request.data is not JSON serializable, skip caching
                return func(view, request, *args, **kwargs)
        return wrapped
    return decorator
