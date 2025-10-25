from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from cctv.models import Brand, CCTVModel

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
        # 2) CCTV Brand data
        # -------------------------
        brands = ["Dahua"]

        for brand_name in brands:
            brand, created = Brand.objects.get_or_create(name=brand_name)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Brand '{brand_name}' added."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Brand '{brand_name}' already exists."))
