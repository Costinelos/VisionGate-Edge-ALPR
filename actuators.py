import RPi.GPIO as GPIO
import time
import logging

logger = logging.getLogger(__name__)


class ServoController:
    def __init__(self, pin=18, open_angle=90, close_angle=0):
        self.pin = pin
        self.open_angle = open_angle
        self.close_angle = max(5, close_angle)
        self.current_angle = self.close_angle

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, 50)
        self.pwm.start(0)

        self._set_angle_instant(self.close_angle)

    def _set_angle_instant(self, angle):
        safe_angle = max(5, min(175, angle))
        duty = 2.5 + (safe_angle / 180.0) * 10.0
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(0.5)
        self.pwm.ChangeDutyCycle(0)
        self.current_angle = safe_angle

    def _sweep_angle(self, target_angle, duration=2.0):
        step_delay = 0.04
        steps = int(duration / step_delay)

        start_angle = self.current_angle
        angle_diff = target_angle - start_angle

        for i in range(1, steps + 1):
            current_step_angle = start_angle + (angle_diff * (i / steps))

            safe_angle = max(5, min(175, current_step_angle))
            duty = 2.5 + (safe_angle / 180.0) * 10.0

            self.pwm.ChangeDutyCycle(duty)
            time.sleep(step_delay)

        final_safe_angle = max(5, min(175, target_angle))
        final_duty = 2.5 + (final_safe_angle / 180.0) * 10.0
        self.pwm.ChangeDutyCycle(final_duty)
        time.sleep(0.2)

        self.pwm.ChangeDutyCycle(0)
        self.current_angle = final_safe_angle

    def open_barrier(self):
        logger.info("Opening barrier (slow)...")
        self._sweep_angle(self.open_angle, duration=0.5)

    def close_barrier(self):
        logger.info("Closing barrier (slow)...")
        self._sweep_angle(self.close_angle, duration=0.5)

    def wait_and_close(self, ultrasonic):
        logger.info("Barrier raised. Waiting for vehicle pass...")
        time.sleep(2)

        clear_readings = 0

        while clear_readings < 5:
            if ultrasonic.is_obstacle(max_dist=15):
                logger.info("OBSTACLE UNDER BARRIER! Holding open...")
                clear_readings = 0
                time.sleep(0.5)
            else:
                clear_readings += 1
                time.sleep(0.2)

        logger.info("Path explicitly cleared. Closing in 2 seconds.")
        time.sleep(2)
        self.close_barrier()

    def cleanup(self):
        self._set_angle_instant(self.close_angle)
        time.sleep(0.5)
        self.pwm.stop()