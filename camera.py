import subprocess
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CameraController:
    def __init__(self, capture_dir="captures", rotation=180):
        self.capture_dir = capture_dir
        self.rotation = rotation
        os.makedirs(self.capture_dir, exist_ok=True)

    # ==============================================================
    # FUNCTIA VECHE (Fără Zoom)
    # ==============================================================
    # def capture_image(self):
    #     filename = f"plate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    #     filepath = os.path.join(self.capture_dir, filename)
    #
    #     cmd = [
    #         "rpicam-still", "-o", filepath, "--width", "1920", "--height", "1080",
    #         "--timeout", "1000", "--rotation", str(self.rotation), "--nopreview", "--quality", "95"
    #     ]
    #
    #     result = subprocess.run(cmd, capture_output=True)
    #     if result.returncode == 0 and os.path.exists(filepath):
    #         logger.info(f"Imagine capturata: {filepath}")
    #         return filepath
    #
    #     logger.error("Eroare la capturarea imaginii.")
    #     return None

    # ==============================================================
    # FUNCTIA NOUA (Zoom ROI)
    # ==============================================================
    def capture_image(self):
        filename = f"plate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(self.capture_dir, filename)
        cmd = [
            "rpicam-still", "-o", filepath,
            "--timeout", "1000",
            "--rotation", str(self.rotation),
            "--nopreview",
            "--quality", "100",
            "--sharpness", "1.5",
            "--roi", "0.5,0.2,0.5,0.5"
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and os.path.exists(filepath):
            logger.info(f"Image captured (High Fidelity + ROI): {filepath}")
            return filepath

        logger.error("Failed to capture image.")
        return None