import base64
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path

import environ
import requests

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialise environment variables
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / ".env")


class DahuaAPI:
    """DahuaAPI class to interact with DoLynk Developer APIs."""

    BASE_URL = "https://open-api-sg.dolynkcloud.com/open-api"
    ACCESS_KEY = env("DAHUA_ACCESS_KEY")
    SECRET_ACCESS_KEY = env("DAHUA_SECRET_ACCESS_KEY")
    PRODUCT_ID = env("DAHUA_PRODUCT_ID")
    VERSION = env("DAHUA_VERSION", default="v1")

    def __init__(self):
        self.app_access_token = None
        self.token_expiry = 0

    # -------------------------------------------------------------------------------
    # Helper methods for request signing and data preprocessing:
    # - _delete_whitespace: removes all whitespace from a string
    # - _open_token_sign: generates HMAC-SHA512 signature for access token requests
    # - _open_sign: generates HMAC-SHA512 signature for business API requests,
    #   including optional JSON body preprocessing and hashing
    # _get_app_access_token: obtains and refreshes the AppAccessToken
    # _post: generic method to make signed POST requests to the DoLynk API
    # -------------------------------------------------------------------------------

    @staticmethod
    def _delete_whitespace(s: str):
        return "".join(c for c in s if not c.isspace())

    def _open_token_sign(self, method, timestamp, nonce):
        str_to_sign = f"{self.ACCESS_KEY}{timestamp}{nonce}{method}"
        sign_result = hmac.new(
            self.SECRET_ACCESS_KEY.encode("utf-8"),
            str_to_sign.encode("utf-8"),
            hashlib.sha512
        ).hexdigest().upper()
        return sign_result

    def _open_sign(self, method, timestamp, nonce, app_access_token, body):
        body_str = json.dumps(body) if body else ""
        clean_body = self._delete_whitespace(body_str)

        # SHA512 hash of cleaned body
        body_hash = hashlib.sha512(clean_body.encode(
            "utf-8")).hexdigest() if body_str else ""

        # stringToSign includes "POST\n" + body hash
        string_to_sign = f"{method}\n{body_hash}"

        # Full string to sign
        str_auth = f"{
            self.ACCESS_KEY}{app_access_token}{timestamp}{nonce}{string_to_sign}"

        # HMAC-SHA512 signature
        sign_result = hmac.new(
            self.SECRET_ACCESS_KEY.encode("utf-8"),
            str_auth.encode("utf-8"),
            hashlib.sha512
        ).hexdigest().upper()

        return sign_result

    def _get_app_access_token(self):
        """Get product app access token from DoLynk API.
        """
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        method = "POST"
        sign = self._open_token_sign(method, timestamp, nonce)

        headers = {
            "Content-Type": "application/json",
            "AccessKey": self.ACCESS_KEY,
            "Timestamp": timestamp,
            "Nonce": nonce,
            "Sign": sign,
            "X-TraceId-Header": str(uuid.uuid4()),
            "ProductId": self.PRODUCT_ID,
            "Version": self.VERSION,
        }

        url = f"{self.BASE_URL}/api-base/auth/getAppAccessToken"
        resp = requests.post(url, headers=headers, json={}).json()

        if resp.get("code") == "200":
            self.app_access_token = resp["data"]["appAccessToken"]
            self.token_expiry = time.time() + 6.5 * 24 * 60 * 60
        else:
            raise Exception(f"Failed to get AppAccessToken: {resp}")

    # Ensure token validity before request

    def _ensure_token(self):
        if not self.app_access_token or time.time() >= self.token_expiry:
            # Refreshing AppAccessToken...
            self._get_app_access_token()

    def _post(self, endpoint, body):
        self._ensure_token()
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        method = "POST"

        sign = self._open_sign(
            method,
            timestamp,
            nonce,
            self.app_access_token,
            body)

        headers = {
            "Content-Type": "application/json",
            "AccessKey": self.ACCESS_KEY,
            "AppAccessToken": self.app_access_token,
            "Timestamp": timestamp,
            "Nonce": nonce,
            "Sign": sign,
            "ProductId": self.PRODUCT_ID,
            "X-TraceId-Header": str(uuid.uuid4()),
            "Version": self.VERSION,
        }

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.post(url, headers=headers, json=body)
        return response.json()

    # --------------------
    # Business APIs
    # --------------------

    def add_device(
            self,
            device_id: str,
            dev_password: str,
            category_code: str = "IPC",
            dev_account: str = "admin"):
        """
        Add a device to your DoLynk product using the device_id set in the class.

        Parameters:
        - category_code (str): The category of the device, e.g., "IPC"
        - dev_password (str): The device's login password (will be encrypted)
        - dev_account (str): The device login account, defaults to "admin"

        Returns:
        - dict: API response from DoLynk
        """

        if not device_id:
            raise ValueError("Device ID is not set in the class.")

        # Encrypt the device password
        encoded_password = base64.b64encode(
            dev_password.encode("utf-8")).decode("utf-8")
        encrypted_dev_code = f"Dolynk_{encoded_password}"

        payload = {
            "deviceId": device_id,
            "categoryCode": category_code,
            "devCode": encrypted_dev_code,
            "devAccount": dev_account
        }
        response = self._post("api-iot/device/addDevice", payload)

        if response.get("code") != "200":
            return {
                "code": response.get("code"),
                "message": response.get("msg")}

        # Check the device smart abilities and disable SMD if present
        device_abilities = self.disable_smd_abilities(device_id)

        # Create device hls url
        hls_response = self.create_live_hls_url(device_id)
        if str(hls_response.get("code")) not in ["200", "IDV0055"]:
            self.delete_device(device_id)
            return {
                "code": "400",
                "message": "Failed to create live HLS URL for the device. Device may be offline.",
            }

        # Check if motion detection is supported
        check_payload = {
            "deviceId": device_id,
            "channelId": "0",
            "abilityType": "motionDetect"
        }
        check_response = self._post(
            "api-iot/device/getAbilityStatus", check_payload)

        if (
            check_response.get("code") == "200"
            and check_response.get("success")
            and check_response.get("data")
            and "status" in check_response["data"]
        ):
            if check_response["data"]["status"] == "off":
                enable_payload = {
                    "deviceId": device_id,
                    "channelId": "0",
                    "abilityType": "motionDetect",
                    "status": "on"
                }
                enable_response = self._post(
                    "api-iot/device/setAbilityStatus", enable_payload)
                if enable_response.get(
                        "code") == "200" and enable_response.get("success"):
                    return {
                        "code": "200",
                        "message": "Device added and motion detection enabled successfully."}
            else:
                return {
                    "code": "200",
                    "message": "Device added successfully. Motion detection was already enabled."}
        else:
            self.delete_device(device_id)
            return {
                "code": "400",
                "message": "Device does not support motion detection."
            }

    def delete_device(self, device_id: str):
        """
        Delete the device using device_id.

        Raises:
        - ValueError: If device_id is not set.

        Returns:
        """
        # Ensure that device_id has been set before calling this method
        if not device_id:
            raise ValueError("Device ID is not set.")

        payload = {
            "deviceId": device_id
        }

        return self._post("api-iot/device/deleteDevice", payload)

    def get_camera_models(self):
        """
        Fetch device categories for 'IPC' (Network Cameras) and 'SD' (PTZ Cameras).

        Returns:
        - dict: {
            "Network Cameras": [...device models...],
            "PTZ Cameras": [...device models...]
        }
        """
        category_map = {
            "Network Cameras": "IPC",
            "PTZ Cameras": "SD"
        }

        formatted_result = {}

        for label, code in category_map.items():
            payload = {"secondCategoryCode": code}
            response = self._post("api-iot/device/getCategory", payload)

            if response.get("code") == "200" and response.get("success"):
                data = response.get("data", {}).get("categoryList", [])
                if data:
                    # Some APIs return multiple items, so we flatten any found
                    # deviceModel lists
                    device_models = []
                    for item in data:
                        models = item.get("deviceModel", [])
                        device_models.extend(models)
                    formatted_result[code] = device_models
                else:
                    formatted_result[code] = []
            else:
                formatted_result[code] = []
        return formatted_result

    def get_device_status(self, device_id: str):
        """
        Get the online/offline status of a single Dahua device.

        Parameters:
        - device_id (str): The unique device ID or serial number.

        Returns:
        - dict: API response containing the device's online/offline status.
        API Reference:
            /open-api/api-iot/device/deviceOnline
        """
        if not device_id:
            raise ValueError("device_id is required.")

        payload = {"deviceId": device_id}
        response = self._post("api-iot/device/deviceOnline", payload)

        if response.get("code") == "200" and response.get("success"):
            data = response.get("data", {})
            return {
                "code": "200",
                "deviceId": data.get("deviceId", device_id),
                "status": data.get("status", "unknown")
            }
        else:
            return {
                "code": response.get("code", "400"),
                "message": "Failed to retrieve device status."
            }

    def disable_smd_abilities(self, device_id: str):
        """
        Disable SMD abilities for a device. Only requires the device_id.
        Abilities: smdHuman, smdAnimal, smdHumanAndVehicle, smdVehicle
        """
        abilities_to_disable = [
            "smdHuman",
            "smdAnimal",
            "smdHumanAndVehicle",
            "smdVehicle"]
        channel_id = "0"
        results = {}

        for ability in abilities_to_disable:
            # Check if the device supports this ability
            check_payload = {
                "deviceId": device_id,
                "channelId": channel_id,
                "abilityType": ability
            }
            check_response = self._post(
                "api-iot/device/getAbilityStatus", check_payload)

            if (check_response.get("code") == "200"
                and check_response.get("success")
                and check_response.get("data")
                    and "status" in check_response["data"]):

                if check_response["data"]["status"] != "off":
                    # Disable the ability
                    disable_payload = {
                        "deviceId": device_id,
                        "channelId": channel_id,
                        "abilityType": ability,
                        "status": "off"
                    }
                    disable_response = self._post(
                        "api-iot/device/setAbilityStatus", disable_payload)

                    if disable_response.get(
                            "code") == "200" and disable_response.get("success"):
                        results[ability] = "disabled"
                    else:
                        results[ability] = f"failed to disable: {disable_response}"
                else:
                    results[ability] = "already off"
            else:
                results[ability] = "not supported"

        return results

    def create_live_hls_url(self, device_id: str, channel_id=0, stream_type=0):
        """
        Get the permanent HLS live stream URL for a Dahua device.

        Parameters:
        - device_id (str): The device ID
        - channel_id (int): Channel number (default 0)
        - stream_type (int): Stream type, 0 = HD main stream, 1 = SD sub stream

        Returns:
        - dict: { "code": 200, "hls_url": "<url>" } on success
        """
        if not device_id:
            raise ValueError("device_id is required")

        payload = {
            "deviceId": device_id,
            "channelId": str(channel_id),
            "streamType": stream_type
        }

        response = self._post("api-iot/device/createDeviceHlsLive", payload)

        if response.get("code") == "200" and response.get("success"):
            # Grab the first HLS URL from streamList
            stream_list = response.get("data", {}).get("streamList", [])
            if stream_list:
                return {"code": 200, "hls_url": stream_list[0].get("hls")}
            else:
                return {"code": 400, "message": "No HLS URL returned"}
        else:
            return {
                "code": response.get("code", 400),
                "message": "Failed to get live HLS URL",
                "response": response
            }

    def get_hls_live_list(self, device_id: str, channel_id: str = "0"):
        """
        Get the HLS live stream URL list for a given Dahua device and pick the best HD HTTPS URL.

        Parameters:
        - device_id (str): The device ID
        - channel_id (str): Channel number (default "0")

        Returns:
        - dict: {
            "code": 200,
            "hls_urls": [list of all HLS URLs],
            "stream_info": [full streamList info],
            "best_hls": str or None  # Best HD HTTPS stream for React/browser
        } on success
        """
        if not device_id:
            raise ValueError("device_id is required")

        payload = {
            "deviceId": device_id,
            "channelId": channel_id
        }

        response = self._post("api-iot/device/getHlsLiveList", payload)

        if response.get("code") == "200" and response.get(
                "success") and response.get("data"):
            hls_urls = []
            stream_info = []
            best_hls = None

            for item in response["data"]:
                stream_list = item.get("streamList", [])
                for stream in stream_list:
                    hls_url = stream.get("hls")
                    if hls_url:
                        hls_urls.append(hls_url)
                        stream_info.append(stream)
                        # Pick first HD HTTPS stream as best_hls
                        if not best_hls and stream.get(
                                "streamType") == 0 and hls_url.startswith("https://"):
                            best_hls = hls_url

            return {
                "code": 200,
                "url": best_hls
            }
        else:
            return {
                "code": response.get("code", 400),
                "message": "Failed to get HLS live list",
                "response": response
            }

    def get_hls_playback_list(
        self,
        device_id: str,
        channel_id: str = "0",
        begin_time: str = None,
        end_time: str = None
    ):
        """
        Generate an HLS live stream from device recording segments.

        Parameters:
        - device_id (str): Dahua device ID
        - channel_id (str): Channel number (default "0")
        - begin_time (str): Playback begin time, format "yyyy-MM-dd HH:mm:ss"
        - end_time (str): Playback end time, format "yyyy-MM-dd HH:mm:ss"

        Returns:
        - dict: {
            "code": int,
            "success": bool,
            "hls_url": str
            "msg": str
        } on success
        """
        if not all([device_id, begin_time, end_time]):
            raise ValueError(
                "device_id, begin_time, and end_time are required")

        payload = {
            "deviceId": device_id,
            "channelId": channel_id,
            "beginTime": begin_time,
            "endTime": end_time
        }

        response = self._post("api-iot/device/createDeviceRecordHls", payload)

        if response.get("code") == "200" and response.get(
                "success") and response.get("data"):
            return {
                "code": 200,
                "success": True,
                "url": response["data"].get("url"),
                "msg": response.get("msg", "")
            }
        else:
            return {
                "code": response.get(
                    "code",
                    400),
                "success": False,
                "hls_url": None,
                "message": response.get(
                    "msg",
                    "Failed to generate HLS from recording"),
                "response": response}

    def get_all_device_statuses(self, page_size=100):
        """
        Batch fetch all Dahua device IDs and their statuses.
        Returns a list of dicts: {deviceId, deviceStatus}
        """
        devices = []
        page_num = 1
        while True:
            payload = {
                "pageNum": str(page_num),
                "pageSize": str(page_size)
            }
            response = self._post("api-iot/device/getDeviceList", payload)
            if response.get("code") != "200" or not response.get("success"):
                break
            data = response.get("data", {})
            page_data = data.get("pageData", [])
            if not page_data:
                break
            for item in page_data:
                device_list = item.get("deviceList", [])
                for device in device_list:
                    devices.append({
                        "deviceId": device.get("deviceId"),
                        "deviceStatus": device.get("deviceStatus")
                    })
            # Pagination
            current_page = data.get("currentPage", page_num)
            total_page = data.get("totalPage", page_num)
            if current_page >= total_page:
                break
            page_num += 1
        return devices


if __name__ == "__main__":
    dahua_api = DahuaAPI()
    # Example usage: Add a device
    print(dahua_api.get_all_device_statuses())
