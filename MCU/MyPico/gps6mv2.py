from machine import Pin, UART
import utime


def _safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def _nmea_to_decimal(raw, direction):
    if not raw or not direction:
        return None

    try:
        value = float(raw)
        degrees = int(value // 100)
        minutes = value - (degrees * 100)
        decimal = degrees + (minutes / 60.0)

        if direction in ("S", "W"):
            decimal = -decimal

        return decimal

    except Exception:
        return None


class GPS6MV2:
    def __init__(
        self,
        uart_id=1,
        rx_pin=5,
        tx_pin=None,
        baudrate=9600,
        timeout=100,
        debug=False
    ):
        self.uart_id = uart_id
        self.rx_pin = rx_pin
        self.tx_pin = tx_pin
        self.baudrate = baudrate
        self.timeout = timeout
        self.debug = debug

        self.uart = None
        self.ok = False
        self.last_error = None

        self._last_gga = None
        self._last_rmc = None
        self._last_line = None

        self._last_altitude_m = None
        self._last_altitude_ms = None

        self._init_uart()

    # -------------------------
    # Init / reconnect
    # -------------------------
    def _init_uart(self):
        try:
            kwargs = {
                "baudrate": self.baudrate,
                "bits": 8,
                "parity": None,
                "stop": 1,
                "timeout": self.timeout,
                "rx": Pin(self.rx_pin),
            }

            if self.tx_pin is not None:
                kwargs["tx"] = Pin(self.tx_pin)

            self.uart = UART(self.uart_id, **kwargs)

            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.uart = None
            self.ok = False
            self.last_error = str(e)
            return False

    def reconnect(self):
        self.ok = False
        self.last_error = None
        self._last_gga = None
        self._last_rmc = None
        self._last_line = None
        self._last_altitude_m = None
        self._last_altitude_ms = None
        return self._init_uart()

    # -------------------------
    # Parsing
    # -------------------------
    def _parse_gga(self, parts):
        if len(parts) < 10:
            return None

        fix_quality = _safe_int(parts[6], 0)
        satellites = _safe_int(parts[7], 0)
        hdop = _safe_float(parts[8], None)
        altitude_m = _safe_float(parts[9], None)

        lat = _nmea_to_decimal(parts[2], parts[3])
        lon = _nmea_to_decimal(parts[4], parts[5])

        return {
            "sentence": "GGA",
            "utc_time_raw": parts[1],
            "latitude": lat,
            "longitude": lon,
            "fix_quality": fix_quality,
            "satellites": satellites,
            "hdop": hdop,
            "altitude_m": altitude_m,
            "has_fix": fix_quality > 0,
        }

    def _parse_rmc(self, parts):
        if len(parts) < 10:
            return None

        status = parts[2]
        lat = _nmea_to_decimal(parts[3], parts[4])
        lon = _nmea_to_decimal(parts[5], parts[6])

        speed_knots = _safe_float(parts[7], 0.0)
        course_deg = _safe_float(parts[8], None)

        return {
            "sentence": "RMC",
            "utc_time_raw": parts[1],
            "status": status,
            "latitude": lat,
            "longitude": lon,
            "speed_knots": speed_knots,
            "speed_kmh": speed_knots * 1.852,
            "course_deg": course_deg,
            "date_raw": parts[9],
            "has_fix": status == "A",
        }

    def _parse_line(self, line):
        if not line:
            return None

        line = line.strip()
        if not line.startswith("$"):
            return None

        if "*" in line:
            line = line.split("*", 1)[0]

        parts = line.split(",")

        if parts[0] in ("$GPGGA", "$GNGGA"):
            return self._parse_gga(parts)

        if parts[0] in ("$GPRMC", "$GNRMC"):
            return self._parse_rmc(parts)

        return None

    def _read_available_lines(self):
        lines = []

        if self.uart is None:
            return lines

        while self.uart.any():
            raw = self.uart.readline()
            if not raw:
                break

            try:
                line = raw.decode("utf-8").strip()
            except Exception:
                continue

            if line:
                lines.append(line)

        return lines

    # -------------------------
    # Helpers
    # -------------------------
    def _estimate_vertical_speed(self, altitude_m):
        if altitude_m is None:
            return None

        now_ms = utime.ticks_ms()

        if self._last_altitude_m is None or self._last_altitude_ms is None:
            self._last_altitude_m = altitude_m
            self._last_altitude_ms = now_ms
            return None

        dt_ms = utime.ticks_diff(now_ms, self._last_altitude_ms)
        if dt_ms <= 0:
            return None

        dt_s = dt_ms / 1000.0
        vertical_speed_ms = (altitude_m - self._last_altitude_m) / dt_s

        self._last_altitude_m = altitude_m
        self._last_altitude_ms = now_ms

        return vertical_speed_ms

    def _format_utc_date(self, raw):
        if not raw or len(raw) < 6:
            return None

        try:
            day = int(raw[0:2])
            month = int(raw[2:4])
            year = 2000 + int(raw[4:6])
            return "{:04d}-{:02d}-{:02d}".format(year, month, day)
        except Exception:
            return None

    def _format_utc_time(self, raw):
        if not raw or len(raw) < 6:
            return None

        try:
            hour = int(raw[0:2])
            minute = int(raw[2:4])
            second = int(raw[4:6])
            return "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
        except Exception:
            return None

    # -------------------------
    # Public
    # -------------------------
    def read(self):
        try:
            if self.uart is None:
                if not self.reconnect():
                    return self._error_result(self.last_error or "gps uart init failed")

            got_anything = False

            for line in self._read_available_lines():
                got_anything = True
                self._last_line = line

                parsed = self._parse_line(line)
                if parsed is None:
                    continue

                if parsed["sentence"] == "GGA":
                    self._last_gga = parsed
                elif parsed["sentence"] == "RMC":
                    self._last_rmc = parsed

            if not got_anything and self._last_gga is None and self._last_rmc is None:
                raise RuntimeError("no GPS data")

            lat = None
            lon = None
            altitude_m = None
            satellites = None
            hdop = None
            speed_kmh = None
            horizontal_speed_kmh = None
            vertical_speed_ms = None
            course_deg = None
            utc_time_raw = None
            utc_date_raw = None
            utc_time = None
            utc_date = None
            fix = False

            if self._last_gga is not None:
                lat = self._last_gga["latitude"]
                lon = self._last_gga["longitude"]
                altitude_m = self._last_gga["altitude_m"]
                satellites = self._last_gga["satellites"]
                hdop = self._last_gga["hdop"]
                utc_time_raw = self._last_gga["utc_time_raw"]
                fix = fix or self._last_gga["has_fix"]

            if self._last_rmc is not None:
                if lat is None:
                    lat = self._last_rmc["latitude"]
                if lon is None:
                    lon = self._last_rmc["longitude"]
                speed_kmh = self._last_rmc["speed_kmh"]
                horizontal_speed_kmh = self._last_rmc["speed_kmh"]
                course_deg = self._last_rmc["course_deg"]
                utc_date_raw = self._last_rmc["date_raw"]
                if utc_time_raw is None:
                    utc_time_raw = self._last_rmc["utc_time_raw"]
                fix = fix or self._last_rmc["has_fix"]

            utc_time = self._format_utc_time(utc_time_raw)
            utc_date = self._format_utc_date(utc_date_raw)

            if altitude_m is not None:
                vertical_speed_ms = self._estimate_vertical_speed(altitude_m)

            result = {
                "ok": True,
                "connected": got_anything or (self._last_line is not None),
                "fix": fix,
                "latitude": lat,
                "longitude": lon,
                "altitude_m": altitude_m,
                "absolute_altitude_m": altitude_m,
                "satellites": satellites,
                "hdop": hdop,
                "speed_kmh": speed_kmh,
                "horizontal_speed_kmh": horizontal_speed_kmh,
                "vertical_speed_ms": vertical_speed_ms,
                "course_deg": course_deg,
                "compass_deg": course_deg,
                "utc_time_raw": utc_time_raw,
                "utc_date_raw": utc_date_raw,
                "utc_time": utc_time,
                "utc_date": utc_date,
                "rtc_update_ready": bool(utc_date and utc_time),
                "last_sentence": self._last_line,
            }

            self.ok = True
            self.last_error = None

            if self.debug and self._last_line:
                print("GPS RAW:", self._last_line)

            return result

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return self._error_result(str(e))

    def _error_result(self, error_text):
        return {
            "ok": False,
            "connected": False,
            "fix": False,
            "latitude": None,
            "longitude": None,
            "altitude_m": None,
            "absolute_altitude_m": None,
            "satellites": None,
            "hdop": None,
            "speed_kmh": None,
            "horizontal_speed_kmh": None,
            "vertical_speed_ms": None,
            "course_deg": None,
            "compass_deg": None,
            "utc_time_raw": None,
            "utc_date_raw": None,
            "utc_time": None,
            "utc_date": None,
            "rtc_update_ready": False,
            "last_sentence": self._last_line,
            "error": error_text,
        }