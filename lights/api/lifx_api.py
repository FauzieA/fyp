# lights/api/lifx_api.py
import logging
from typing import Optional, List, Dict, Any
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

LIFX_BASE_URL = "https://api.lifx.com/v1"


class LifxApiError(Exception):
    pass


class LIFXApi:
    """
    Minimal LIFX Cloud v1 client.
    Uses LIFX_API_TOKEN from settings.
    """

    def __init__(self, token: Optional[str] = None, timeout: int | None = None):
        self.token = token or getattr(settings, "LIFX_API_TOKEN", None)
        if not self.token:
            raise LifxApiError("LIFX_API_TOKEN is not configured in settings")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.timeout = timeout or getattr(settings, "REQUESTS_TIMEOUT", 10)

    def list_all_lights(self) -> List[Dict[str, Any]]:
        """Return a list of lights under the account."""
        url = f"{LIFX_BASE_URL}/lights/all"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        logger.info("LIFX list_all_lights -> %s", resp.status_code)
        if resp.status_code == 401:
            raise LifxApiError("Unauthorized - invalid LIFX token")
        resp.raise_for_status()
        return resp.json()

    def get_light(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Return single light details or None if not found."""
        url = f"{LIFX_BASE_URL}/lights/id:{device_id}"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        logger.info("LIFX get_light %s -> %s", device_id, resp.status_code)
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            raise LifxApiError("Unauthorized - invalid LIFX token")
        resp.raise_for_status()
        data = resp.json()
        # API returns list for lights endpoint; pick first item or dict
        if isinstance(data, list) and data:
            return data[0]
        return data

    def set_state(self, device_id: str, **kwargs) -> Dict[str, Any]:
        """
        Control light state. kwargs examples:
          power='on'/'off', brightness=0.5, color='kelvin:3500', duration=1.0
        """
        url = f"{LIFX_BASE_URL}/lights/id:{device_id}/state"
        resp = requests.put(url, headers=self.headers, json=kwargs, timeout=self.timeout)
        logger.info("LIFX set_state %s %s -> %s", device_id, kwargs, resp.status_code)
        if resp.status_code == 401:
            raise LifxApiError("Unauthorized - invalid LIFX token")
        resp.raise_for_status()
        return resp.json()

    # convenience wrappers
    def power_on(self, device_id: str):
        return self.set_state(device_id, power="on")

    def power_off(self, device_id: str):
        return self.set_state(device_id, power="off")

    def set_brightness(self, device_id: str, brightness: float):
        # LIFX brightness is 0.0-1.0
        b = max(0.0, min(1.0, float(brightness)))
        return self.set_state(device_id, brightness=b)
