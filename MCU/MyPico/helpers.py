import utime

RFM_MAX_PAYLOAD_BYTES = 60
RFM_LINE_CHUNK_BYTES = 45
LED_COUNT = 4
LED_RTC = 0
LED_TMP36 = 1
LED_BME = 2
LED_MPU = 3
LED_SD = 0
LED_GPS = 1
LED_RFM = 2
LED_MAG = 3
LED_INIT_CHECK_MS = 20
LED_INIT_RESULT_MS = 40
LED_CYCLE_CHECK_MS = 10
LED_CYCLE_RESULT_MS = 20
LED_BETWEEN_CYCLES_MS = 20
LED_BLUE_BIP_MS = 15
LED_DARK_BIP_MS = 10
leds = None
GPS_RTC_UTC_OFFSET_HOURS = 2


def configure_helpers(
    rfm_max_payload_bytes=None,
    leds_obj=None,
    led_count=None,
    led_rtc=None,
    led_tmp36=None,
    led_bme=None,
    led_mpu=None,
    led_sd=None,
    led_gps=None,
    led_rfm=None,
    led_mag=None,
    led_init_check_ms=None,
    led_init_result_ms=None,
    led_cycle_check_ms=None,
    led_cycle_result_ms=None,
    led_between_cycles_ms=None,
    led_blue_bip_ms=None,
    led_dark_bip_ms=None,
):
    global RFM_MAX_PAYLOAD_BYTES, LED_COUNT, LED_RTC, LED_TMP36, LED_BME, LED_MPU
    global LED_SD, LED_GPS, LED_RFM, LED_MAG, LED_INIT_CHECK_MS, LED_INIT_RESULT_MS
    global LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS, LED_BETWEEN_CYCLES_MS
    global LED_BLUE_BIP_MS, LED_DARK_BIP_MS, leds

    if rfm_max_payload_bytes is not None:
        RFM_MAX_PAYLOAD_BYTES = rfm_max_payload_bytes
    if leds_obj is not None:
        leds = leds_obj
    if led_count is not None:
        LED_COUNT = led_count
    if led_rtc is not None:
        LED_RTC = led_rtc
    if led_tmp36 is not None:
        LED_TMP36 = led_tmp36
    if led_bme is not None:
        LED_BME = led_bme
    if led_mpu is not None:
        LED_MPU = led_mpu
    if led_sd is not None:
        LED_SD = led_sd
    if led_gps is not None:
        LED_GPS = led_gps
    if led_rfm is not None:
        LED_RFM = led_rfm
    if led_mag is not None:
        LED_MAG = led_mag
    if led_init_check_ms is not None:
        LED_INIT_CHECK_MS = led_init_check_ms
    if led_init_result_ms is not None:
        LED_INIT_RESULT_MS = led_init_result_ms
    if led_cycle_check_ms is not None:
        LED_CYCLE_CHECK_MS = led_cycle_check_ms
    if led_cycle_result_ms is not None:
        LED_CYCLE_RESULT_MS = led_cycle_result_ms
    if led_between_cycles_ms is not None:
        LED_BETWEEN_CYCLES_MS = led_between_cycles_ms
    if led_blue_bip_ms is not None:
        LED_BLUE_BIP_MS = led_blue_bip_ms
    if led_dark_bip_ms is not None:
        LED_DARK_BIP_MS = led_dark_bip_ms

def now_text(rtc_data):
    if rtc_data["ok"]:
        return rtc_data["datetime"]
    return "RTC_ERR"


def log_line(timestamp, level, source, message):
    return "{} [{}] {} {}".format(timestamp, level, source, message)


def fmt_value(value, decimals=None, unit=""):
    if value is None:
        return "None"
    if decimals is None:
        return "{}{}".format(value, unit)
    fmt = "{:." + str(decimals) + "f}{}"
    return fmt.format(value, unit)


def error_result_rtc(error_text):
    return {
        "ok": False,
        "year": None,
        "month": None,
        "day": None,
        "weekday": None,
        "hour": None,
        "minute": None,
        "second": None,
        "date": None,
        "time": None,
        "datetime": None,
        "error": error_text,
    }


def error_result_bme(error_text):
    return {
        "ok": False,
        "temperature_c": None,
        "pressure_hpa": None,
        "humidity_pct": None,
        "altitude_m": None,
        "gas_ohms": None,
        "gas_valid": False,
        "error": error_text,
    }


def error_result_mpu(error_text):
    return {
        "ok": False,
        "ax": None,
        "ay": None,
        "az": None,
        "gx": None,
        "gy": None,
        "gz": None,
        "temp": None,
        "pitch": None,
        "roll": None,
        "error": error_text,
    }


def error_result_tmp36(error_text):
    return {
        "ok": False,
        "raw": None,
        "voltage_v": None,
        "temperature_c": None,
        "error": error_text,
    }


def error_result_mag(error_text):
    return {
        "ok": False,
        "chip": None,
        "x": None,
        "y": None,
        "z": None,
        "heading_deg": None,
        "data_ready": False,
        "overflow": False,
        "error": error_text,
    }


def error_result_gps(error_text):
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
        "last_sentence": None,
        "error": error_text,
    }


class StartupModule:
    def __init__(self, name, factory, error_result):
        self.name = name
        self.factory = factory
        self.error_result = error_result
        self.module = None
        self.ok = False
        self.last_error = None
        self.reconnect()

    def __getattr__(self, name):
        if self.module is not None:
            return getattr(self.module, name)
        raise AttributeError(name)

    def reconnect(self):
        try:
            if self.module is not None and hasattr(self.module, "reconnect"):
                result = self.module.reconnect()
                self.ok = getattr(self.module, "ok", bool(result))
                self.last_error = getattr(self.module, "last_error", None)
                return self.ok

            self.module = self.factory()
            self.ok = getattr(self.module, "ok", True)
            self.last_error = getattr(self.module, "last_error", None)
            return self.ok

        except Exception as e:
            self.module = None
            self.ok = False
            self.last_error = str(e)
            print("{} INIT ERROR: {}".format(self.name, self.last_error))
            return False

    def read(self):
        if self.module is None:
            return self.error_result(self.last_error or "{} not initialized".format(self.name))

        try:
            result = self.module.read()
            self.ok = result["ok"] if isinstance(result, dict) and "ok" in result else getattr(self.module, "ok", True)
            self.last_error = getattr(self.module, "last_error", None)
            return result
        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return self.error_result(self.last_error)

    def write_data(self, line):
        if self.module is None and not self.reconnect():
            return False
        if self.module is None or not hasattr(self.module, "write_data"):
            return False
        result = self.module.write_data(line)
        self.ok = getattr(self.module, "ok", bool(result))
        self.last_error = getattr(self.module, "last_error", None)
        return result

    def write_log(self, line):
        if self.module is None and not self.reconnect():
            return False
        if self.module is None or not hasattr(self.module, "write_log"):
            return False
        result = self.module.write_log(line)
        self.ok = getattr(self.module, "ok", bool(result))
        self.last_error = getattr(self.module, "last_error", None)
        return result

    def send_line(self, text):
        if self.module is None and not self.reconnect():
            return False
        if self.module is None or not hasattr(self.module, "send_line"):
            return False
        result = self.module.send_line(text)
        self.ok = getattr(self.module, "ok", bool(result))
        self.last_error = getattr(self.module, "last_error", None)
        return result

    def debug_status(self):
        if self.module is None or not hasattr(self.module, "debug_status"):
            return {
                "ok": False,
                "error": self.last_error or "{} not initialized".format(self.name),
            }
        return self.module.debug_status()


class NullSDModule:
    def __init__(self, error_text):
        self.ok = False
        self.last_error = error_text

    def reconnect(self):
        return False

    def write_data(self, line):
        return False

    def write_log(self, line):
        return False


class NullRFM69:
    def __init__(self, error_text):
        self.ok = False
        self.last_error = error_text

    def reconnect(self):
        return False

    def send_line(self, text):
        return False

    def debug_status(self):
        return {
            "ok": False,
            "error": self.last_error,
        }


def fmt_rfm_int(value, width=None):
    if value is None:
        return "0"

    try:
        number = int(round(value))
    except Exception:
        return "0"

    text = str(number)

    if width is not None and number >= 0:
        while len(text) < width:
            text = "0" + text

    return text


def scale_int(value, factor=1):
    if value is None:
        return "0"
    try:
        return str(int(round(value * factor)))
    except Exception:
        return "0"


def short_time(ts):
    if ts == "RTC_ERR":
        return "RTCERR"
    return ts[-8:].replace(":", "")


def short_date(ts):
    if ts == "RTC_ERR":
        return "0"
    return ts[:10].replace("-", "")


def weekday_from_date(year, month, day):
    # Sakamoto algorithm: returns DS1302 weekday 1..7, Monday=1.
    offsets = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if month < 3:
        year -= 1
    sunday_based = (year + year // 4 - year // 100 + year // 400 + offsets[month - 1] + day) % 7
    return 7 if sunday_based == 0 else sunday_based


def is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if month == 2:
        return 29 if is_leap_year(year) else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def add_hours_to_datetime(year, month, day, hour, offset_hours):
    hour += offset_hours

    while hour >= 24:
        hour -= 24
        day += 1
        if day > days_in_month(year, month):
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1

    while hour < 0:
        hour += 24
        day -= 1
        if day < 1:
            month -= 1
            if month < 1:
                month = 12
                year -= 1
            day = days_in_month(year, month)

    return year, month, day, hour


def sync_rtc_from_gps(rtc, gps_data):
    if not gps_data["ok"] or not gps_data["rtc_update_ready"]:
        return False
    try:
        date_text = gps_data["utc_date"]
        time_text = gps_data["utc_time"]
        year = int(date_text[0:4])
        month = int(date_text[5:7])
        day = int(date_text[8:10])
        hour = int(time_text[0:2])
        minute = int(time_text[3:5])
        second = int(time_text[6:8])
        year, month, day, hour = add_hours_to_datetime(
            year,
            month,
            day,
            hour,
            GPS_RTC_UTC_OFFSET_HOURS
        )
        weekday = weekday_from_date(year, month, day)
        return rtc.set_datetime(year, month, day, weekday, hour, minute, second)
    except Exception:
        return False


def retry_due(last_ms, interval_ms):
    return utime.ticks_diff(utime.ticks_ms(), last_ms) >= interval_ms


def format_bme_text(bme_data):
    if not bme_data["ok"]:
        return "BME[ERR]"
    return "BME[T={} P={} H={} G={}ohm A={} GV={}]".format(
        fmt_value(bme_data["temperature_c"], 1, "C"),
        fmt_value(bme_data["pressure_hpa"], 1, "hPa"),
        fmt_value(bme_data["humidity_pct"], 1, "%"),
        fmt_value(bme_data["gas_ohms"]),
        fmt_value(bme_data["altitude_m"], 1, "m"),
        1 if bme_data.get("gas_valid") else 0,
    )


def format_mpu_text(mpu_data):
    if not mpu_data["ok"]:
        return "MPU[ERR]"
    return "MPU[Ax={} Ay={} Az={} Gx={} Gy={} Gz={} Tmp={} Pit={} Rol={}]".format(
        fmt_value(mpu_data["ax"], 2, "g"),
        fmt_value(mpu_data["ay"], 2, "g"),
        fmt_value(mpu_data["az"], 2, "g"),
        fmt_value(mpu_data["gx"], 2, "dps"),
        fmt_value(mpu_data["gy"], 2, "dps"),
        fmt_value(mpu_data["gz"], 2, "dps"),
        fmt_value(mpu_data["temp"], 1, "C"),
        fmt_value(mpu_data["pitch"], 1, "deg"),
        fmt_value(mpu_data["roll"], 1, "deg")
    )


def format_tmp36_text(tmp_data):
    if not tmp_data["ok"]:
        return "TMP36[ERR:{}]".format(tmp_data.get("error", "unknown"))
    return "TMP36[T={} V={} Raw={}]".format(
        fmt_value(tmp_data["temperature_c"], 1, "C"),
        fmt_value(tmp_data["voltage_v"], 3, "V"),
        fmt_value(tmp_data["raw"]),
    )


def format_mag_text(mag_data):
    if not mag_data["ok"]:
        return "MAG[ERR:{}]".format(mag_data.get("error", "unknown"))
    return "MAG[X={} Y={} Z={} H={} CHIP={}]".format(
        fmt_value(mag_data["x"]),
        fmt_value(mag_data["y"]),
        fmt_value(mag_data["z"]),
        fmt_value(mag_data["heading_deg"], 1, "deg"),
        mag_data["chip"]
    )


def format_gps_text(gps_data):
    if not gps_data["ok"]:
        return "GPS[ERR:{}]".format(gps_data.get("error", "unknown"))
    return "GPS[FIX={} SAT={} LAT={} LON={} ALT={} HDOP={} SPD={} CRS={} VS={}]".format(
        int(gps_data["fix"]),
        fmt_value(gps_data["satellites"]),
        fmt_value(gps_data["latitude"]),
        fmt_value(gps_data["longitude"]),
        fmt_value(gps_data["absolute_altitude_m"], 1, "m"),
        fmt_value(gps_data.get("hdop")),
        fmt_value(gps_data.get("speed_kmh"), 1, "kmh"),
        fmt_value(gps_data.get("course_deg"), 1, "deg"),
        fmt_value(gps_data.get("vertical_speed_ms"), 2, "ms"),
    )


def format_telemetry_line(ts, tmp_data, bme_data, mpu_data, mag_data, gps_data, sample_id=None):
    prefix = "T={}".format(ts)
    if sample_id is not None:
        prefix = "SID={} {}".format(sample_id, prefix)

    return "{} {} {} {} {} {}".format(
        prefix,
        format_tmp36_text(tmp_data),
        format_bme_text(bme_data),
        format_mpu_text(mpu_data),
        format_mag_text(mag_data),
        format_gps_text(gps_data)
    )


def format_rfm_line(ts, tmp_data, bme_data, mag_data, gps_data):
    time_text = ts[-8:].replace(":", "") if ts != "RTC_ERR" else "RTCERR"
    tmp_temp = tmp_data["temperature_c"] if tmp_data["ok"] else None
    bme_temp = bme_data["temperature_c"] if bme_data["ok"] else None
    bme_hum = bme_data["humidity_pct"] if bme_data["ok"] else None
    mag_x = mag_data["x"] if mag_data["ok"] else None
    mag_y = mag_data["y"] if mag_data["ok"] else None
    mag_z = mag_data["z"] if mag_data["ok"] else None
    gps_fix = int(gps_data["fix"]) if gps_data["ok"] else 0
    gps_sat = gps_data["satellites"] if gps_data["ok"] else None

    return "{},TMP{},BT{},BH{},M{},{},{},G{},S{}".format(
        time_text,
        fmt_rfm_int(tmp_temp),
        fmt_rfm_int(bme_temp),
        fmt_rfm_int(bme_hum),
        fmt_rfm_int(mag_x),
        fmt_rfm_int(mag_y),
        fmt_rfm_int(mag_z),
        gps_fix,
        fmt_rfm_int(gps_sat, 2)
    )


def rfm_bool(data):
    return 1 if data.get("ok") else 0


def rfm_scale_int(value, factor=1):
    if value is None:
        return "x"
    return scale_int(value, factor)


def build_env_packet(sample_id, ts, tmp_data, bme_data):
    return "E,{},{},{},{},{},{},{},{},{},{},{}".format(
        sample_id,
        short_date(ts),
        short_time(ts),
        rfm_bool(tmp_data),
        rfm_bool(bme_data),
        rfm_scale_int(tmp_data["temperature_c"] if tmp_data["ok"] else None, 10),
        rfm_scale_int(tmp_data["voltage_v"] if tmp_data["ok"] else None, 1000),
        rfm_scale_int(tmp_data["raw"] if tmp_data["ok"] else None),
        rfm_scale_int(bme_data["temperature_c"] if bme_data["ok"] else None, 10),
        rfm_scale_int(bme_data["pressure_hpa"] if bme_data["ok"] else None, 10),
        rfm_scale_int(bme_data["humidity_pct"] if bme_data["ok"] else None, 10),
    )


def build_bme_packet(sample_id, bme_data):
    return "B,{},{},{},{},{}".format(
        sample_id,
        rfm_bool(bme_data),
        rfm_scale_int(bme_data["gas_ohms"] if bme_data["ok"] else None),
        rfm_scale_int(bme_data["altitude_m"] if bme_data["ok"] else None, 10),
        1 if bme_data.get("gas_valid") else 0,
    )


def build_accel_packet(sample_id, mpu_data):
    return "A,{},{},{},{},{},{},{},{}".format(
        sample_id,
        rfm_bool(mpu_data),
        rfm_scale_int(mpu_data["ax"] if mpu_data["ok"] else None, 1000),
        rfm_scale_int(mpu_data["ay"] if mpu_data["ok"] else None, 1000),
        rfm_scale_int(mpu_data["az"] if mpu_data["ok"] else None, 1000),
        rfm_scale_int(mpu_data["gx"] if mpu_data["ok"] else None, 100),
        rfm_scale_int(mpu_data["gy"] if mpu_data["ok"] else None, 100),
        rfm_scale_int(mpu_data["gz"] if mpu_data["ok"] else None, 100),
    )


def build_orientation_packet(sample_id, mpu_data):
    return "O,{},{},{},{},{}".format(
        sample_id,
        rfm_bool(mpu_data),
        rfm_scale_int(mpu_data["temp"] if mpu_data["ok"] else None, 10),
        rfm_scale_int(mpu_data["pitch"] if mpu_data["ok"] else None, 10),
        rfm_scale_int(mpu_data["roll"] if mpu_data["ok"] else None, 10),
    )


def build_mag_packet(sample_id, mag_data):
    return "C,{},{},{},{},{},{},{}".format(
        sample_id,
        rfm_bool(mag_data),
        rfm_scale_int(mag_data["x"] if mag_data["ok"] else None),
        rfm_scale_int(mag_data["y"] if mag_data["ok"] else None),
        rfm_scale_int(mag_data["z"] if mag_data["ok"] else None),
        rfm_scale_int(mag_data["heading_deg"] if mag_data["ok"] else None, 10),
        mag_data["chip"] if mag_data["ok"] else "0",
    )


def build_gps_packet(sample_id, gps_data):
    return "G,{},{},{},{},{},{},{},{},{},{},{}".format(
        sample_id,
        rfm_bool(gps_data),
        int(gps_data["fix"]) if gps_data["ok"] else 0,
        rfm_scale_int(gps_data["satellites"] if gps_data["ok"] else None),
        rfm_scale_int(gps_data["latitude"] if gps_data["ok"] else None, 1000000),
        rfm_scale_int(gps_data["longitude"] if gps_data["ok"] else None, 1000000),
        rfm_scale_int(gps_data["absolute_altitude_m"] if gps_data["ok"] else None, 10),
        rfm_scale_int(gps_data.get("hdop") if gps_data["ok"] else None, 100),
        rfm_scale_int(gps_data.get("speed_kmh") if gps_data["ok"] else None, 10),
        rfm_scale_int(gps_data.get("course_deg") if gps_data["ok"] else None, 10),
        rfm_scale_int(gps_data.get("vertical_speed_ms") if gps_data["ok"] else None, 100),
    )


def build_line_packets(sample_id, line):
    chunks = [
        line[i:i + RFM_LINE_CHUNK_BYTES]
        for i in range(0, len(line), RFM_LINE_CHUNK_BYTES)
    ]
    if not chunks:
        chunks = [""]

    total = len(chunks)
    packets = []
    for index, chunk in enumerate(chunks, 1):
        packets.append("L,{},{},{},{}".format(sample_id, index, total, chunk))
    return packets


def build_rfm_packets(sample_id, telemetry_line, ts, tmp_data, bme_data, mpu_data, mag_data, gps_data):
    return [
        build_env_packet(sample_id, ts, tmp_data, bme_data),
        build_bme_packet(sample_id, bme_data),
        build_accel_packet(sample_id, mpu_data),
        build_orientation_packet(sample_id, mpu_data),
        build_mag_packet(sample_id, mag_data),
        build_gps_packet(sample_id, gps_data),
    ]


def fit_rfm_payload(text):
    payload = text.encode("utf-8")

    if len(payload) <= RFM_MAX_PAYLOAD_BYTES:
        return text

    return payload[:RFM_MAX_PAYLOAD_BYTES].decode("utf-8")


def rfm_debug_line(timestamp, status):
    if status["ok"]:
        version_note = "OK" if status["version_ok"] else "BAD"
        return (
            "{} [DEBUG] RFM69 VERSION=0x{:02X} OPMODE=0x{:02X} "
            "IRQ1=0x{:02X} IRQ2=0x{:02X} VERSION_STATUS={}"
        ).format(
            timestamp,
            status["version"],
            status["opmode"],
            status["irq1"],
            status["irq2"],
            version_note
        )

    return "{} [DEBUG] RFM69 DEBUG_ERROR {}".format(
        timestamp,
        status.get("error", "unknown")
    )


def led_off(index):
    if hasattr(leds, "off"):
        leds.off(index)
        return
    if hasattr(leds, "set_off"):
        leds.set_off(index)
        return
    if hasattr(leds, "clear"):
        leds.clear(index)
        return


def leds_all_off():
    if hasattr(leds, "all_off"):
        leds.all_off()
        return
    if hasattr(leds, "off_all"):
        leds.off_all()
        return
    for i in range(LED_COUNT):
        led_off(i)


def show_led_status(index, is_ok, check_ms, result_ms):
    leds.checking(index)
    utime.sleep_ms(check_ms)

    if is_ok:
        leds.ok(index)
    else:
        leds.fail(index)

    utime.sleep_ms(result_ms)


def gps_led_state(gps_data):
    if gps_data["ok"] and gps_data["connected"] and gps_data["fix"]:
        return "fix"
    if gps_data["ok"] and gps_data["connected"]:
        return "connected"
    return "fail"


def show_gps_status(gps_state, check_ms, result_ms):
    leds.checking(LED_GPS)
    utime.sleep_ms(check_ms)

    if gps_state == "fix":
        leds.ok(LED_GPS)
    elif gps_state == "connected":
        leds.info(LED_GPS)
    else:
        leds.fail(LED_GPS)

    utime.sleep_ms(result_ms)


def blue_bip():
    leds.blink_all(leds.BLUE, LED_BLUE_BIP_MS)


def dark_bip():
    leds_all_off()
    utime.sleep_ms(LED_DARK_BIP_MS)


def show_two_status_cycles(status_map):
    # Cycle 1: RTC, TMP36, BME, MPU
    show_led_status(LED_RTC, status_map["rtc"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_TMP36, status_map["tmp36"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_BME, status_map["bme"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_MPU, status_map["mpu"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)

    blue_bip()
    utime.sleep_ms(LED_BETWEEN_CYCLES_MS)

    # Cycle 2: SD, GPS, RFM, MAG
    led_off(LED_MAG)
    show_led_status(LED_SD, status_map["sd"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_gps_status(status_map["gps"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_RFM, status_map["rfm"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_MAG, status_map["mag"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)

    led_off(LED_MAG)
    dark_bip()


def show_init_module(index, ok):
    leds.checking(index)
    utime.sleep_ms(LED_INIT_CHECK_MS)

    if ok:
        leds.ok(index)
    else:
        leds.fail(index)

    utime.sleep_ms(LED_INIT_RESULT_MS)


def show_init_cycles(init_status_map):
    # cycle 1
    show_init_module(LED_RTC, init_status_map["rtc"])
    show_init_module(LED_TMP36, init_status_map["tmp36"])
    show_init_module(LED_BME, init_status_map["bme"])
    show_init_module(LED_MPU, init_status_map["mpu"])

    blue_bip()
    utime.sleep_ms(LED_BETWEEN_CYCLES_MS)

    # cycle 2
    led_off(LED_MAG)
    show_init_module(LED_SD, init_status_map["sd"])
    show_gps_status(init_status_map["gps"], LED_INIT_CHECK_MS, LED_INIT_RESULT_MS)
    show_init_module(LED_RFM, init_status_map["rfm"])
    show_init_module(LED_MAG, init_status_map["mag"])

    led_off(LED_MAG)
    dark_bip()


