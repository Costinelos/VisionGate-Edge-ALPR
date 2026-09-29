import subprocess
import time
import logging

logger = logging.getLogger(__name__)

HOTSPOT_NAME = "Hotspot"
_original_wifi = None


def get_active_wifi_connection():
    try:
        result = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
            text=True
        )
        for line in result.strip().split('\n'):
            if not line: continue
            parts = line.split(':')
            if len(parts) >= 2:
                name, conn_type = parts[0], parts[1]
                if conn_type == '802-11-wireless' and name != HOTSPOT_NAME:
                    return name
    except Exception as e:
        logger.error(f"Error detecting active Wi-Fi: {e}")
    return None


def start_vision_gate_network():
    global _original_wifi
    try:
        _original_wifi = get_active_wifi_connection()

        if _original_wifi:
            logger.info(f"Local network detected: '{_original_wifi}'. Disabling autoconnect...")
            # PASUL CRITIC: Dezactivam autoconnect ca Linux sa nu o porneasca singur la loc
            subprocess.run(["sudo", "nmcli", "connection", "modify", _original_wifi, "connection.autoconnect", "no"],
                           check=True)
            subprocess.run(["sudo", "nmcli", "connection", "down", _original_wifi], check=False)
            time.sleep(2)

        logger.info("Activating VisionGate Hotspot...")
        # Fortam pornirea hotspot-ului
        subprocess.run(["sudo", "nmcli", "connection", "up", HOTSPOT_NAME], check=True)
        return True

    except Exception as e:
        logger.error(f"Fatal error starting VisionGate network: {e}")
        return False


def restore_home_network():
    global _original_wifi
    try:
        logger.info("Stopping VisionGate Hotspot...")
        subprocess.run(["sudo", "nmcli", "connection", "down", HOTSPOT_NAME], check=False)
        time.sleep(1)

        if _original_wifi:
            logger.info(f"Restoring autoconnect for: '{_original_wifi}'...")

            subprocess.run(["sudo", "nmcli", "connection", "modify", _original_wifi, "connection.autoconnect", "yes"],
                           check=True)
            subprocess.run(["sudo", "nmcli", "connection", "up", _original_wifi], check=False)
    except Exception as e:
        logger.error(f"Error restoring network: {e}")