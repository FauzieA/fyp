import os
import requests
import django
import sys
import uuid

# ----------------------
# Setup Django environment
# ----------------------
PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_PATH)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Centryx.settings")
django.setup()

from lights.models import LightBrand, LightModel, SmartLight

# ----------------------
# Configuration
# ----------------------
DJANGO_SERVER = "http://127.0.0.1:8000"
LIST_ENDPOINT = "/lights/cloud/list/"
REGISTER_ENDPOINT = "/lights/register/"
CONTROL_ENDPOINT_TEMPLATE = "/lights/devices/{uuid}/control/"

USE_MOCK = False

# Mock data
MOCK_LIGHTS = [
    {"id": "d1f2g3h4", "label": "Living Room Lamp"},
    {"id": "a9b8c7d6", "label": "Bedroom Strip"},
]

# ----------------------
# Helper functions
# ----------------------
def fetch_lights():
    if USE_MOCK:
        print("Using mocked cloud lights...")
        return MOCK_LIGHTS
    try:
        headers = {"Authorization": f"Bearer {os.environ['LIFX_API_TOKEN']}"}
        resp = requests.get(f"{DJANGO_SERVER}{LIST_ENDPOINT}", headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print("Error fetching lights:", e)
        return []


def register_light(light, brand_name="LIFX"):
    # Ensure brand exists
    brand, _ = LightBrand.objects.get_or_create(name=brand_name)

    # Ensure model exists (LightModel)
    # Create or get SmartLight
    model, _ = LightModel.objects.get_or_create(name=payload["model_name"], brand=brand)
    sl, created = SmartLight.objects.get_or_create(
    cloud_device_id=payload["cloud_device_id"],
    defaults={"model": model, "name": payload["model_name"]}
    )


    if USE_MOCK:
        print(f"Mock registered light: {sl.name} (Model: {sl.model.name}, Brand: {sl.model.brand.name}) Created: {created}")
    else:
        try:
            payload = {
                "cloud_device_id": light["id"],
                "model": str(model.id)
            }
            resp = requests.post(f"{DJANGO_SERVER}{REGISTER_ENDPOINT}", json=payload)
            resp.raise_for_status()
            print("Registered light successfully:", resp.json())
            return resp.json()
        except requests.RequestException as e:
            print("Error registering light:", e)
            return None
    return sl

def control_light(light_uuid, action="toggle"):
    payload = {"action": action}  # adjust per your API schema
    endpoint = CONTROL_ENDPOINT_TEMPLATE.format(uuid=light_uuid)

    if USE_MOCK:
        print(f"Mock control action '{action}' on light UUID: {light_uuid}")
        return {"status": "mocked"}
    try:
        resp = requests.post(f"{DJANGO_SERVER}{endpoint}", json=payload)
        resp.raise_for_status()
        print(f"Control response: {resp.json()}")
        return resp.json()
    except requests.RequestException as e:
        print("Error controlling light:", e)
        return None

# ----------------------
# Main test run
# ----------------------
if __name__ == "__main__":
    print("Fetching cloud lights...")
    lights = fetch_lights()

    for light in lights:
        print(f"\nProcessing light: {light['label']} ({light['id']})")
        sl = register_light(light)
        control_light(sl.cloud_device_id)
