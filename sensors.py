import RPi.GPIO as GPIO
import time
import logging

logger = logging.getLogger(__name__)


class PIRSensor:
    def __init__(self, pin=17):
        self.pin = pin
        self.last_detection = 0
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)
        time.sleep(2)

    def is_detected(self):
        if GPIO.input(self.pin) == GPIO.HIGH:
            now = time.time()
            if now - self.last_detection > 3:
                self.last_detection = now
                return True
        return False


class UltrasonicSensor:
    def __init__(self, trig=23, echo=24):
        self.trig = trig
        self.echo = echo
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.trig, GPIO.OUT)
        GPIO.setup(self.echo, GPIO.IN)
        GPIO.output(self.trig, False)

    def get_distance(self):
        GPIO.output(self.trig, True)
        time.sleep(0.00001)
        GPIO.output(self.trig, False)

        timeout = time.time()
        start = time.time()
        end = time.time()

        while GPIO.input(self.echo) == 0:
            start = time.time()
            if start - timeout > 0.1:
                return 999

        while GPIO.input(self.echo) == 1:
            end = time.time()
            if end - start > 0.1:
                return 999

        dist = ((end - start) * 34300) / 2
        return round(dist, 1)

    def is_obstacle(self, max_dist=100):
        dist = self.get_distance()
        return dist < max_dist