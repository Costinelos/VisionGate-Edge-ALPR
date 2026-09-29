import logging
from RPLCD.i2c import CharLCD

logger = logging.getLogger(__name__)


class LCDController:
    def __init__(self, address=0x27):
        try:
            self.lcd = CharLCD('PCF8574', address, port=1, cols=16, rows=2)
            self.lcd.backlight_enabled = True
            self.clear_and_write("System Active", "Waiting...")
            logger.info("[LCD] Successfully initialized at 0x27.")
        except Exception as e:
            logger.error(f"[LCD] Initialization error: {e}")
            self.lcd = None

    def clear_and_write(self, line1, line2=""):
        if not self.lcd:
            return

        try:
            text1 = str(line1)[:16]
            text2 = str(line2)[:16]

            pad1 = (16 - len(text1)) // 2
            pad2 = (16 - len(text2)) // 2

            final_line1 = (" " * pad1 + text1).ljust(16)
            final_line2 = (" " * pad2 + text2).ljust(16)

            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(final_line1)

            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(final_line2)

        except Exception as e:
            logger.error(f"[LCD] Write error: {e}")

    def turn_on(self):
        if not self.lcd:
            return
        try:
            self.lcd.backlight_enabled = True
        except Exception as e:
            logger.error(f"[LCD] Error turning on backlight: {e}")

    def turn_off(self):
        if not self.lcd:
            return

        try:
            self.lcd.clear()
            self.lcd.backlight_enabled = False
            logger.info("[LCD] Display text cleared and backlight turned off.")
        except Exception as e:
            logger.error(f"[LCD] Error turning off display: {e}")

    def cleanup(self):
        if self.lcd:
            try:
                self.lcd.clear()
                self.lcd.backlight_enabled = False
                self.lcd.close(clear=True)
            except:
                pass