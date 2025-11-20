import logging
import os
import threading
import time

from integration.services.cctv_services import get_hikvision_client

logger = logging.getLogger(__name__)
hikvision = get_hikvision_client()


def handle_motion_event(event):
    """Handle each Hikvision motion alarm event."""
    try:
        source = event.get("eventSource", {})
        time_info = event.get("timeInfo", {})
        camera_name = source.get("sourceName", "Unknown")
        camera_id = source.get("sourceID")
        alarm_state = event.get("alarmState")
        device_info = source.get("deviceInfo", {})
        device_name = device_info.get("devName")

        # Get device ID from the database using the device_name
        device_id = None
        from cctv.models import \
            CCTVDevice  # Import here to avoid circular imports
        try:
            cctv_device = CCTVDevice.objects.get(name=device_name)
            device_id = cctv_device.id
        except CCTVDevice.DoesNotExist:
            logger.warning(
                f"""CCTVDevice with name
                {device_name} does not exist in the database.""")

        if alarm_state == "1":
            logger.info(
                f"Motion started: {camera_name} ({device_id}) at {
                    time_info.get('startTime')}")
            # Get all lights linked to this camera and turn them on using the
            # device_id

        elif alarm_state == "0":
            logger.info(
                f"Motion ended: {camera_name} ({device_id}) at {
                    time_info.get('endTime')}")
            # Get all lights linked to this camera and turn them off using the
            # device_id

    except Exception:
        logger.exception("Error handling Hikvision motion event")


def listen_for_motion(poll_interval: float = 0.5):
    """Continuously polls Hikvision for motion
    alarms and reconnects on failure.
    """
    logger.info("Starting Hikvision motion listener...")
    try:
        hikvision.subscribe_motion_detection()
    except Exception as e:
        logger.error(f"Failed to subscribe to motion detection: {e}")
        return

    while True:
        try:
            data = hikvision.get_motion_events()
            motion_list = data.get("alarmMsg", [])
            batch_id = data.get("batchId")  # Extract the single batch ID here

            if motion_list:
                for msg in motion_list:
                    handle_motion_event(msg)

            # Acknowledge the entire batch using the batch_id string
            if batch_id:
                hikvision.acknowledge_motion_events(batch_id)

        except Exception as e:
            # ... (error handling remains the same) ...
            time.sleep(poll_interval)
