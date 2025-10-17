import uuid

from django.db import models


class Brand(models.Model):
    """Model for CCTV Brand"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, editable=False)

    def __str__(self):
        return self.name


class CCTVModel(models.Model):
    """Model for CCTV Models"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, editable=False)
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='models')

    def __str__(self):
        return self.name


class CCTV(models.Model):
    """Model for CCTV"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identifier = models.CharField(max_length=100, unique=True, editable=False)
    model = models.ForeignKey(
        CCTVModel,
        on_delete=models.CASCADE,
        related_name='cctvs')
    location = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.identifier} - {self.model.name}"
