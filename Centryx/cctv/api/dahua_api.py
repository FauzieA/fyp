import time
import uuid
import hmac
import hashlib
import json
import requests
import environ
from pathlib import Path
import base64

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

    def __init__(self, device_id=None):
        self.device_id = device_id
        self.app_access_token = None
        self.token_expiry = 0  # track token expiry time

    # --------------------------------------
    # Utility: remove whitespace from string
    # --------------------------------------
    @staticmethod
    def _delete_whitespace(s: str):
        return "".join(c for c in s if not c.isspace())

    # --------------------------------------
    # Signature for access token request
    # --------------------------------------
    def _open_token_sign(self, method, timestamp, nonce):
        str_to_sign = f"{self.ACCESS_KEY}{timestamp}{nonce}{method}"
        sign_result = hmac.new(
            self.SECRET_ACCESS_KEY.encode("utf-8"),
            str_to_sign.encode("utf-8"),
            hashlib.sha512
        ).hexdigest().upper()
        return sign_result

    # --------------------------------------
    # Signature for business API requests
    # --------------------------------------
    def _open_sign(self, method, timestamp, nonce, app_access_token, body):
        body_str = json.dumps(body) if body else ""
        clean_body = self._delete_whitespace(body_str)
        
        # SHA512 hash of cleaned body
        body_hash = hashlib.sha512(clean_body.encode("utf-8")).hexdigest() if body_str else ""
        
        # stringToSign includes "POST\n" + body hash
        string_to_sign = f"{method}\n{body_hash}"
        
        # Full string to sign
        str_auth = f"{self.ACCESS_KEY}{app_access_token}{timestamp}{nonce}{string_to_sign}"
        
        # HMAC-SHA512 signature
        sign_result = hmac.new(
            self.SECRET_ACCESS_KEY.encode("utf-8"),
            str_auth.encode("utf-8"),
            hashlib.sha512
        ).hexdigest().upper()
        
        return sign_result


    # --------------------------------------
    # Obtain AppAccessToken (auto-refresh)
    # --------------------------------------
    def _get_app_access_token(self):
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

    # --------------------------------------
    # Ensure token validity before request
    # --------------------------------------
    def _ensure_token(self):
        if not self.app_access_token or time.time() >= self.token_expiry:
            # Refreshing AppAccessToken...
            self._get_app_access_token()

    # --------------------------------------
    # Generic business API request
    # --------------------------------------
    def _post(self, endpoint, body):
        self._ensure_token()
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        method = "POST"

        sign = self._open_sign(method, timestamp, nonce, self.app_access_token, body)

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
    

    # --------------------------------------
    # Business APIs
    # --------------------------------------
    
    def add_device(self, category_code: str, dev_password: str, dev_account: str = "admin"):
        """
        Add a device to your DoLynk product using the device_id set in the class.

        Parameters:
        - category_code (str): The category of the device, e.g., "IPC"
        - dev_password (str): The device's login password (will be encrypted)
        - dev_account (str): The device login account, defaults to "admin"

        Returns:
        - dict: API response from DoLynk
        """

        # Ensure that self.device_id has been set before calling this method
        if not self.device_id:
            raise ValueError("Device ID is not set in the class.")

        # --------------------------
        # Encrypt the device password
        # --------------------------
        encoded_password = base64.b64encode(dev_password.encode("utf-8")).decode("utf-8")
        encrypted_dev_code = f"Dolynk_{encoded_password}"

        payload = {
            "deviceId": self.device_id,
            "categoryCode": category_code,
            "devCode": encrypted_dev_code,
            "devAccount": dev_account
        }
        return self._post("api-iot/device/addDevice", payload)


    def delete_device(self):
        """
        Delete the device using self.device_id.

        Raises:
        - ValueError: If self.device_id is not set.
        
        Returns:
        - dict: API response
        """
        # Ensure that self.device_id has been set before calling this method
        if not self.device_id:
            raise ValueError("Device ID is not set in the class.")

        payload = {
            "deviceId": self.device_id
        }

        return self._post("api-iot/device/deleteDevice", payload)
    

    def get_live_hls(self, channel_id=0, stream_type=1):
        """
        Get the permanent HLS live stream URL for a device.

        Parameters:
        - channel_id (int): Camera channel (0 for IP cameras, 0-n for NVR channels)
        - stream_type (int): 0 = HD Main Stream, 1 = SD Sub Stream

        Returns:
        - dict: API response containing the stream URL in 'data.streamList'
        """
        if not self.device_id:
            raise ValueError("Device ID is not set in the class.")

        payload = {
            "deviceId": self.device_id,
            "channelId": channel_id,
            "streamType": stream_type
        }

        return self._post("api-iot/device/createDeviceHlsLive", payload)


    def get_cloud_recordings(self, begin_time, end_time, channel_id=0, encrypt_mode=0):
        """
        Fetch cloud recordings for a device within a time range.

        Parameters:
        - begin_time (str): Start time in 'yyyy-MM-dd HH:mm:ss' format
        - end_time (str): End time in 'yyyy-MM-dd HH:mm:ss' format
        - channel_id (int): Camera channel (0 for IP cameras, 0-n for NVR channels)
        - encrypt_mode (int): 0 = no encryption, 1 = encrypted

        Returns:
        - dict: API response containing the cloud recording URL in 'data.url'
        """

        # Ensure that self.device_id has been set before calling this method
        if not self.device_id:
            raise ValueError("Device ID is not set in the class.")
        payload = {
            "deviceId": self.device_id,
            "channelId": channel_id,
            "businessType": "cloudRecord",
            "encryptMode": encrypt_mode,
            "beginTime": begin_time,
            "endTime": end_time
        }

        return self._post("api-iot/device/createDeviceStreamUrl", payload)








if __name__ == "__main__":
    api = DahuaAPI(device_id="5F0679CPAJ7516A")
    try:
        res = api.get_live_hls()
        print("Live HLS Response:", res)
    except Exception as e:
        print("❌ Failed:", e)
