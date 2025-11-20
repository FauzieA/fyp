import uuid
from django.db import models
from django.utils import timezone


class LightBrand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.name


class LightModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    brand = models.ForeignKey(LightBrand, on_delete=models.CASCADE, related_name='models')
    capabilities = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = (('name', 'brand'),)

    def __str__(self):
        return f"{self.brand.name} {self.name}"


class SmartLight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)

    model = models.ForeignKey(LightModel, on_delete=models.PROTECT, related_name='devices')
    cloud_device_id = models.CharField(max_length=255, unique=True)

    local_ip = models.GenericIPAddressField(null=True, blank=True)

    is_on = models.BooleanField(default=False)
    brightness = models.FloatField(null=True, blank=True)
    raw_meta = models.JSONField(default=dict, blank=True)

    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.name} ({self.model.brand.name} - {self.model.name})"


class DeviceAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(SmartLight, on_delete=models.CASCADE, related_name='audits')
    action = models.CharField(max_length=100)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.device.name} - {self.action} @ {self.created.isoformat()}"
