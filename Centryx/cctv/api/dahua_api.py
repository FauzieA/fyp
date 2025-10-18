import time
import uuid
import hmac
import hashlib
import json
import requests
import environ
from pathlib import Path

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
        body_hash = hashlib.sha512(clean_body.encode("utf-8")).hexdigest() if body_str else ""
        str_to_sign = f"{self.ACCESS_KEY}{app_access_token}{timestamp}{nonce}{method}{body_hash}"

        sign_result = hmac.new(
            self.SECRET_ACCESS_KEY.encode("utf-8"),
            str_to_sign.encode("utf-8"),
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
            self.token_expiry = time.time() + 24 * 60 * 60
        else:
            raise Exception(f"Failed to get AppAccessToken: {resp}")

    # --------------------------------------
    # Ensure token validity before request
    # --------------------------------------
    def _ensure_token(self):
        if not self.app_access_token or time.time() >= self.token_expiry:
            print("Refreshing AppAccessToken...")
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
    # Get live video stream
    # --------------------------------------
    def get_live_stream(self, encrypt_mode=0):
        payload = {
            "deviceId": self.device_id,
            "channelId": 0,
            "businessType": "real",
            "encryptMode": encrypt_mode
        }
        return self._post("api-iot/device/createDeviceStreamUrl", payload)

    # --------------------------------------
    # Get playback recording
    # --------------------------------------
    def get_recordings(self, begin_time, end_time, encrypt_mode=0):
        payload = {
            "deviceId": self.device_id,
            "channelId": 0,
            "businessType": "cloudRecord",
            "encryptMode": encrypt_mode,
            "beginTime": begin_time,
            "endTime": end_time
        }
        return self._post("api-iot/device/createDeviceStreamUrl", payload)


if __name__ == "__main__":
    api = DahuaAPI()
    try:
        api._get_app_access_token()
        print("✅ AppAccessToken fetched successfully!")
        print("Token:", api.app_access_token)
    except Exception as e:
        print("❌ Failed:", e)
