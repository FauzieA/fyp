import logging
from .models import SmartLight, DeviceAudit, LightModel, LightBrand
from lights.api.lifx_api import LIFXApi

logger = logging.getLogger(__name__)


class LIFXService:
    def __init__(self):
        self.api = LIFXApi()

    def validate_and_get_metadata(self, cloud_device_id: str):
        return self.api.get_device(cloud_device_id)

    def register_device(self, *, name, location, cloud_device_id, model_name):
        metadata = self.validate_and_get_metadata(cloud_device_id)
        if not metadata:
            raise ValueError("Device not found on LIFX Cloud")

        brand = LightBrand.objects.get(name="LIFX")

        model, _ = LightModel.objects.get_or_create(
            name=model_name,
            brand=brand,
            defaults={
                "capabilities": {
                    "color": metadata.get("color", False),
                    "brightness": True
                }
            }
        )

        light = SmartLight.objects.create(
            name=name,
            location=location,
            model=model,
            cloud_device_id=cloud_device_id,
            is_on=metadata.get("power") == "on",
            brightness=metadata.get("brightness"),
            raw_meta=metadata
        )
        return light

    def turn_on(self, light: SmartLight):
        result = self.api.set_state(light.cloud_device_id, power="on")
        light.is_on = True
        light.save()

        DeviceAudit.objects.create(device=light, action="turn_on", result=result)
        return result

    def turn_off(self, light: SmartLight):
        result = self.api.set_state(light.cloud_device_id, power="off")
        light.is_on = False
        light.save()

        DeviceAudit.objects.create(device=light, action="turn_off", result=result)
        return result

    def set_brightness(self, light: SmartLight, brightness: float):
        result = self.api.set_state(light.cloud_device_id, brightness=brightness)
        light.brightness = brightness
        light.save()

        DeviceAudit.objects.create(
            device=light,
            action="set_brightness",
            payload={"brightness": brightness},
            result=result
        )
        return result
