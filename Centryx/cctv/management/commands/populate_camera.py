import random
import uuid

from django.core.management.base import BaseCommand

from cctv.models import Brand, Camera, CCTVModel


class Command(BaseCommand):
    help = "Populate database with 100 CCTV cameras"

    def handle(self, *args, **options):
        # Ensure there are brands
        brands = Brand.objects.all()
        if not brands.exists():
            self.stdout.write(self.style.ERROR(
                "No brands found! Add some brands first."))
            return

        cameras_created = 0

        for i in range(1, 101):  # create 100 cameras
            # Pick a random brand
            brand = random.choice(list(brands))

            # Pick a random model of that brand or create one if none
            models_qs = brand.models.all()
            if not models_qs.exists():
                model = CCTVModel.objects.create(
                    name=f"{brand.name} Default Model", brand=brand)
            else:
                model = random.choice(list(models_qs))

            # Generate unique identifier
            identifier = str(uuid.uuid4())[:8]  # short random id

            # Create camera
            camera = Camera.objects.create(
                name=f"{brand.name} Camera {i}",
                identifier=identifier,
                model=model,
                location=f"Location {i}"
            )

            cameras_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {cameras_created} CCTV cameras."))
