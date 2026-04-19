from machine import ADC, Pin


class TMP36:
    def __init__(self, pin=26, vref=3.3):
        self.pin = pin
        self.vref = vref
        self.adc = ADC(Pin(pin))
        self.ok = False
        self.last_error = None

    def reconnect(self):
        try:
            self.adc = ADC(Pin(self.pin))
            self.ok = True
            self.last_error = None
            return True
        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return False

    def read(self):
        try:
            raw = self.adc.read_u16()
            voltage = raw * self.vref / 65535.0
            temperature_c = (voltage - 0.5) * 100.0

            self.ok = True
            self.last_error = None
            return {
                "ok": True,
                "raw": raw,
                "voltage_v": voltage,
                "temperature_c": temperature_c,
                "error": None,
            }
        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return {
                "ok": False,
                "raw": None,
                "voltage_v": None,
                "temperature_c": None,
                "error": str(e),
            }
