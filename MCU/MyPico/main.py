from machine import Pin, I2C
import utime

from rtc import DS1302
from bmp580 import BMP580
from bme688 import BME688
from mpu6500 import MPU6500
from gy271 import GY271
from gps6mv2 import GPS6MV2
from sdcard import SDModule
from status_leds import StatusLEDs
from rfm69 import RFM69


# =========================
# CONFIG
# =========================

# RTC pins
RTC_CLK_PIN = 2
RTC_DAT_PIN = 3
RTC_RST_PIN = 4

# Shared I2C bus
I2C_ID = 0
I2C_SCL_PIN = 1
I2C_SDA_PIN = 0
I2C_FREQ = 100000

# BMP580
BMP_ADDRESS = None
BMP_SEA_LEVEL_PRESSURE = 1013.25
 
# BME688
BME_ADDRESS = 0x77
BME_SEA_LEVEL_PRESSURE = 1013.25

# MPU6500
MPU_ADDRESS = 0x68
MPU_DO_CALIBRATION = True
MPU_CALIBRATION_SAMPLES = 300

# Magnetometer (HW-246 / GY-271)
MAG_ADDRESS = None

# GPS (GY-GPS6MV2 / NEO-6M)
GPS_UART_ID = 1
GPS_RX_PIN = 5
GPS_TX_PIN = None
GPS_BAUDRATE = 9600
GPS_DEBUG = False

# SD card SPI
SD_SCK_PIN = 27
SD_MOSI_PIN = 28
SD_MISO_PIN = 26
SD_CS_PIN = 29
SD_BAUDRATE = 500000

# LED module
LED_PIN = 15
LED_COUNT = 4

# LED cycle 1
LED_RTC = 0
LED_BMP = 1
LED_BME = 2
LED_MPU = 3

# LED cycle 2
LED_SD = 0
LED_GPS = 1
LED_RFM = 2
LED_MAG = 3

# RFM69
RFM_SCK_PIN = SD_SCK_PIN
RFM_MOSI_PIN = SD_MOSI_PIN
RFM_MISO_PIN = SD_MISO_PIN
RFM_CS_PIN = 14
RFM_RST_PIN = None
RFM_FREQ_MHZ = 434.0
RFM_BITRATE = 4800
RFM_TX_POWER_DBM = 13
RFM_MAX_PAYLOAD_BYTES = 60
RFM_LOG_EVERY_SEND = True
DEBUG_TELEMETRY = True

# Main loop
LOOP_DELAY_MS = 200
SENSOR_RECONNECT_INTERVAL_MS = 3000
RFM_RECONNECT_INTERVAL_MS = 3000

# =========================
# LED TIMINGS
# =========================
LED_INIT_CHECK_MS = 60
LED_INIT_RESULT_MS = 100

LED_CYCLE_CHECK_MS = 30
LED_CYCLE_RESULT_MS = 60

LED_BETWEEN_CYCLES_MS = 60
LED_BLUE_BIP_MS = 40
LED_DARK_BIP_MS = 10

LED_MAIN_ERROR_RED_MS = 120



# =========================
# HELPERS
# =========================
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


def error_result_bmp(error_text):
    return {
        "ok": False,
        "temperature_c": None,
        "pressure_hpa": None,
        "altitude_m": None,
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
        return "?"

    try:
        number = int(round(value))
    except Exception:
        return "?"

    text = str(number)

    if width is not None and number >= 0:
        while len(text) < width:
            text = "0" + text

    return text


def scale_int(value, factor=1):
    if value is None:
        return "?"
    try:
        return str(int(round(value * factor)))
    except Exception:
        return "?"


def short_time(ts):
    if ts == "RTC_ERR":
        return "RTCERR"
    return ts[-8:].replace(":", "")


def weekday_from_date(year, month, day):
    # Sakamoto algorithm: returns DS1302 weekday 1..7, Monday=1.
    offsets = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if month < 3:
        year -= 1
    sunday_based = (year + year // 4 - year // 100 + year // 400 + offsets[month - 1] + day) % 7
    return 7 if sunday_based == 0 else sunday_based


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
        weekday = weekday_from_date(year, month, day)
        return rtc.set_datetime(year, month, day, weekday, hour, minute, second)
    except Exception:
        return False


def retry_due(last_ms, interval_ms):
    return utime.ticks_diff(utime.ticks_ms(), last_ms) >= interval_ms


def format_bmp_text(bmp_data):
    if not bmp_data["ok"]:
        return "BMP[ERR:{}]".format(bmp_data.get("error", "unknown"))
    return "BMP[T={} P={} A={}]".format(
        fmt_value(bmp_data["temperature_c"], 1, "C"),
        fmt_value(bmp_data["pressure_hpa"], 1, "hPa"),
        fmt_value(bmp_data["altitude_m"], 1, "m")
    )


def format_bme_text(bme_data):
    if not bme_data["ok"]:
        return "BME[ERR]"
    return "BME[T={} P={} H={} G={}ohm A={}]".format(
        fmt_value(bme_data["temperature_c"], 1, "C"),
        fmt_value(bme_data["pressure_hpa"], 1, "hPa"),
        fmt_value(bme_data["humidity_pct"], 1, "%"),
        fmt_value(bme_data["gas_ohms"]),
        fmt_value(bme_data["altitude_m"], 1, "m")
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
    return "GPS[FIX={} SAT={} LAT={} LON={} ALT={}]".format(
        int(gps_data["fix"]),
        fmt_value(gps_data["satellites"]),
        fmt_value(gps_data["latitude"]),
        fmt_value(gps_data["longitude"]),
        fmt_value(gps_data["absolute_altitude_m"], 1, "m"),
    )


def format_telemetry_line(ts, bmp_data, bme_data, mpu_data, mag_data, gps_data):
    return "T={} {} {} {} {} {}".format(
        ts,
        format_bmp_text(bmp_data),
        format_bme_text(bme_data),
        format_mpu_text(mpu_data),
        format_mag_text(mag_data),
        format_gps_text(gps_data)
    )


def format_rfm_line(ts, bmp_data, bme_data, gps_data, mag_data):
    time_text = ts[-8:].replace(":", "") if ts != "RTC_ERR" else "RTCERR"
    bmp_alt = bmp_data["altitude_m"] if bmp_data["ok"] else None
    bme_temp = bme_data["temperature_c"] if bme_data["ok"] else None
    bme_hum = bme_data["humidity_pct"] if bme_data["ok"] else None
    gps_fix = int(gps_data["fix"]) if gps_data["ok"] else 0
    gps_sat = gps_data["satellites"] if gps_data["ok"] else None
    mag_x = mag_data["x"] if mag_data["ok"] else None
    mag_y = mag_data["y"] if mag_data["ok"] else None
    mag_z = mag_data["z"] if mag_data["ok"] else None

    return "{},A{},T{},H{},G{},S{},M{},{},{}".format(
        time_text,
        fmt_rfm_int(bmp_alt),
        fmt_rfm_int(bme_temp),
        fmt_rfm_int(bme_hum),
        gps_fix,
        fmt_rfm_int(gps_sat, 2),
        fmt_rfm_int(mag_x),
        fmt_rfm_int(mag_y),
        fmt_rfm_int(mag_z)
    )


def build_env_packet(sample_id, ts, bmp_data, bme_data):
    bmp_temp = bmp_data["temperature_c"] if bmp_data["ok"] else None
    bmp_pressure = bmp_data["pressure_hpa"] if bmp_data["ok"] else None
    bme_temp = bme_data["temperature_c"] if bme_data["ok"] else None
    bme_pressure = bme_data["pressure_hpa"] if bme_data["ok"] else None
    bme_humidity = bme_data["humidity_pct"] if bme_data["ok"] else None
    bme_gas = bme_data["gas_ohms"] if bme_data["ok"] else None

    return "E,{},{},{},{},{},{},{},{}".format(
        sample_id,
        short_time(ts),
        scale_int(bmp_temp, 10),
        scale_int(bmp_pressure, 10),
        scale_int(bme_temp, 10),
        scale_int(bme_pressure, 10),
        scale_int(bme_humidity, 10),
        scale_int(bme_gas),
    )


def build_motion_packet(sample_id, mpu_data):
    return "M,{},A,{},{},{},{},{},{}".format(
        sample_id,
        scale_int(mpu_data["ax"] if mpu_data["ok"] else None, 1000),
        scale_int(mpu_data["ay"] if mpu_data["ok"] else None, 1000),
        scale_int(mpu_data["az"] if mpu_data["ok"] else None, 1000),
        scale_int(mpu_data["gx"] if mpu_data["ok"] else None, 100),
        scale_int(mpu_data["gy"] if mpu_data["ok"] else None, 100),
        scale_int(mpu_data["gz"] if mpu_data["ok"] else None, 100),
    )


def build_mag_packet(sample_id, mag_data):
    return "M,{},C,{},{},{}".format(
        sample_id,
        scale_int(mag_data["x"] if mag_data["ok"] else None),
        scale_int(mag_data["y"] if mag_data["ok"] else None),
        scale_int(mag_data["z"] if mag_data["ok"] else None),
    )


def build_gps_packet(sample_id, gps_data):
    return "G,{},{},{},{},{},{},{},{}".format(
        sample_id,
        int(gps_data["fix"]) if gps_data["ok"] else 0,
        scale_int(gps_data["satellites"] if gps_data["ok"] else None),
        scale_int(gps_data["latitude"] if gps_data["ok"] else None, 1000000),
        scale_int(gps_data["longitude"] if gps_data["ok"] else None, 1000000),
        scale_int(gps_data["absolute_altitude_m"] if gps_data["ok"] else None, 10),
        gps_data["utc_date"] if gps_data["ok"] and gps_data["utc_date"] else "?",
        gps_data["utc_time"] if gps_data["ok"] and gps_data["utc_time"] else "?",
    )


def build_rfm_packets(sample_id, ts, bmp_data, bme_data, mpu_data, mag_data, gps_data, send_gps):
    packets = [
        build_env_packet(sample_id, ts, bmp_data, bme_data),
        build_motion_packet(sample_id, mpu_data),
    ]
    if send_gps:
        packets.append(build_gps_packet(sample_id, gps_data))
    packets.append(build_mag_packet(sample_id, mag_data))
    return packets


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
    # Cycle 1: RTC, BMP, BME, MPU
    show_led_status(LED_RTC, status_map["rtc"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_BMP, status_map["bmp"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
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
    show_init_module(LED_BMP, init_status_map["bmp"])
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


# =========================
# INIT LEDS
# =========================
leds = StatusLEDs(pin_num=LED_PIN, count=LED_COUNT, brightness=20)
leds.startup_test()


# =========================
# INIT I2C
# =========================
i2c = I2C(
    I2C_ID,
    scl=Pin(I2C_SCL_PIN),
    sda=Pin(I2C_SDA_PIN),
    freq=I2C_FREQ
)

print("I2C devices:", [hex(x) for x in i2c.scan()])


# =========================
# INIT RTC
# =========================
rtc = StartupModule(
    "RTC",
    lambda: DS1302(
        clk=RTC_CLK_PIN,
        dat=RTC_DAT_PIN,
        rst=RTC_RST_PIN
    ),
    error_result_rtc
)
rtc_test = rtc.read()
print("RTC INIT:", rtc_test)


# =========================
# INIT BMP580
# =========================
bmp = StartupModule(
    "BMP580",
    lambda: BMP580(
        i2c=i2c,
        address=BMP_ADDRESS,
        sea_level_pressure=BMP_SEA_LEVEL_PRESSURE,
        pressure_osr=BMP580.OSR128,
        temperature_osr=BMP580.OSR8,
        iir_coef=BMP580.COEF_7,
    ),
    error_result_bmp
)
bmp_test = bmp.read()
print("BMP INIT:", bmp_test)


# =========================
# INIT BME688
# =========================
bme = StartupModule(
    "BME688",
    lambda: BME688(
        i2c=i2c,
        address=BME_ADDRESS,
        sea_level_pressure=BME_SEA_LEVEL_PRESSURE,
        gas_enabled=True,
        pressure_os=4,
        temperature_os=8,
        humidity_os=2,
        iir_filter=3,
        gas_temp=320,
        gas_ms=150,
    ),
    error_result_bme
)
bme_test = bme.read()
print("BME INIT:", bme_test)


# =========================
# INIT MPU6500
# =========================
mpu = StartupModule(
    "MPU6500",
    lambda: MPU6500(
        i2c=i2c,
        addr=MPU_ADDRESS
    ),
    error_result_mpu
)

if MPU_DO_CALIBRATION and mpu.ok:
    try:
        print("MPU6500 CALIBRATION: keep the board still")
        mpu.calibrate(samples=MPU_CALIBRATION_SAMPLES)
        print("MPU6500 CALIBRATION DONE")
    except Exception as e:
        mpu.ok = False
        mpu.last_error = str(e)
        print("MPU6500 CALIBRATION ERROR:", mpu.last_error)

mpu_test = mpu.read()
print("MPU INIT:", mpu_test)


# =========================
# INIT MAGNETOMETER
# =========================
mag = StartupModule(
    "MAG",
    lambda: GY271(
        i2c=i2c,
        address=MAG_ADDRESS
    ),
    error_result_mag
)
mag_test = mag.read()
print("MAG INIT:", mag_test)


# =========================
# INIT GPS
# =========================
print("GPS INIT: UART{} RX={} TX={}".format(GPS_UART_ID, GPS_RX_PIN, GPS_TX_PIN))
gps = StartupModule(
    "GPS",
    lambda: GPS6MV2(
        uart_id=GPS_UART_ID,
        rx_pin=GPS_RX_PIN,
        tx_pin=GPS_TX_PIN,
        baudrate=GPS_BAUDRATE,
        debug=GPS_DEBUG
    ),
    error_result_gps
)
gps_test = gps.read()
print("GPS INIT:", gps_test)


# =========================
# INIT SD MODULE
# =========================
sdmod = StartupModule(
    "SD",
    lambda: SDModule(
        sck_pin=SD_SCK_PIN,
        mosi_pin=SD_MOSI_PIN,
        miso_pin=SD_MISO_PIN,
        cs_pin=SD_CS_PIN,
        baudrate=SD_BAUDRATE,
        mount_point="/sd",
        data_filename="data.txt",
        log_filename="logs.txt"
    ),
    lambda error_text: {"ok": False, "error": error_text}
)

if sdmod.ok:
    print("SD CARD READY")
else:
    print("SD CARD NOT READY:", sdmod.last_error)


# =========================
# INIT RFM69
# =========================
rfm = StartupModule(
    "RFM69",
    lambda: RFM69(
        sck_pin=RFM_SCK_PIN,
        mosi_pin=RFM_MOSI_PIN,
        miso_pin=RFM_MISO_PIN,
        cs_pin=RFM_CS_PIN,
        rst_pin=RFM_RST_PIN,
        frequency_mhz=RFM_FREQ_MHZ,
        bitrate=RFM_BITRATE,
        tx_power_dbm=RFM_TX_POWER_DBM
    ),
    lambda error_text: {"ok": False, "error": error_text}
)

if rfm.ok:
    print("RFM69 READY")
else:
    print("RFM69 NOT READY:", rfm.last_error)

print("CANSAT RFM CONFIG: SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} FREQ={}MHz BITRATE={} TX_POWER={}dBm".format(
    RFM_SCK_PIN,
    RFM_MOSI_PIN,
    RFM_MISO_PIN,
    RFM_CS_PIN,
    RFM_FREQ_MHZ,
    RFM_BITRATE,
    RFM_TX_POWER_DBM
))

sdmod.write_log(log_line(
    now_text(rtc_test),
    "INFO",
    "RFM69",
    "CONFIG SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} FREQ={}MHz BITRATE={} TX_POWER={}dBm".format(
        RFM_SCK_PIN,
        RFM_MOSI_PIN,
        RFM_MISO_PIN,
        RFM_CS_PIN,
        RFM_FREQ_MHZ,
        RFM_BITRATE,
        RFM_TX_POWER_DBM
    )
))

rfm_debug = rfm_debug_line(now_text(rtc_test), rfm.debug_status())
print(rfm_debug)
sdmod.write_log(rfm_debug)


# =========================
# SHOW INIT STATUS CYCLES
# =========================
init_status_map = {
    "rtc": rtc_test["ok"],
    "bmp": bmp_test["ok"],
    "bme": bme_test["ok"],
    "mpu": mpu_test["ok"],
    "mag": mag_test["ok"],
    "sd": sdmod.ok,
    "gps": gps_led_state(gps_test),
    "rfm": rfm.ok,
}
show_init_cycles(init_status_map)


# =========================
# STATUS FLAGS
# =========================
rtc_was_ok = rtc_test["ok"]
bmp_was_ok = bmp_test["ok"]
bme_was_ok = bme_test["ok"]
mpu_was_ok = mpu_test["ok"]
mag_was_ok = mag_test["ok"]
gps_was_ok = gps_test["ok"]
gps_had_fix = gps_test["fix"] if gps_test["ok"] else False
sd_was_ok = sdmod.ok
rfm_was_ok = rfm.ok
sample_id = 0
gps_time_synced_for_connection = False
gps_packet_sent_for_connection = False
gps_fix_packet_sent_for_connection = False

last_rtc_reconnect_ms = utime.ticks_ms()
last_bmp_reconnect_ms = utime.ticks_ms()
last_bme_reconnect_ms = utime.ticks_ms()
last_mpu_reconnect_ms = utime.ticks_ms()
last_mag_reconnect_ms = utime.ticks_ms()
last_gps_reconnect_ms = utime.ticks_ms()
last_rfm_reconnect_ms = utime.ticks_ms()


# =========================
# MAIN LOOP
# =========================
while True:
    try:
        # ---------- RTC ----------
        rtc_data = rtc.read()
        ts = now_text(rtc_data)

        if rtc_data["ok"]:
            if not rtc_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "RTC", "RECONNECTED"))
            rtc_was_ok = True
        else:
            if retry_due(last_rtc_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                rtc.reconnect()
                last_rtc_reconnect_ms = utime.ticks_ms()
            rtc_was_ok = False

        # ---------- BMP580 ----------
        bmp_data = bmp.read()

        if bmp_data["ok"]:
            if not bmp_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "BMP580", "RECONNECTED"))
            bmp_was_ok = True
        else:
            if bmp_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "BMP580", bmp_data.get("error", "unknown")))
            if retry_due(last_bmp_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                bmp.reconnect()
                last_bmp_reconnect_ms = utime.ticks_ms()
            bmp_was_ok = False

        # ---------- BME688 ----------
        bme_data = bme.read()

        if bme_data["ok"]:
            if not bme_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "BME688", "RECONNECTED"))
            bme_was_ok = True
        else:
            if bme_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "BME688", bme_data.get("error", "unknown")))
            if retry_due(last_bme_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                bme.reconnect()
                last_bme_reconnect_ms = utime.ticks_ms()
            bme_was_ok = False

        # ---------- MPU6500 ----------
        mpu_data = mpu.read()

        if mpu_data["ok"]:
            if not mpu_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "MPU6500", "RECONNECTED"))
            mpu_was_ok = True
        else:
            if mpu_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "MPU6500", mpu_data.get("error", "unknown")))
            if retry_due(last_mpu_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                mpu.reconnect()
                last_mpu_reconnect_ms = utime.ticks_ms()
            mpu_was_ok = False

        # ---------- MAGNETOMETER ----------
        mag_data = mag.read()

        if mag_data["ok"]:
            if not mag_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "MAG", "RECONNECTED"))
            mag_was_ok = True
        else:
            if mag_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "MAG", mag_data.get("error", "unknown")))
            if retry_due(last_mag_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                mag.reconnect()
                last_mag_reconnect_ms = utime.ticks_ms()
            mag_was_ok = False

        # ---------- GPS ----------
        gps_data = gps.read()

        if gps_data["ok"]:
            if not gps_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "GPS", "RECONNECTED"))
                gps_time_synced_for_connection = False
                gps_packet_sent_for_connection = False
                gps_fix_packet_sent_for_connection = False
            gps_was_ok = True
        else:
            if gps_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "GPS", gps_data.get("error", "unknown")))
            if retry_due(last_gps_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                gps.reconnect()
                last_gps_reconnect_ms = utime.ticks_ms()
            gps_was_ok = False
            gps_time_synced_for_connection = False
            gps_packet_sent_for_connection = False
            gps_fix_packet_sent_for_connection = False

        if gps_data["ok"] and gps_data["fix"]:
            if not gps_had_fix:
                sdmod.write_log(log_line(ts, "INFO", "GPS", "FIX_ACQUIRED"))
            gps_had_fix = True
        else:
            if gps_had_fix:
                sdmod.write_log(log_line(ts, "WARN", "GPS", "FIX_LOST"))
            gps_had_fix = False

        if gps_data["ok"] and gps_data["rtc_update_ready"] and not gps_time_synced_for_connection:
            if sync_rtc_from_gps(rtc, gps_data):
                sdmod.write_log(log_line(ts, "INFO", "GPS", "RTC_SYNCED"))
                gps_time_synced_for_connection = True
            else:
                sdmod.write_log(log_line(ts, "WARN", "GPS", "RTC_SYNC_FAILED"))

        # ---------- FORMAT OUTPUTS ----------
        telemetry_line = format_telemetry_line(ts, bmp_data, bme_data, mpu_data, mag_data, gps_data)
        send_gps_packet = False

        if gps_data["ok"] and gps_data["connected"] and not gps_packet_sent_for_connection:
            send_gps_packet = True
            gps_packet_sent_for_connection = True

        if gps_data["ok"] and gps_data["fix"] and not gps_fix_packet_sent_for_connection:
            send_gps_packet = True
            gps_fix_packet_sent_for_connection = True

        rfm_packets = build_rfm_packets(
            sample_id,
            ts,
            bmp_data,
            bme_data,
            mpu_data,
            mag_data,
            gps_data,
            send_gps_packet
        )

        # ---------- SD WRITE / HEALTH ----------
        current_sd_ok = sd_was_ok
        data_ok = sdmod.write_data(telemetry_line)

        if data_ok:
            if not sd_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "SD", "RECONNECTED"))
            current_sd_ok = True
        else:
            current_sd_ok = False

        sd_was_ok = current_sd_ok

        # ---------- RFM SEND ----------
        current_rfm_ok = rfm_was_ok
        all_rfm_ok = True

        for packet in rfm_packets:
            rfm_tx_line = fit_rfm_payload(packet)

            if RFM_LOG_EVERY_SEND:
                tx_attempt_log = log_line(ts, "INFO", "RFM69", "TX_ATTEMPT {}".format(rfm_tx_line))
                print(tx_attempt_log)
                sdmod.write_log(tx_attempt_log)

            rfm_ok = rfm.send_line(rfm_tx_line)

            if rfm_ok:
                if RFM_LOG_EVERY_SEND:
                    tx_ok_log = log_line(ts, "INFO", "RFM69", "TX_OK {}".format(rfm_tx_line))
                    print(tx_ok_log)
                    sdmod.write_log(tx_ok_log)
            else:
                all_rfm_ok = False
                tx_fail_log = log_line(
                    ts,
                    "ERROR",
                    "RFM69",
                    "TX_FAIL {} ERROR={}".format(rfm_tx_line, rfm.last_error)
                )
                print(tx_fail_log)
                sdmod.write_log(tx_fail_log)
                break

        if all_rfm_ok:
            if not rfm_was_ok:
                sdmod.write_log(log_line(ts, "INFO", "RFM69", "RECONNECTED"))
            current_rfm_ok = True
        else:
            if rfm_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "RFM69", rfm.last_error))
            if retry_due(last_rfm_reconnect_ms, RFM_RECONNECT_INTERVAL_MS):
                rfm.reconnect()
                last_rfm_reconnect_ms = utime.ticks_ms()
            current_rfm_ok = False

        rfm_was_ok = current_rfm_ok

        # ---------- LED STATUS CYCLES ----------
        status_map = {
            "rtc": rtc_data["ok"],
            "bmp": bmp_data["ok"],
            "bme": bme_data["ok"],
            "mpu": mpu_data["ok"],
            "mag": mag_data["ok"],
            "sd": current_sd_ok,
            "gps": gps_led_state(gps_data),
            "rfm": current_rfm_ok,
        }
        if DEBUG_TELEMETRY:
            print(telemetry_line)
        show_two_status_cycles(status_map)
        sample_id = (sample_id + 1) % 10000

    except Exception as e:
        print("MAIN LOOP ERROR:", e)
        leds.blink_all(leds.RED, LED_MAIN_ERROR_RED_MS)
        sdmod.write_log(log_line("RTC_ERR", "ERROR", "MAIN", str(e)))

    utime.sleep_ms(LOOP_DELAY_MS)
