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
        """Get product app access token
        API Reference: https://open.dolynkcloud.com/platform/develop/doccenter/doc?d=1715309164030x1724914605005
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
        API References:
            ** add device : https://open.dolynkcloud.com/platform/develop/doccenter/doc?d=1715309164030x1724914923611
            ** check motion : https://open.dolynkcloud.com/platform/develop/doccenter/doc?d=1715309164030x1724914808503
            ** Enable motion : https://open.dolynkcloud.com/platform/develop/doccenter/doc?d=1715309164030x1724915269635
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
            return response

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
        - dict: API response
        API Reference: https://open.dolynkcloud.com/platform/develop/doccenter/doc?d=1715309164030x1724914667805
        """
        # Ensure that device_id has been set before calling this method
        if not device_id:
            raise ValueError("Device ID is not set.")

        payload = {
            "deviceId": device_id
        }

        return self._post("api-iot/device/deleteDevice", payload)

    def get_camera_models(self, categories=None):
        """
        Fetch device models for specified camera categories from DoLynk.

        Returns only the list of device models, ignoring category names.
        """
        if categories is None:
            categories = {"IPC": "NetworkCameras", "SD": "PTZCameras"}

        all_models = []
        for code in categories.keys():
            payload = {"secondCategoryCode": code}
            response = self._post("api-iot/device/getCategory", payload)

            if response.get("success") and response.get(
                    "data") and response["data"].get("categoryList"):
                models = response["data"]["categoryList"][0].get(
                    "deviceModel", [])
                all_models.extend(models)

        return all_models

    def get_stream_url(
            self,
            device_id,
            channel_id=0,
            business_type="real",
            encrypt_mode=0,
            stream_type=0,
            proto_type="rtsp",
            begin_time=None,
            end_time=None):
        """
        Get the temporary streaming URL for live view or playback (local/cloud recording).

        businessType options:
        - "real"         → Live stream
        - "localRecord"  → Local SD card recording playback
        - "cloudRecord"  → Cloud recording playback

        API Reference:
        https://open.dolynkcloud.com/platform/develop/doccenter/doc?d=1715309164030x1724932054107
        """
        if not device_id:
            raise ValueError("Device ID is not set.")

        # Base payload for all stream types
        payload = {
            "deviceId": device_id,
            "channelId": str(channel_id),
            "businessType": business_type,
            "encryptMode": encrypt_mode,
            "streamType": stream_type,
            "protoType": proto_type
        }

        # If requesting recording playback, include time range
        if business_type in ["localRecord", "cloudRecord"]:
            if not (begin_time and end_time):
                raise ValueError(
                    "begin_time and end_time are required for recording playback.")
            payload["beginTime"] = begin_time
            payload["endTime"] = end_time

        # Send request
        response = self._post("api-iot/device/createDeviceStreamUrl", payload)

        # Handle response
        if response.get("code") == "200" and response.get("success"):
            stream_url = response["data"]["url"]
            return {"code": "200", "url": stream_url, "type": business_type}
        else:
            return {
                "code": "400",
                "message": f"Failed to get {business_type} stream URL.",
                "response": response
            }
