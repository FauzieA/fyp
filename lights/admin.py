# lights/admin.py
from django.contrib import admin
from .models import LightBrand, LightModel, SmartLight, DeviceAudit


@admin.register(LightBrand)
class LightBrandAdmin(admin.ModelAdmin):
    list_display = ("name", "created")
    search_fields = ("name",)


@admin.register(LightModel)
class LightModelAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "created")
    list_filter = ("brand",)
    search_fields = ("name",)


@admin.register(SmartLight)
class SmartLightAdmin(admin.ModelAdmin):
    list_display = ("name", "model", "cloud_device_id", "is_on", "brightness", "created")
    search_fields = ("name", "cloud_device_id")
    list_filter = ("model__brand", "is_on")
    readonly_fields = ("raw_meta",)
    actions = ["force_refresh_state"]

    def force_refresh_state(self, request, queryset):
        """
        Admin action to fetch latest state from LIFX Cloud for selected lights.
        """
        from .api.lifx_api import LIFXApi
        api = LIFXApi()
        updated = 0
        for light in queryset:
            try:
                meta = api.get_light(light.cloud_device_id)
                if meta:
                    light.is_on = (meta.get("power") == "on")
                    light.brightness = meta.get("brightness")
                    light.raw_meta = meta
                    light.save()
                    updated += 1
            except Exception:
                continue
        self.message_user(request, f"Refreshed {updated} lights")


@admin.register(DeviceAudit)
class DeviceAuditAdmin(admin.ModelAdmin):
    list_display = ("device", "action", "created")
    readonly_fields = ("payload", "result")
    search_fields = ("device__name", "action")
