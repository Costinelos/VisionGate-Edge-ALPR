import time
import logging
import json
import threading
import base64
import os
import cv2
import RPi.GPIO as GPIO

from camera import CameraController
from image_processor import ImageProcessor
from ocr_engine import OCREngine
from sensors import PIRSensor, UltrasonicSensor
from actuators import ServoController
from database import DatabaseManager
from lcd_display import LCDController
from server_wifi import WifiServer
import network_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LicensePlateSystem:
    def __init__(self):
        logger.info("Initializing system...")
        self.db = DatabaseManager()
        self.camera = CameraController()
        self.processor = ImageProcessor()
        self.ocr = OCREngine()
        self.pir = PIRSensor(pin=17)
        self.ultrasonic = UltrasonicSensor(trig=23, echo=24)
        self.servo = ServoController(pin=18)
        self.lcd = LCDController()

        self.wifi_server = WifiServer(self.process_network_command)

        self.net_thread = threading.Thread(target=self.wifi_server.start, daemon=True)
        self.net_thread.start()
        logger.info("Network service is running in the background.")

        self.running = False
        self.ai_active = False

    def process_network_command(self, command):
        logger.info(f"Network command received: {command}")

        try:
            parts = command.split(':')
            cmd = parts[0].strip()

            if cmd == "LOGIN" and len(parts) == 3:
                username = parts[1]
                password = parts[2]
                role = self.db.verify_login(username, password)

                if role == "BANNED":
                    return "ERR:AccountBanned"
                elif role:
                    return f"OK:LOGIN:{role}"
                else:
                    return "ERR:InvalidCredentials"

            elif cmd == "OPEN_GATE":
                action_user = parts[1] if len(parts) > 1 else "MOBILE_USER"

                if self.db.is_user_banned(action_user):
                    self.db.log_access(plate_text=None, access_type="BLOCKED_BANNED_USER", image_path="None",
                                       action_by=action_user)
                    return "ERR:UserBanned"

                if hasattr(self.lcd, 'turn_on'): self.lcd.turn_on()
                self.lcd.clear_and_write("Manual Command", f"User: {action_user}")

                image_path = self.camera.capture_image()
                self.db.log_access(plate_text=None, access_type="ALERT!!!:MANUAL_OPEN", image_path=image_path,
                                   action_by=action_user)

                self.servo.open_barrier()
                self.servo.wait_and_close(self.ultrasonic)

                if self.ai_active:
                    self.lcd.clear_and_write("VisionGate", "Waiting for car")
                else:
                    if hasattr(self.lcd, 'turn_off'): self.lcd.turn_off()
                return "OK:Gate Opened"

            elif cmd == "SET_AI" and len(parts) == 2:
                state = parts[1].strip()
                if state == "ON":
                    self.ai_active = True
                    if hasattr(self.lcd, 'turn_on'): self.lcd.turn_on()
                    self.lcd.clear_and_write("VisionGate", "Waiting for car")
                    return "OK:AI_ON"
                elif state == "OFF":
                    self.ai_active = False
                    if hasattr(self.lcd, 'turn_off'): self.lcd.turn_off()
                    return "OK:AI_OFF"
                return "ERR:InvalidState"

            elif cmd == "GET_PLATES":
                return json.dumps(self.db.get_all_plates())

            elif cmd == "GET_USERS":
                users = [u['username'] for u in self.db.get_all_users()]
                return json.dumps(users)

            elif cmd == "GET_LOGS":
                return json.dumps(self.db.get_logs(limit=1000))

            elif cmd == "GET_IMAGE" and len(parts) >= 2:
                img_path = command.split(':', 1)[1].strip()
                if os.path.exists(img_path):
                    try:
                        img = cv2.imread(img_path)
                        h, w = img.shape[:2]
                        new_dim = (1080, int(h * (1080.0 / w)))
                        hq_img = cv2.resize(img, new_dim, interpolation=cv2.INTER_AREA)

                        _, img_buffer = cv2.imencode('.jpg', hq_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        return f"OK:IMAGE:{base64.b64encode(img_buffer).decode('utf-8')}"
                    except:
                        return "ERR:CannotReadImage"
                return "ERR:ImageNotFound"

            elif cmd == "ADD_PLATE" and len(parts) >= 4:
                admin_user = parts[1].strip()
                plate = parts[2].strip()
                owner = ":".join(parts[3:]).strip()
                if self.db.add_plate(plate, owner, admin_user):
                    self.db.log_access(plate_text=plate, access_type="PLATE_ADDED", image_path="None",
                                       action_by=admin_user)
                    return "OK:Added"
                return "ERR:Database Error"

            elif cmd == "EDIT_PLATE" and len(parts) >= 5:
                admin_user = parts[1].strip()
                old_plate = parts[2].strip()
                new_plate = parts[3].strip()
                new_owner = ":".join(parts[4:]).strip()
                if self.db.update_plate(old_plate, new_plate, new_owner):
                    self.db.log_access(plate_text=f"{old_plate}->{new_plate}", access_type="PLATE_EDITED",
                                       image_path="None", action_by=admin_user)
                    return "OK:Updated"
                return "ERR:Edit Failed"

            elif cmd == "DEL_PLATE" and len(parts) >= 3:
                admin_user = parts[1].strip()
                plate = parts[2].strip()
                if self.db.delete_plate(plate):
                    self.db.log_access(plate_text=plate, access_type="PLATE_DELETED", image_path="None",
                                       action_by=admin_user)
                    return "OK:Deleted"
                return "ERR:Database Error"

            return "ERR:Unknown Command"
        except Exception as e:
            return f"ERR:{str(e)}"

    def process_vehicle(self):
        self.lcd.clear_and_write("Detection!", "Processing...")
        time.sleep(0.5)

        image_path = self.camera.capture_image()

        if not image_path:
            self.lcd.clear_and_write("Camera Error", "")
            time.sleep(1)
            return

        crops = self.processor.process_and_crop(image_path)
        if not crops:
            self.lcd.clear_and_write("Unknown", "No Plate Found")
            self.db.log_access(plate_text="UNKNOWN", access_type="NO_PLATE_DETECTED", image_path=image_path,
                               action_by="SYSTEM")
            time.sleep(1.5)
            self.lcd.clear_and_write("VisionGate", "Waiting for car")
            return

        best_raw_read = "UNREADABLE"
        for crop in crops:
            plate_text = self.ocr.recognize(crop['image'])
            if plate_text:
                clean_text = plate_text.upper().replace(" ", "").replace("-", "").strip()
                if not clean_text: continue
                best_raw_read = clean_text

                if self.db.is_authorized(clean_text):
                    self.db.log_access(plate_text=clean_text, access_type="GRANTED", image_path=image_path,
                                       action_by="SYSTEM")
                    self.lcd.clear_and_write(clean_text, "ACCESS GRANTED")
                    self.servo.open_barrier()
                    self.servo.wait_and_close(self.ultrasonic)
                    self.lcd.clear_and_write("VisionGate", "Waiting for car")
                    return

        self.db.log_access(plate_text=best_raw_read, access_type="DENIED", image_path=image_path, action_by="SYSTEM")
        self.lcd.clear_and_write("Access Denied", "Unknown Plate")

        time.sleep(3)
        self.lcd.clear_and_write("VisionGate", "Waiting for car")

    def run(self):
        self.running = True
        if hasattr(self.lcd, 'turn_off'): self.lcd.turn_off()

        try:
            while self.running:
                if self.ai_active and self.pir.is_detected():
                    self.process_vehicle()
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False

    def shutdown(self):
        self.running = False
        try:
            self.servo.cleanup()
            if hasattr(self.lcd, 'turn_off'): self.lcd.turn_off()
            GPIO.cleanup()
        except:
            pass


if __name__ == "__main__":
    network_ok = network_manager.start_vision_gate_network()

    app = LicensePlateSystem()

    try:
        app.run()
    finally:
        app.shutdown()
        logger.info("Restoring wifi...")
        network_manager.restore_home_network()