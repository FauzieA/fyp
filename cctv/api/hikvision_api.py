import json
import os
import time
from pathlib import Path
from urllib import response

import environ
import requests

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialise environment variables
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / ".env")


class HikvisionAPI:
    """Hikvision Hik-Connect for Teams (HikCentral Connect) API Client"""

    BASE_URL = "https://isgp.hikcentralconnect.com"
    APP_KEY = env("HIKVISION_ACCESS_KEY")
    SECRET_KEY = env("HIKVISION_ACCESS_SECRET")
    DOMAIN_NAME = "cctv"

    def __init__(self):
        self.access_token = None
        self.token_expiry = 0
        self.domain_id = None

    # -----------------------------------------------------------------------
    # Get new access token
    # -----------------------------------------------------------------------
    def _get_access_token(self):
        url = f"{self.BASE_URL}/api/hccgw/platform/v1/token/get"
        payload = {"appKey": self.APP_KEY, "secretKey": self.SECRET_KEY}

        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers)
        data = resp.json()

        if data.get("errorCode") == "0":
            token_data = data["data"]
            self.access_token = token_data["accessToken"]
            self.token_expiry = time.time() + 6.5 * 24 * 60 * 60
        else:
            raise Exception(f"Failed to get token: {data}")

    # ---------------------------------------------------------------------------
    # Ensure token is valid before any request
    # ---------------------------------------------------------------------------
    def _ensure_token(self):
        if not self.access_token or time.time() >= self.token_expiry:
            self._get_access_token()

    # ---------------------------------------------------------------------------
    # Private helper to make authorized POST requests
    # ---------------------------------------------------------------------------
    def _post(self, endpoint: str, body: dict):
        self._ensure_token()
        if not endpoint.startswith("api/"):
            endpoint = f"api/{endpoint.lstrip('/')}"

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Token": self.access_token}

        response = requests.post(url, headers=headers, json=body)
        try:
            data = response.json()
        except Exception:
            raise Exception(f"Invalid JSON response: {response.text}")

        if data.get("errorCode") == "0":
            return data.get("data", {})
        return data

    # ---------------------------------------------------------------------------
    # Private method: ensure domain (area) "centry cctv" exists
    # ---------------------------------------------------------------------------
    def _ensure_domain_exists(self):
        """Check if 'cctv' area exists, create if missing, return areaID."""
        if self.domain_id:
            return self.domain_id

        # list all areas
        try:
            body = {"pageIndex": 1, "pageSize": 100}
            result = self._post("hccgw/resource/v1/areas/get", body)
            area_list = result.get("area", []) or result.get("list", [])
            for area in area_list:
                if area.get("name") == self.DOMAIN_NAME or area.get(
                        "areaName") == self.DOMAIN_NAME:
                    self.domain_id = area.get("areaID") or area.get("id")
                    return self.domain_id
        except Exception:
            pass

        # create the area if not found
        create_body = {"parentAreaID": "-1", "areaName": self.DOMAIN_NAME}
        create_result = self._post("hccgw/resource/v1/areas/add", create_body)
        self.domain_id = (
            create_result.get("areaID")
            or create_result.get("id")
            or create_result.get("areaId")
        )
        return self.domain_id

    # ---------------------------------------------------------------------------
    # Business APIs
    # ---------------------------------------------------------------------------
    def add_device(
        self,
        *,
        name: str,
        ezviz_serial_no: str = None,
        ezviz_verify_code: str = None,
        time_zone_id: str = "26",
        import_area_id: str = "",
        import_enable: str = "1",
        stream_secret_key: str = None,
        device_category: str = "encodingDevice",
    ):
        """
        Add an encoding device (camera/encoder) to Hik-Connect for Teams.

        - device_category: enum (default "encodingDevice")
        - time_zone_id: required string ID (e.g. "26")
        - For Ezviz cameras, include ezviz_serial_no and ezviz_verify_code.

        Returns:
            dict: API response data on success, or custom error if unsupported.
        """

        if not time_zone_id:
            raise ValueError(
                """time_zone_id is required
                (example: '26' corresponds to GMT+8)""")

        # Ensure domain exists
        area_id = self._ensure_domain_exists()
        import_area_id = import_area_id or area_id

        device_info = {
            "name": name,
            "streamSecretKey": stream_secret_key,
        }

        if ezviz_serial_no:
            device_info["ezvizSerialNo"] = ezviz_serial_no
        if ezviz_verify_code:
            device_info["ezvizVerifyCode"] = ezviz_verify_code

        body = {
            "deviceCategory": device_category,
            "deviceInfo": device_info,
            "importToArea": {
                "areaID": import_area_id,
                "enable": import_enable
            },
            "timeZone": {
                "id": str(time_zone_id),
                "applyToDevice": "1"
            },
        }

        # Add the device
        add_device_response = self._post("hccgw/resource/v1/devices/add", body)
        device_id = (
            add_device_response.get("data", {})
            .get("addDeviceResponse", {})
            .get("deviceList", [{}])[0]
            .get("deviceId")
        )
        if not device_id or add_device_response.get("errorCode") != "0":
            # device add failed (invalid info)m
            return {
                "errorCode": "4000",
                "message": "Failed to add device. Check serial number, verify code, and ensure the device is online."}

        # Check motion detection support
        supports_motion = self.check_motion_detection_support(device_id)

        if supports_motion:
            return {
                "errorCode": "0",
                "deviceID": device_id,
                "message": "Device added successfully with motion detection support."}
        else:
            # delete device if motion not supported
            self.delete_device(device_id)
            return {
                "errorCode": "4001",
                "message": "Failed to add device: motion detection not supported."}

    def delete_device(self, device_id: str):
        """
        Delete a device (camera/NVR/DVR) from Hik-Connect for Teams.

        Args:
            device_id (str): The unique deviceID assigned by the platform.

        Returns:
            dict: API response data on success
        Raises:
            Exception: with API payload on failure
        """
        if not device_id:
            raise ValueError("device_id is required to delete a device")

        body = {
            "deviceID": [device_id],
            "deviceCategory": "encodingDevice"
        }

        return self._post("hccgw/resource/v1/devices/delete", body)

    def get_stream(
        self,
        device_id: str,
        type_: str = "1",  # 1 = live, 2 = local playback, 3 = cloud playback
        start_time: str = "",
        stop_time: str = "",
        protocol: int = 2,         # 1=EZOPEN, 2=HLS, 3=RTMP
        quality: int = 2,          # 1=HD, 2=Fluent
        expire_time: int = 600,    # validity in seconds
        code: str = ""
    ):
        """
        Get live or playback stream URL using only device_id.
        Automatically retrieves resourceId and deviceSerial.
        """

        if not device_id:
            raise ValueError("device_id is required")

        # Get resourceId and deviceSerial from device_id
        device_info = self._post("hccgw/resource/v1/areas/cameras/get", {
            "pageIndex": 1,
            "pageSize": 1,
            "filter": {
                "deviceID": f"{device_id}"
            }
        })
        if device_info.get("errorCode") != "0":
            return {
                "errorCode": "4002",
                "message": "Failed to retrieve device info — device not found or invalid device_id.",
                "details": device_info}

        try:
            camera_data = device_info["data"]["camera"][0]
            device_serial = camera_data["device"]["devInfo"].get("serialNo")
            resource_id = camera_data.get("id")
        except Exception as e:
            raise Exception(
                f"Failed to parse device info: {e}, response: {device_info}")

        if not resource_id or not device_serial:
            raise Exception(
                f"Missing resourceId or deviceSerial for {device_id}")

        # Prepare stream request
        body = {
            "resourceId": resource_id,
            "deviceSerial": device_serial,
            "type": type_,
            "protocol": protocol,
            "quality": quality,
            "expireTime": expire_time,
        }

        if code:
            body["code"] = code
        if type_ == "2":  # local or cloud playback
            if not start_time or not stop_time:
                raise ValueError(
                    "start_time and stop_time are required for playback streams")

            for stream_type in ["2", "3"]:  # 2 = local, 3 = cloud
                body["type"] = stream_type
                body["startTime"] = start_time
                body["stopTime"] = stop_time

                response = self._post("hccgw/video/v1/live/address/get", body)

                if response.get("errorCode") == "0" and response.get(
                        "data", {}).get("url"):
                    return {
                        "stream_url": response["data"]["url"],
                        "errorCode": 0}

            # If neither works
            return {
                "stream_url": None,
                "errorCode": 4002,
                "message": "Failed to get playback stream URL (local and cloud)",
            }

        else:
            # Get live stream
            body['type'] = "1"
            response = self._post("hccgw/video/v1/live/address/get", body)

            if response.get(
                    "errorCode") != "0" or "data" not in response or "url" not in response["data"]:
                return {
                    "stream_url": None,
                    "errorCode": 4001,
                    "message": "Failed to retrieve live stream URL"
                }

            stream_url = response["data"]["url"]
            return {"stream_url": stream_url, "errorCode": 0}

    def list_devices_with_status(
            self,
            page_index: int = 1,
            name: str = "",
            page_size: int = 50):
        """List all devices with their online/offline status."""
        body = {
            "pageIndex": page_index,
            "pageSize": page_size,
            "filter": {"matchKey": name}
        }
        data = self._post("hccgw/resource/v1/devices/get", body)

        devices = data.get("data", {}).get("deviceList", [])
        return [
            {
                "deviceName": d.get("name"),
                "status": "Online" if d.get("online") == "1" else "Offline"
            }
            for d in devices
        ]

    # ---------------------------------------------------------------------------
    # Motion Detection Alarm APIs
    # ---------------------------------------------------------------------------
    def check_motion_detection_support(self, device_id: str):
        """
        Check if a device's camera supports motion detection.
        Automatically retrieves the cameraID from the given device_id.
        Returns True or False (same as original).
        """

        if not device_id:
            raise ValueError("device_id is required")

        # Check motion detection support for that camera
        body = {
            "pageIndex": 1,
            "pageSize": 1,
            "filter": {"deviceID": device_id}
        }

        data = self._post("hccgw/resource/v1/areas/cameras/get", body)
        cameras = data.get("data", {}).get("camera", [])

        if not cameras:
            return False

        abilities = cameras[0].get("abilitySet", "")
        return "2002" in abilities.split(",")

    def subscribe_motion_detection(self):
        """Subscribe to all motion-detection alarms (eventType 10002)."""
        body = {
            "subscribeType": 1,
            "subscribeMode": 1,
            "eventType": [10002]  # 10002 = Motion Detection
        }
        return self._post("hccgw/alarm/v1/mq/subscribe", body)

    def get_motion_events(self, max_per_time: int = 100):
        """Retrieve pending motion detection alarms."""
        body = {"maxNumberPerTime": max_per_time}
        return self._post("hccgw/alarm/v1/mq/messages", body)

    def acknowledge_motion_events(self, batch_id: str):
        """Acknowledge that messages were received so they won’t repeat."""
        if not batch_id:
            return {"error": "No batch ID provided."}
        body = {"batchId": batch_id}
        return self._post("hccgw/alarm/v1/mq/messages/complete", body)

    def unsubscribe_motion_detection(self):
        """Unsubscribe from all alarm message queues (including motion)."""
        body = {
            "subscribeType": 0,
            "subscribeMode": 1,
            "eventType": [10002]  # 10002 = Motion Detection
        }
        return self._post("hccgw/alarm/v1/mq/subscribe", body)
