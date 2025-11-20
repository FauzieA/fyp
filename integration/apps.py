import logging
import os
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class IntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integration'

    def ready(self):
        """Start Hikvision motion listener when Django starts (only once)."""
        try:
            # Prevent multiple threads when running with Gunicorn/Reload
            if os.environ.get("RUN_MAIN") == "true":
                from integration.services.hikvision_motion_listener import \
                    listen_for_motion
                thread = threading.Thread(
                    target=listen_for_motion, daemon=True)
                thread.start()
                logger.info("Hikvision motion listener started successfully.")
        except Exception as e:
            logger.error(f"Failed to start Hikvision motion listener: {e}")
