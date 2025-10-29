import os
import time
import logging
import threading
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

        if alarm_state == "1":
            logger.info(
                f"Motion started: {camera_name} ({camera_id}) at {
                    time_info.get('startTime')}")
            # Get all lights linked to this camera and turn them on
        elif alarm_state == "0":
            logger.info(
                f"Motion ended: {camera_name} ({camera_id}) at {
                    time_info.get('endTime')}")
            # GGet all lights linked to this camera and turn them off

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
            if motion_list:
                for msg in motion_list:
                    handle_motion_event(msg)

                ids = [m.get("msgID") for m in motion_list if m.get("msgID")]
                if ids:
                    hikvision.acknowledge_motion_events(ids)

        except Exception as e:
            logger.warning(f"Motion listener error: {e}, retrying in 5s...")
            try:
                hikvision._get_access_token()
                hikvision.subscribe_motion_detection()
            except Exception as inner_e:
                logger.error(f"Re-subscription failed: {inner_e}")
            time.sleep(5)
        time.sleep(poll_interval)
