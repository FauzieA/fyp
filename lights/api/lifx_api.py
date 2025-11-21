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
    def __init__(self):
        self.base = LIFX_BASE_URL
        self.token = getattr(settings, "LIFX_API_TOKEN", None)
        if not self.token:
            raise LifxApiError("LIFX_API_TOKEN is not configured in settings (set in .env)")

    def _request(self, method: str, path: str, params: dict = None, json_body: dict = None):
        url = f"{self.base}{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=10)
        except requests.RequestException as e:
            logger.exception("LIFX request failure")
            raise LifxApiError(f"Network error during LIFX request: {e}")
        if resp.status_code == 401:
            raise LifxApiError("LIFX authentication failed (401) - check token")
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            logger.error("LIFX API error %s %s", resp.status_code, resp.text)
            raise LifxApiError(f"LIFX API returned {resp.status_code}: {resp.text}")
        try:
            return resp.json()
        except ValueError:
            return resp.text

    #  wrappers
    def list_all_lights(self):
        return self._request("GET", "/lights/all")

    def get_light(self, device_id: str):
        return self._request("GET", f"/lights/id:{device_id}")
    
    def power_on(self, device_id: str):
        return self.set_state(device_id, power="on")

    def power_off(self, device_id: str):
        return self.set_state(device_id, power="off")

    def set_brightness(self, device_id: str, brightness: float):
        # LIFX brightness is 0.0-1.0
        b = max(0.0, min(1.0, float(brightness)))
        return self.set_state(device_id, brightness=b)
