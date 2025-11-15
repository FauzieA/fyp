import uuid

from django.db import models
from django.utils import timezone


class Brand(models.Model):
    """Model for CCTV Brand"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, editable=False)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.name


class CCTVModel(models.Model):
    """Model for CCTV Models"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='models')
    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.name


class Camera(models.Model):
    """Model for CCTV"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100, null=False)
    identifier = models.CharField(max_length=100, unique=True)
    model = models.ForeignKey(
        CCTVModel,
        on_delete=models.CASCADE,
        related_name='cctvs')
    location = models.CharField(max_length=255)
    created = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'identifier',
                    'model'],
                name='unique_camera_per_model')]

    def __str__(self):
        return f"{self.identifier} - {self.model.name}"


class Automation(models.Model):
    """Model for CCTV Brand"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return str(self.active)
