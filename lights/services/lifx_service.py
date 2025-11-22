# lights/api/services/lifx_service.py

import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone

from lights.models import SmartLight, DeviceAudit
from lights.api.lifx_api import LIFXApi
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)


class LIFXService:
    """
    Unified service layer for handling LIFX cloud operations and local SmartLight management.
    """

    def __init__(self):
        self.api = LIFXApi()

    # ------------------------------------------------------------
    # CLOUD LIST + STATUS MAPPING
    # ------------------------------------------------------------
    def fetch_all_cloud_lights(self) -> List[Dict[str, Any]]:
        """
        Fetch all LIFX cloud lights with raw metadata.
        """
        response = self.api.list_all_lights()
        return response

    @staticmethod
    def map_lifx_status_to_field(cloud_device: Dict[str, Any]) -> str:
        """
        Convert LIFX connectivity to our unified status values.
        """
        if cloud_device.get("connected") is True:
            return "ok"
        return "offline"

    # ------------------------------------------------------------
    # LOCAL MODEL SYNC
    # ------------------------------------------------------------
    def update_local_status_from_cloud(self, light: SmartLight, cloud_meta: Dict[str, Any]) -> None:
        """
        Update local SmartLight status based on cloud metadata.
        """
        mapped = self.map_lifx_status_to_field(cloud_meta)
        if light.status != mapped:
            light.status = mapped
            light.save(update_fields=["status"])

    # ------------------------------------------------------------
    # DEVICE REGISTRATION
    # ------------------------------------------------------------
    
    def register_device(self, cloud_device_id: str, meta: Dict[str, Any]) -> SmartLight:
        """
        Create a local SmartLight mapped to a LIFX cloud device.
        """
        from lights.models import LightBrand, LightModel

        # Check if device already exists
        if SmartLight.objects.filter(cloud_device_id=cloud_device_id, model__brand__name="LIFX").exists():
            raise ValueError("This LIFX device is already registered.")

        # Get or create the LIFX brand
        lifx_brand, _ = LightBrand.objects.get_or_create(name="LIFX")

        # Get or create a default model for new devices
        default_model_name = "Default LIFX Model"
        default_model, _ = LightModel.objects.get_or_create(name=default_model_name, brand=lifx_brand)

        # Extract metadata
        name = meta.get("name") or "LIFX Light"
        product = meta.get("product", {})
        caps = product.get("capabilities", {})

        # Create SmartLight instance
        light = SmartLight.objects.create(
            name=name,
            model=default_model,
            cloud_device_id=cloud_device_id,
            is_on=meta.get("power") == "on",
            brightness=meta.get("brightness", 1.0),
            raw_meta=meta,
            status=self.map_lifx_status_to_field(meta),
        )   

        # Optional: store capabilities in model if needed
        default_model.capabilities.update({
            "has_color": caps.get("has_color", True),
            "has_variable_color_temp": caps.get("has_variable_color_temp", True),
        })
        default_model.save(update_fields=["capabilities"])

        # Audit log
        DeviceAudit.objects.create(
            device=light,
            action="register",
            payload={"cloud_device_id": cloud_device_id, "metadata": meta},
        )

        return light


    # ------------------------------------------------------------
    # CONTROL
    # ------------------------------------------------------------
    def control_light(self, light: SmartLight, **kwargs) -> Dict[str, Any]:
        """
        Unified control interface (on/off, brightness, color, etc.)
        """

        cloud_device_id = light.cloud_device_id
        if not cloud_device_id:
            raise ValidationError({
                "error": "missing_cloud_device_id",
                "message": "This device has no cloud_device_id and cannot be controlled."
            })

        # ------------------------------
        # WRAP LIFX API CALL IN TRY/EXCEPT
        # ------------------------------
        try:
            api_response = self.api.set_state(cloud_device_id, **kwargs)

        except Exception as e:
            # CLEAN JSON ERROR INSTEAD OF 500
            raise ValidationError({
                "error": "lifx_api_error",
                "message": str(e)
            })

        # If the API responded but with its own error field
        if api_response.get("error"):
            raise ValidationError({
                "error": "lifx_api_error",
                "message": api_response["error"]
            })

        # Update local fields
        if "power" in kwargs:
            light.is_on = kwargs["power"] == "on"

        if "brightness" in kwargs:
            light.brightness = float(kwargs["brightness"])

        light.status = "ok"
        light.last_seen = timezone.now()
        light.save(update_fields=["is_on", "brightness", "status", "last_seen"])

        # Audit log
        DeviceAudit.objects.create(
            device=light,
            action="control",
            payload={"sent": kwargs, "response": api_response},
        )

        return api_response

    # ------------------------------------------------------------
    # GET SINGLE
    # ------------------------------------------------------------
    def fetch_single_cloud_light(self, cloud_device_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch specific LIFX cloud device metadata.
        """
        data = self.api.get_light(cloud_device_id)
        if not data or "result" not in data:
            return None
        return data["result"]
class LifxApiError(Exception):
    """Raised when a LIFX API call fails"""
    pass