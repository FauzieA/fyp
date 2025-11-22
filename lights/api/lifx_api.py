# lights/api/lifx_api.py
import logging
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
            resp.raise_for_status()
        except requests.HTTPError:
            logger.error("LIFX API error %s %s", resp.status_code, resp.text)
            raise LifxApiError(f"LIFX API returned {resp.status_code}: {resp.text}")
        except requests.RequestException as e:
            logger.exception("LIFX request failure")
            raise LifxApiError(f"Network error during LIFX request: {e}")

        try:
            return resp.json()
        except ValueError:
            return resp.text

    # ---  wrappers ---
    def list_all_lights(self):
        return self._request("GET", "/lights/all")

    def get_light(self, device_id: str):
        return self._request("GET", f"/lights/id:{device_id}")

    def set_state(self, device_id: str, **kwargs):
        """
        Generic state setter for power, brightness, color, duration, etc.
        Calls: PUT /v1/lights/id:{device_id}/state
        """
        return self._request("PUT", f"/lights/id:{device_id}/state", json_body=kwargs)
