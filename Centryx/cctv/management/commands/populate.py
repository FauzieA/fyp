from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from integration.models import Profile

from cctv.models import Brand

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with super admin, users, and CCTV data'

    def handle(self, *args, **options):
        # -------------------------
        # 0) Configure Site for password reset emails
        # -------------------------
        site = Site.objects.get(id=1)
        site.domain = 'localhost:8000'
        site.name = 'Centryx Local'
        site.save()
        self.stdout.write(self.style.SUCCESS(
            f"Site configured: {site.domain}"))

        # -------------------------
        # 1) Users data
        # -------------------------
        admin_username = "centryxadmin"
        first_name = "Admin"
        last_name = "Centryx"
        admin_email = "antoine.leno@student.aiu.edu.my"
        admin_password = "centryxpassword"
        phone_number = "+6056568568"

        user, created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                "email": admin_email,
                "first_name": first_name,
                "last_name": last_name,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(admin_password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Super admin '{admin_username}' created successfully."))
        else:
            # Ensure existing user has admin permissions
            if not user.is_superuser or not user.is_staff:
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated '{admin_username}' to superuser."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Super admin '{admin_username}' already exists."))

        # Create or update profile safely
        profile, _ = Profile.objects.get_or_create(user=user)
        if not profile.phone_number:
            profile.phone_number = phone_number
            profile.save()

        # Verify admin email for allauth
        EmailAddress.objects.get_or_create(
            user=user,
            email=admin_email,
            defaults={
                'verified': True,
                'primary': True,
            }
        )

        # -------------------------
        # 2) CCTV Brand data
        # -------------------------
        brands = ["Dahua", "Hikvision"]

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

        # -------------------------
        # 3) Set automation to true
        # -------------------------
        from cctv.models import Automation
        automation, created = Automation.objects.get_or_create()
        if created:
            automation.active = True
            automation.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Automation set to active."))
        else:
            if not automation.active:
                automation.active = True
                automation.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Automation updated to active."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Automation is already active."))
