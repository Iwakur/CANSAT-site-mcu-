from machine import Pin
import neopixel
import utime


class StatusLEDs:
    def __init__(self, pin_num=8, count=4, brightness=20):
        self.pin_num = pin_num
        self.count = count
        self.brightness = brightness
        self.np = neopixel.NeoPixel(Pin(self.pin_num), self.count)

        # basic colors
        self.OFF = (0, 0, 0)
        self.RED = (brightness, 0, 0)
        self.GREEN = (0, brightness, 0)
        self.YELLOW = (brightness, brightness, 0)
        self.BLUE = (0, 0, brightness)
        self.ORANGE = (brightness, brightness // 2, 0)

        self.clear()

    # -------------------------
    # LOW LEVEL
    # -------------------------
    def _set(self, index, color):
        if 0 <= index < self.count:
            self.np[index] = color

    def show(self):
        self.np.write()

    def clear(self):
        for i in range(self.count):
            self.np[i] = self.OFF
        self.show()

    # -------------------------
    # SIMPLE STATES
    # -------------------------
    def off(self, index):
        self._set(index, self.OFF)
        self.show()

    def ok(self, index):
        self._set(index, self.GREEN)
        self.show()

    def fail(self, index):
        self._set(index, self.RED)
        self.show()

    def checking(self, index):
        self._set(index, self.YELLOW)
        self.show()

    def warn(self, index):
        self._set(index, self.ORANGE)
        self.show()

    def info(self, index):
        self._set(index, self.BLUE)
        self.show()

    # -------------------------
    # GLOBAL EFFECTS
    # -------------------------
    def all_color(self, color):
        for i in range(self.count):
            self.np[i] = color
        self.show()

    def blink_all(self, color, duration_ms=120):
        old = [self.np[i] for i in range(self.count)]
        self.all_color(color)
        utime.sleep_ms(duration_ms)
        for i in range(self.count):
            self.np[i] = old[i]
        self.show()

    def startup_test(self):
        for i in range(self.count):
            self._set(i, self.YELLOW)
            self.show()
            utime.sleep_ms(120)
            self._set(i, self.OFF)
        self.show()
