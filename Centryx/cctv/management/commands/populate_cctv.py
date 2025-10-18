from django.core.management.base import BaseCommand
from cctv.models import Brand, CCTVModel
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with super admin, users, and CCTV data'

    def handle(self, *args, **options):
        # -------------------------
        # 1) Users data
        # -------------------------
        admin_username = "centryxadmin"
        admin_email = "admin@example.com"
        admin_password = "centryxpassword"

        if not User.objects.filter(username=admin_username).exists():
            User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Super admin '{admin_username}' created successfully."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Super admin '{admin_username}' already exists."))

        # -------------------------
        # 2) CCTV Brand & Models
        # -------------------------
        brand_name = "Dahua"
        model_names = [
            "IPC-HDW3541EM-S-S2",
            "H3B",
            "IPC-HFW1539DTK1-SW-PV",
            "P5AS-PV"
        ]

        # Create brand if it doesn't exist
        brand_obj, created = Brand.objects.get_or_create(name=brand_name)
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Brand '{brand_name}' created successfully."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Brand '{brand_name}' already exists."))

        # Create CCTV models
        for model_name in model_names:
            model_obj, created = CCTVModel.objects.get_or_create(
                name=model_name,
                brand=brand_obj
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"CCTV model '{model_name}' created under brand '{brand_name}'."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"CCTV model '{model_name}' already exists under brand '{brand_name}'."))
