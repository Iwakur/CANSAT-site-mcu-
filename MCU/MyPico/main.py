from machine import Pin, I2C, SPI
import os
import utime

from rtc import DS1302
from bme688 import BME688
from mpu6500 import MPU6500
from gy271 import GY271
from gps6mv2 import GPS6MV2
from sdcard import SDModule
from status_leds import StatusLEDs
from rfm69 import RFM69
from tmp36 import TMP36
from helpers import *


# =========================
# CONFIG
# =========================

# RTC pins
RTC_CLK_PIN = 27
RTC_DAT_PIN = 28
RTC_RST_PIN = 29

# Shared I2C bus
I2C_ID = 0
I2C_SCL_PIN = 1
I2C_SDA_PIN = 0
I2C_FREQ = 100000

# BME688
BME_ADDRESS = 0x77
BME_SEA_LEVEL_PRESSURE = 1013.25

# MPU6500
MPU_ADDRESS = 0x68
MPU_DO_CALIBRATION = True
MPU_CALIBRATION_SAMPLES = 300

# TMP36 analog temperature sensor
TMP36_PIN = 26

# Magnetometer (HW-246 / GY-271)
MAG_ADDRESS = 0x2c

# GPS (GY-GPS6MV2 / NEO-6M)
GPS_UART_ID = 0
GPS_RX_PIN = 13
GPS_TX_PIN = None
GPS_BAUDRATE = 9600
GPS_DEBUG = False

# SD card SPI
SD_SCK_PIN = 2
SD_MOSI_PIN = 3
SD_MISO_PIN = 4
SD_CS_PIN = 5
SD_SPI_ID = 0
SD_USE_HARDWARE_SPI = False
SD_BAUDRATE = 500000
SD_WRITE_ENABLED = False
SD_RECONNECT_INTERVAL_MS = 10000
SD_FLUSH_EVERY_SAMPLES = 5

# Onboard flash packet log
FLASH_LOG_ENABLED = True
FLASH_LOG_FILENAME = "log.txt"
FLASH_LOG_RESET_ON_BOOT = True
FLASH_LOG_MIN_FREE_MB = 0.15

# LED modules a linvers
MISSION_LED_PIN = 10   
MODULE_LED_PIN = 9
MODULE_LED_COUNT = 8

MODULE_RTC = 0
MODULE_TMP36 = 1
MODULE_BME = 2
MODULE_MPU = 3
MODULE_MAG = 4
MODULE_GPS = 5
MODULE_SD = 6
MODULE_RFM = 7

# RFM69 433.3 MHz
RFM_SCK_PIN = SD_SCK_PIN
RFM_MOSI_PIN = SD_MOSI_PIN
RFM_MISO_PIN = SD_MISO_PIN
RFM_CS_PIN = 6
RFM_RST_PIN = 7
RFM_SPI_ID = 0
RFM_SPI_BAUDRATE = 50000
RFM_FREQ_MHZ = 433.3
RFM_BITRATE = 9600
RFM_FREQ_DEVIATION = 19000
RFM_RX_BW_REG = 0x43
RFM_AFC_BW_REG = 0x42
RFM_PREAMBLE_LENGTH = 8
RFM_TX_POWER_DBM = 20
RFM_NODE_ID = 0xCA
RFM_DESTINATION_ID = 0xA6
RFM_ACK_TIMEOUT_MS = 350
RFM_ACK_RETRIES = 0
RFM_ENCRYPTION_KEY = b"CANSAT2026RFM69!"
RFM_MAX_PAYLOAD_BYTES = 60
RFM_PACKET_GAP_MS = 300
RFM_LOG_EVERY_SEND = True
RFM_ACK_BLUE_BLINK_MS = 5
DEBUG_TELEMETRY = True
DEBUG_TELEMETRY_EVERY_SAMPLES = 1
RFM_STATUS_EVERY_SAMPLES = 1

# Main loop
LOOP_PERIOD_MS = 3000
GREEN_LED_OFF_AFTER_SAMPLES = 100
SENSOR_RECONNECT_INTERVAL_MS = 30000
RFM_RECONNECT_INTERVAL_MS = 10000

# Startup calibration / settling
STARTUP_CALIBRATION_ENABLED = True
STARTUP_STABLE_READS = 3
STARTUP_RTC_STABLE_READS = 1
STARTUP_MODULE_SETTLE_TIMEOUT_MS = 6000
STARTUP_READ_INTERVAL_MS = 120
STARTUP_GPS_TIME_SYNC_WAIT_MS = 15000
STARTUP_GPS_POLL_MS = 250
STARTUP_LED_ANIMATION_MS = 70

LED_MAIN_ERROR_RED_MS = 60



# =========================
# HELPERS
# =========================
# Helper functions and wrapper classes live in helpers.py.


def release_sd_cs():
    try:
        Pin(SD_CS_PIN, Pin.OUT, value=1)
    except Exception:
        pass


def release_rfm_cs():
    try:
        Pin(RFM_CS_PIN, Pin.OUT, value=1)
    except Exception:
        pass


def select_sd_bus():
    release_rfm_cs()
    release_sd_cs()
    utime.sleep_us(50)


def select_rfm_bus():
    release_sd_cs()
    release_rfm_cs()
    utime.sleep_us(50)


flash_log_write_enabled = FLASH_LOG_ENABLED
flash_log_last_error = None


def flash_log_free_space_mb():
    stat = os.statvfs("/")
    block_size = stat[0]
    free_blocks = stat[3]
    free_bytes = block_size * free_blocks
    return free_bytes / (1024 * 1024)


def flash_log_print_free_space():
    free_mb = flash_log_free_space_mb()
    print("Free space: {:.2f} Mo".format(free_mb))
    return free_mb


def flash_log_boot_reset():
    global flash_log_last_error

    if not FLASH_LOG_ENABLED or not FLASH_LOG_RESET_ON_BOOT:
        return True

    try:
        os.remove(FLASH_LOG_FILENAME)
    except OSError:
        pass
    except Exception as e:
        flash_log_last_error = str(e)
        return False

    flash_log_last_error = None
    return True


def flash_log_can_write():
    global flash_log_write_enabled, flash_log_last_error

    if not flash_log_write_enabled:
        return False

    try:
        free_mb = flash_log_print_free_space()
        if free_mb <= FLASH_LOG_MIN_FREE_MB:
            flash_log_write_enabled = False
            flash_log_last_error = "LOW_SPACE {:.2f} Mo".format(free_mb)
            return False
        return True
    except Exception as e:
        flash_log_last_error = str(e)
        return False


def flash_log_append_line(line):
    global flash_log_write_enabled, flash_log_last_error

    if not FLASH_LOG_ENABLED:
        return False

    if not flash_log_can_write():
        return False

    try:
        with open(FLASH_LOG_FILENAME, "a") as f:
            f.write(line + "\n")

        flash_log_last_error = None
        free_mb = flash_log_print_free_space()
        if free_mb <= FLASH_LOG_MIN_FREE_MB:
            flash_log_write_enabled = False
            flash_log_last_error = "LOW_SPACE {:.2f} Mo".format(free_mb)
        return True

    except Exception as e:
        flash_log_last_error = str(e)
        return False


class CompatibleRFM69:
    REG_VERSION = 0x10
    REG_OPMODE = 0x01
    REG_IRQFLAGS1 = 0x27
    REG_IRQFLAGS2 = 0x28
    MODE_STDBY = 0x04
    MODE_TX = 0x0C
    EXPECTED_VERSION = 0x24

    def __init__(
        self,
        sck_pin,
        mosi_pin,
        miso_pin,
        cs_pin,
        rst_pin,
        spi_id,
        spi_baudrate,
        frequency_mhz,
        bitrate,
        frequency_deviation,
        rx_bw_reg,
        afc_bw_reg,
        preamble_length,
        tx_power_dbm,
        node_id,
        destination_id,
        ack_timeout_ms,
        ack_retries,
        encryption_key,
    ):
        self.sck_pin = sck_pin
        self.mosi_pin = mosi_pin
        self.miso_pin = miso_pin
        self.cs_pin = cs_pin
        self.rst_pin = rst_pin
        self.spi_id = spi_id
        self.spi_baudrate = spi_baudrate
        self.frequency_mhz = frequency_mhz
        self.bitrate = bitrate
        self.frequency_deviation = frequency_deviation
        self.rx_bw_reg = rx_bw_reg
        self.afc_bw_reg = afc_bw_reg
        self.preamble_length = preamble_length
        self.tx_power_dbm = tx_power_dbm
        self.node_id = node_id
        self.destination_id = destination_id
        self.ack_timeout_ms = ack_timeout_ms
        self.ack_retries = ack_retries
        self.encryption_key = encryption_key
        self.radio = None
        self.spi = None
        self.nss = None
        self.reset_pin = None
        self.native_send_line = False
        self.ok = False
        self.last_error = None
        self.reconnect()

    def reconnect(self):
        self.ok = False
        self.last_error = None

        try:
            try:
                Pin(SD_CS_PIN, Pin.OUT, value=1)
                Pin(self.cs_pin, Pin.OUT, value=1)
            except Exception:
                pass

            self.spi = SPI(
                self.spi_id,
                baudrate=self.spi_baudrate,
                polarity=0,
                phase=0,
                firstbit=SPI.MSB,
                sck=Pin(self.sck_pin),
                mosi=Pin(self.mosi_pin),
                miso=Pin(self.miso_pin)
            )
            self.nss = Pin(self.cs_pin, Pin.OUT, value=True)
            if self.rst_pin is None:
                self.reset_pin = None
            else:
                self.reset_pin = Pin(self.rst_pin, Pin.OUT, value=False)

            radio = RFM69(spi=self.spi, nss=self.nss, reset=self.reset_pin)
            radio.frequency_mhz = self.frequency_mhz
            radio.bitrate = self.bitrate
            radio.frequency_deviation = self.frequency_deviation
            radio.preamble_length = self.preamble_length
            radio.spi_write(0x19, self.rx_bw_reg)
            radio.spi_write(0x1A, self.afc_bw_reg)
            radio.encryption_key = self.encryption_key
            radio.tx_power = self.tx_power_dbm
            radio.node = self.node_id
            radio.destination = self.destination_id
            radio.ack_wait = self.ack_timeout_ms / 1000
            radio.ack_retries = self.ack_retries
            self.native_send_line = False

            self.radio = radio
            version = self._read_version()
            if version != self.EXPECTED_VERSION:
                raise OSError("rfm bad version 0x{:02X}".format(version))

            self.ok = getattr(radio, "ok", True)
            self.last_error = getattr(radio, "last_error", None)
            return self.ok

        except Exception as e:
            self.radio = None
            self.ok = False
            self.last_error = str(e)
            return False

    def _read_version(self):
        if hasattr(self.radio, "_read_reg"):
            return self.radio._read_reg(self.REG_VERSION)
        return self.radio.spi_read(self.REG_VERSION)

    def _read_reg(self, register):
        if hasattr(self.radio, "_read_reg"):
            return self.radio._read_reg(register)
        return self.radio.spi_read(register)

    def _set_mode(self, mode):
        if hasattr(self.radio, "_set_mode"):
            self.radio._set_mode(mode)
        else:
            self.radio.set_mode(mode)

    def activate_spi(self):
        self.spi = SPI(
            self.spi_id,
            baudrate=self.spi_baudrate,
            polarity=0,
            phase=0,
            firstbit=SPI.MSB,
            sck=Pin(self.sck_pin),
            mosi=Pin(self.mosi_pin),
            miso=Pin(self.miso_pin)
        )
        if self.radio is not None:
            self.radio.spi = self.spi
        release_sd_cs()
        try:
            self.nss.high()
        except Exception:
            pass

    def send_line(self, text):
        try:
            if not self.ok:
                if not self.reconnect():
                    return False

            try:
                Pin(SD_CS_PIN, Pin.OUT, value=1)
                self.nss.high()
            except Exception:
                pass

            payload = text.encode("utf-8")
            if len(payload) > RFM_MAX_PAYLOAD_BYTES:
                payload = payload[:RFM_MAX_PAYLOAD_BYTES]

            self.ok = True
            if self.radio.send(payload):
                self.last_error = None
                return True

            self.last_error = "TX_FAIL id={}".format(self.radio.identifier)
            return False

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            try:
                self._set_mode(self.MODE_STDBY)
            except Exception:
                pass
            try:
                self.reconnect()
            except Exception:
                pass
            return False

    def debug_status(self):
        try:
            if self.radio is None:
                raise OSError(self.last_error or "not initialized")
            version = self._read_reg(self.REG_VERSION)
            opmode = self._read_reg(self.REG_OPMODE)
            irq1 = self._read_reg(self.REG_IRQFLAGS1)
            irq2 = self._read_reg(self.REG_IRQFLAGS2)
            return {
                "ok": True,
                "version": version,
                "opmode": opmode,
                "irq1": irq1,
                "irq2": irq2,
                "version_ok": version == self.EXPECTED_VERSION,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }


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


def rfm_bool(data):
    return 1 if data.get("ok") else 0


def rfm_scale_int(value, factor=1):
    if value is None:
        return "x"
    return scale_int(value, factor)


def short_date(ts):
    if ts == "RTC_ERR":
        return "0"
    return ts[:10].replace("-", "")


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


def build_rfm_packets(sample_id, telemetry_line, ts, tmp_data, bme_data, mpu_data, mag_data, gps_data):
    return [
        build_env_packet(sample_id, ts, tmp_data, bme_data),
        build_bme_packet(sample_id, bme_data),
        build_accel_packet(sample_id, mpu_data),
        build_orientation_packet(sample_id, mpu_data),
        build_mag_packet(sample_id, mag_data),
        build_gps_packet(sample_id, gps_data),
    ]


def format_legacy_telemetry_line(ts, tmp_data, bme_data, mpu_data, mag_data, gps_data):
    return "T={} {} {} {} {} {}".format(
        ts,
        format_tmp36_text(tmp_data),
        format_bme_text(bme_data),
        format_mpu_text(mpu_data),
        format_mag_text(mag_data),
        format_gps_text(gps_data)
    )


def bool_status_color(ok):
    return module_leds.GREEN if ok else module_leds.RED


def sd_status_color(status):
    if status == "buffering":
        return module_leds.ORANGE
    if status == "writing":
        return module_leds.BLUE
    if status == "low_space":
        return module_leds.ORANGE
    if status == "saved":
        return module_leds.GREEN
    return module_leds.GREEN if status else module_leds.RED


def rfm_status_color(status):
    if status == "no_ack":
        return module_leds.ORANGE
    return module_leds.GREEN if status else module_leds.RED


def rfm_status_ok(status):
    return status is True or status == "ok"


def is_no_ack_error(error_text):
    return str(error_text).startswith("NO_ACK")


def blink_rfm_ack():
    module_leds._set(MODULE_RFM, module_leds.BLUE)
    module_leds.show()
    utime.sleep_ms(RFM_ACK_BLUE_BLINK_MS)
    module_leds._set(MODULE_RFM, module_leds.GREEN)
    module_leds.show()


def gps_status_color(gps_state):
    if gps_state == "fix":
        return module_leds.GREEN
    if gps_state == "connected":
        return module_leds.BLUE
    return module_leds.RED


def mission_health_level(status_map):
    module_failures = 0

    for key in ("rtc", "tmp36", "bme", "mpu", "mag"):
        if not status_map.get(key):
            module_failures += 1

    if status_map.get("sd") is False:
        module_failures += 1

    if not rfm_status_ok(status_map.get("rfm")):
        module_failures += 1

    if status_map.get("gps") != "fix":
        module_failures += 1

    if module_failures >= 3:
        return "critical"

    if not rfm_status_ok(status_map.get("rfm")):
        return "warning"

    if module_failures == 0:
        return "good"

    return "warning"


def update_module_leds(status_map, sample_id):
    module_leds._set(MODULE_RTC, bool_status_color(status_map["rtc"]))
    module_leds._set(MODULE_TMP36, bool_status_color(status_map["tmp36"]))
    module_leds._set(MODULE_BME, bool_status_color(status_map["bme"]))
    module_leds._set(MODULE_MPU, bool_status_color(status_map["mpu"]))
    module_leds._set(MODULE_MAG, bool_status_color(status_map["mag"]))
    module_leds._set(MODULE_GPS, gps_status_color(status_map["gps"]))
    module_leds._set(MODULE_SD, sd_status_color(status_map["sd"]))
    module_leds._set(MODULE_RFM, rfm_status_color(status_map["rfm"]))

    if sample_id >= GREEN_LED_OFF_AFTER_SAMPLES:
        for index in range(MODULE_LED_COUNT):
            if module_leds.np[index] == module_leds.GREEN:
                module_leds._set(index, module_leds.OFF)

    module_leds.show()


def update_mission_led(status_map, sample_id):
    level = mission_health_level(status_map)
    pulse_on = (sample_id % 2) == 0

    if level == "critical":
        color = mission_led.RED
    elif level == "warning":
        color = mission_led.ORANGE
    else:
        color = mission_led.GREEN

    if sample_id >= GREEN_LED_OFF_AFTER_SAMPLES and color == mission_led.GREEN:
        color = mission_led.OFF

    mission_led._set(0, color if pulse_on else mission_led.OFF)
    mission_led.show()


def update_status_leds(status_map, sample_id):
    update_module_leds(status_map, sample_id)
    update_mission_led(status_map, sample_id)


def calibration_log(message):
    line = "CALIBRATION {}".format(message)
    print(line)
    try:
        if "sdmod" in globals() and sdmod is not None and sdmod.ok:
            sdmod.write_log(log_line(now_text(rtc.read()), "INFO", "CALIBRATION", message))
    except Exception:
        pass


def calibration_leds(active_index=None, done=None, failed=None, tick=0):
    if done is None:
        done = {}
    if failed is None:
        failed = {}

    for index in range(MODULE_LED_COUNT):
        module_leds._set(index, module_leds.OFF)

    for index in done:
        module_leds._set(index, module_leds.GREEN)

    for index in failed:
        module_leds._set(index, module_leds.RED)

    if active_index is not None:
        module_leds._set(
            active_index,
            module_leds.YELLOW if (tick % 2) == 0 else module_leds.BLUE
        )

    module_leds.show()


def wait_for_stable_module(label, module, module_index, error_result, done, failed, stable_reads):
    calibration_log("{} SETTLING".format(label))
    start = utime.ticks_ms()
    consecutive_ok = 0
    last_data = error_result("startup calibration did not run")
    tick = 0

    while utime.ticks_diff(utime.ticks_ms(), start) < STARTUP_MODULE_SETTLE_TIMEOUT_MS:
        calibration_leds(module_index, done, failed, tick)
        last_data = module.read()

        if last_data["ok"]:
            consecutive_ok += 1
            if consecutive_ok >= stable_reads:
                done[module_index] = True
                calibration_leds(None, done, failed, tick)
                calibration_log("{} READY".format(label))
                return last_data
        else:
            consecutive_ok = 0

        tick += 1
        utime.sleep_ms(STARTUP_READ_INTERVAL_MS)

    failed[module_index] = True
    calibration_leds(None, done, failed, tick)
    calibration_log("{} NOT_READY {}".format(label, last_data.get("error", "unknown")))
    return last_data


def calibrate_mpu_startup(done, failed):
    if not MPU_DO_CALIBRATION or not mpu.ok:
        return

    calibration_log("MPU6500 OFFSET_CALIBRATION keep board still")

    def progress(good, total):
        tick = good // 10
        calibration_leds(MODULE_MPU, done, failed, tick)

    try:
        mpu.calibrate(samples=MPU_CALIBRATION_SAMPLES, progress=progress)
        calibration_log("MPU6500 OFFSET_CALIBRATION_DONE")
    except Exception as e:
        mpu.ok = False
        mpu.last_error = str(e)
        failed[MODULE_MPU] = True
        calibration_leds(None, done, failed, 0)
        calibration_log("MPU6500 OFFSET_CALIBRATION_FAILED {}".format(mpu.last_error))


def wait_for_gps_time_sync(done, failed):
    calibration_log("GPS TIME_SYNC_WAIT")
    start = utime.ticks_ms()
    tick = 0
    last_data = gps_test

    while utime.ticks_diff(utime.ticks_ms(), start) < STARTUP_GPS_TIME_SYNC_WAIT_MS:
        calibration_leds(MODULE_GPS, done, failed, tick)
        last_data = gps.read()

        if last_data["ok"] and last_data["rtc_update_ready"]:
            if sync_rtc_from_gps(rtc, last_data):
                last_data["rtc_synced"] = True
                done[MODULE_GPS] = True
                calibration_leds(None, done, failed, tick)
                calibration_log("GPS RTC_SYNCED")
                return last_data

        tick += 1
        utime.sleep_ms(STARTUP_GPS_POLL_MS)

    if last_data["ok"] and last_data["connected"]:
        done[MODULE_GPS] = True
        calibration_log("GPS CONNECTED_NO_TIME continuing without fix")
    else:
        failed[MODULE_GPS] = True
        calibration_log("GPS NO_TIME {}".format(last_data.get("error", "no time")))

    calibration_leds(None, done, failed, tick)
    last_data["rtc_synced"] = False
    return last_data


def run_startup_calibration():
    if not STARTUP_CALIBRATION_ENABLED:
        return rtc_test, tmp36_test, bme_test, mpu_test, mag_test, gps_test

    calibration_log("START")
    done = {}
    failed = {}

    rtc_ready = wait_for_stable_module(
        "RTC",
        rtc,
        MODULE_RTC,
        error_result_rtc,
        done,
        failed,
        STARTUP_RTC_STABLE_READS
    )
    tmp36_ready = wait_for_stable_module(
        "TMP36",
        tmp36,
        MODULE_TMP36,
        error_result_tmp36,
        done,
        failed,
        STARTUP_STABLE_READS
    )
    bme_ready = wait_for_stable_module(
        "BME688",
        bme,
        MODULE_BME,
        error_result_bme,
        done,
        failed,
        STARTUP_STABLE_READS
    )

    calibrate_mpu_startup(done, failed)
    mpu_ready = wait_for_stable_module(
        "MPU6500",
        mpu,
        MODULE_MPU,
        error_result_mpu,
        done,
        failed,
        STARTUP_STABLE_READS
    )
    mag_ready = wait_for_stable_module(
        "MAG",
        mag,
        MODULE_MAG,
        error_result_mag,
        done,
        failed,
        STARTUP_STABLE_READS
    )

    gps_ready = wait_for_gps_time_sync(done, failed)

    if flash_log_write_enabled:
        done[MODULE_SD] = True
    else:
        failed[MODULE_SD] = True

    if rfm.ok:
        done[MODULE_RFM] = True
    else:
        failed[MODULE_RFM] = True

    calibration_leds(None, done, failed, 0)
    utime.sleep_ms(250)
    calibration_log("DONE")

    rtc_after = rtc.read()
    return rtc_after, tmp36_ready, bme_ready, mpu_ready, mag_ready, gps_ready


# =========================
# INIT LEDS
# =========================
mission_led = StatusLEDs(pin_num=MISSION_LED_PIN, count=1, brightness=20)
module_leds = StatusLEDs(pin_num=MODULE_LED_PIN, count=MODULE_LED_COUNT, brightness=20)
for _ in range(3):
    mission_led._set(0, mission_led.BLUE)
    mission_led.show()
    utime.sleep_ms(80)
    mission_led._set(0, mission_led.OFF)
    mission_led.show()
    utime.sleep_ms(80)
module_leds.startup_test()


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
# INIT ONBOARD FLASH LOG
# =========================
if FLASH_LOG_ENABLED:
    if flash_log_boot_reset():
        print("FLASH LOG RESET:", FLASH_LOG_FILENAME)
    else:
        print("FLASH LOG RESET FAILED:", flash_log_last_error)
    flash_log_print_free_space()


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
rtc.set_datetime(2000, 1, 1, 6, 0, 0, 0)
print("RTC INIT:", rtc_test)


# =========================
# INIT TMP36
# =========================
tmp36 = StartupModule(
    "TMP36",
    lambda: TMP36(
        pin=TMP36_PIN
    ),
    error_result_tmp36
)
tmp36_test = tmp36.read()
print("TMP36 INIT:", tmp36_test)


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
# PREPARE SHARED SPI BUS
# =========================
Pin(SD_CS_PIN, Pin.OUT, value=1)
Pin(RFM_CS_PIN, Pin.OUT, value=1)


# =========================
# INIT SD MODULE
# =========================
if SD_WRITE_ENABLED:
    select_sd_bus()
    sdmod = StartupModule(
        "SD",
        lambda: SDModule(
            sck_pin=SD_SCK_PIN,
            mosi_pin=SD_MOSI_PIN,
            miso_pin=SD_MISO_PIN,
            cs_pin=SD_CS_PIN,
            spi_id=SD_SPI_ID,
            use_hardware_spi=SD_USE_HARDWARE_SPI,
            baudrate=SD_BAUDRATE,
            mount_point="/sd",
            data_filename="data.txt",
            log_filename="logs.txt"
        ),
        lambda error_text: {"ok": False, "error": error_text}
    )
else:
    sdmod = NullSDModule("sd write disabled")
    print("SD WRITE DISABLED")

if SD_WRITE_ENABLED:
    if sdmod.ok:
        print("SD CARD READY")
    else:
        print("SD CARD NOT READY:", sdmod.last_error)


# =========================
# INIT RFM69
# =========================
select_rfm_bus()
rfm = StartupModule(
    "RFM69",
    lambda: CompatibleRFM69(
        sck_pin=RFM_SCK_PIN,
        mosi_pin=RFM_MOSI_PIN,
        miso_pin=RFM_MISO_PIN,
        cs_pin=RFM_CS_PIN,
        rst_pin=RFM_RST_PIN,
        spi_id=RFM_SPI_ID,
        spi_baudrate=RFM_SPI_BAUDRATE,
        frequency_mhz=RFM_FREQ_MHZ,
        bitrate=RFM_BITRATE,
        frequency_deviation=RFM_FREQ_DEVIATION,
        rx_bw_reg=RFM_RX_BW_REG,
        afc_bw_reg=RFM_AFC_BW_REG,
        preamble_length=RFM_PREAMBLE_LENGTH,
        tx_power_dbm=RFM_TX_POWER_DBM,
        node_id=RFM_NODE_ID,
        destination_id=RFM_DESTINATION_ID,
        ack_timeout_ms=RFM_ACK_TIMEOUT_MS,
        ack_retries=RFM_ACK_RETRIES,
        encryption_key=RFM_ENCRYPTION_KEY
    ),
    lambda error_text: {"ok": False, "error": error_text}
)

if rfm.ok:
    print("RFM69 READY")
else:
    print("RFM69 NOT READY:", rfm.last_error)

print("CANSAT RFM CONFIG: SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} RST=GP{} FREQ={}MHz BITRATE={} FDEV={} RXBW=0x{:02X} AFCBW=0x{:02X} PREAMBLE={} TX_POWER={}dBm NODE=0x{:02X} DEST=0x{:02X} ACK={}ms RETRIES={} AES=ON".format(
    RFM_SCK_PIN,
    RFM_MOSI_PIN,
    RFM_MISO_PIN,
    RFM_CS_PIN,
    RFM_RST_PIN,
    RFM_FREQ_MHZ,
    RFM_BITRATE,
    RFM_FREQ_DEVIATION,
    RFM_RX_BW_REG,
    RFM_AFC_BW_REG,
    RFM_PREAMBLE_LENGTH,
    RFM_TX_POWER_DBM,
    RFM_NODE_ID,
    RFM_DESTINATION_ID,
    RFM_ACK_TIMEOUT_MS,
    RFM_ACK_RETRIES
))

sdmod.write_log(log_line(
    now_text(rtc_test),
    "INFO",
    "RFM69",
    "CONFIG SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} RST=GP{} FREQ={}MHz BITRATE={} FDEV={} RXBW=0x{:02X} AFCBW=0x{:02X} PREAMBLE={} TX_POWER={}dBm NODE=0x{:02X} DEST=0x{:02X} ACK={}ms RETRIES={} AES=ON".format(
        RFM_SCK_PIN,
        RFM_MOSI_PIN,
        RFM_MISO_PIN,
        RFM_CS_PIN,
        RFM_RST_PIN,
        RFM_FREQ_MHZ,
        RFM_BITRATE,
        RFM_FREQ_DEVIATION,
        RFM_RX_BW_REG,
        RFM_AFC_BW_REG,
        RFM_PREAMBLE_LENGTH,
        RFM_TX_POWER_DBM,
        RFM_NODE_ID,
        RFM_DESTINATION_ID,
        RFM_ACK_TIMEOUT_MS,
        RFM_ACK_RETRIES
    )
))

rfm_debug = rfm_debug_line(now_text(rtc_test), rfm.debug_status())
print(rfm_debug)
sdmod.write_log(rfm_debug)


# =========================
# STARTUP CALIBRATION / SETTLING
# =========================
rtc_test, tmp36_test, bme_test, mpu_test, mag_test, gps_test = run_startup_calibration()


# =========================
# SHOW INIT STATUS CYCLES
# =========================
init_status_map = {
    "rtc": rtc_test["ok"],
    "tmp36": tmp36_test["ok"],
    "bme": bme_test["ok"],
    "mpu": mpu_test["ok"],
    "mag": mag_test["ok"],
    "sd": flash_log_write_enabled,
    "gps": gps_led_state(gps_test),
    "rfm": rfm.ok,
}
update_status_leds(init_status_map, 0)


# =========================
# STATUS FLAGS
# =========================
rtc_was_ok = rtc_test["ok"]
bme_was_ok = bme_test["ok"]
mpu_was_ok = mpu_test["ok"]
tmp36_was_ok = tmp36_test["ok"]
mag_was_ok = mag_test["ok"]
gps_was_ok = gps_test["ok"]
gps_had_fix = gps_test["fix"] if gps_test["ok"] else False
sd_was_ok = flash_log_write_enabled
rfm_was_ok = rfm.ok
sample_id = 0
gps_time_synced_for_connection = gps_test.get("rtc_synced", False)
gps_packet_sent_for_connection = False
gps_fix_packet_sent_for_connection = False

last_rtc_reconnect_ms = utime.ticks_ms()
last_bme_reconnect_ms = utime.ticks_ms()
last_mpu_reconnect_ms = utime.ticks_ms()
last_tmp36_reconnect_ms = utime.ticks_ms()
last_mag_reconnect_ms = utime.ticks_ms()
last_gps_reconnect_ms = utime.ticks_ms()
last_sd_reconnect_ms = utime.ticks_ms()
last_rfm_reconnect_ms = utime.ticks_ms()
sd_data_buffer = []
sd_log_buffer = []
rfm_spi_restore_needed = False


def queue_sd_log(line):
    if not SD_WRITE_ENABLED:
        return

    try:
        if sdmod.ok:
            select_sd_bus()
            sdmod.write_log(line)
    except Exception:
        pass
    finally:
        try:
            sdmod.release_bus()
        except Exception:
            pass
        restore_rfm_bus()


def restore_rfm_bus():
    global rfm_spi_restore_needed

    select_rfm_bus()
    try:
        rfm.activate_spi()
        rfm_spi_restore_needed = False
        return True
    except Exception:
        rfm_spi_restore_needed = True
        return False


def flush_sd_buffers():
    global last_sd_reconnect_ms, rfm_spi_restore_needed

    if not SD_WRITE_ENABLED:
        return False

    if not sd_data_buffer and not sd_log_buffer:
        return sdmod.ok

    if not sdmod.ok and not retry_due(last_sd_reconnect_ms, SD_RECONNECT_INTERVAL_MS):
        return False

    module_leds._set(MODULE_SD, module_leds.BLUE)
    module_leds.show()
    select_sd_bus()

    data_ok = False
    log_ok = False
    try:
        data_ok = sdmod.write_data_lines(sd_data_buffer)
        log_ok = sdmod.write_log_lines(sd_log_buffer)
    finally:
        try:
            sdmod.release_bus()
        except Exception:
            pass
        rfm_spi_restore_needed = True
        restore_rfm_bus()

    if data_ok and log_ok:
        del sd_data_buffer[:]
        del sd_log_buffer[:]
        return True

    last_sd_reconnect_ms = utime.ticks_ms()
    return False


# =========================
# MAIN LOOP
# =========================
while True:
    loop_start_ms = utime.ticks_ms()

    try:
        # ---------- RTC ----------
        rtc_data = rtc.read()
        ts = now_text(rtc_data)

        if rtc_data["ok"]:
            if not rtc_was_ok:
                queue_sd_log(log_line(ts, "INFO", "RTC", "RECONNECTED"))
            rtc_was_ok = True
        else:
            if retry_due(last_rtc_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                rtc.reconnect()
                last_rtc_reconnect_ms = utime.ticks_ms()
            rtc_was_ok = False

        # ---------- TMP36 ----------
        tmp36_data = tmp36.read()

        if tmp36_data["ok"]:
            if not tmp36_was_ok:
                queue_sd_log(log_line(ts, "INFO", "TMP36", "RECONNECTED"))
            tmp36_was_ok = True
        else:
            if tmp36_was_ok:
                queue_sd_log(log_line(ts, "ERROR", "TMP36", tmp36_data.get("error", "unknown")))
            if retry_due(last_tmp36_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                tmp36.reconnect()
                last_tmp36_reconnect_ms = utime.ticks_ms()
            tmp36_was_ok = False

        # ---------- BME688 ----------
        bme_data = bme.read()

        if bme_data["ok"]:
            if not bme_was_ok:
                queue_sd_log(log_line(ts, "INFO", "BME688", "RECONNECTED"))
            bme_was_ok = True
        else:
            if bme_was_ok:
                queue_sd_log(log_line(ts, "ERROR", "BME688", bme_data.get("error", "unknown")))
            if retry_due(last_bme_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                bme.reconnect()
                last_bme_reconnect_ms = utime.ticks_ms()
            bme_was_ok = False

        # ---------- MPU6500 ----------
        mpu_data = mpu.read()

        if mpu_data["ok"]:
            if not mpu_was_ok:
                queue_sd_log(log_line(ts, "INFO", "MPU6500", "RECONNECTED"))
            mpu_was_ok = True
        else:
            if mpu_was_ok:
                queue_sd_log(log_line(ts, "ERROR", "MPU6500", mpu_data.get("error", "unknown")))
            if retry_due(last_mpu_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                mpu.reconnect()
                last_mpu_reconnect_ms = utime.ticks_ms()
            mpu_was_ok = False

        # ---------- MAGNETOMETER ----------
        mag_data = mag.read()

        if mag_data["ok"]:
            if not mag_was_ok:
                queue_sd_log(log_line(ts, "INFO", "MAG", "RECONNECTED"))
            mag_was_ok = True
        else:
            if mag_was_ok:
                queue_sd_log(log_line(ts, "ERROR", "MAG", mag_data.get("error", "unknown")))
            if retry_due(last_mag_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                mag.reconnect()
                last_mag_reconnect_ms = utime.ticks_ms()
            mag_was_ok = False

        # ---------- GPS ----------
        gps_data = gps.read()

        if gps_data["ok"]:
            if not gps_was_ok:
                queue_sd_log(log_line(ts, "INFO", "GPS", "RECONNECTED"))
                gps_time_synced_for_connection = False
                gps_packet_sent_for_connection = False
                gps_fix_packet_sent_for_connection = False
            gps_was_ok = True
        else:
            if gps_was_ok:
                queue_sd_log(log_line(ts, "ERROR", "GPS", gps_data.get("error", "unknown")))
            if retry_due(last_gps_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                gps.reconnect()
                last_gps_reconnect_ms = utime.ticks_ms()
            gps_was_ok = False
            gps_time_synced_for_connection = False
            gps_packet_sent_for_connection = False
            gps_fix_packet_sent_for_connection = False

        if gps_data["ok"] and gps_data["fix"]:
            if not gps_had_fix:
                queue_sd_log(log_line(ts, "INFO", "GPS", "FIX_ACQUIRED"))
            gps_had_fix = True
        else:
            if gps_had_fix:
                queue_sd_log(log_line(ts, "WARN", "GPS", "FIX_LOST"))
            gps_had_fix = False

        if gps_data["ok"] and gps_data["rtc_update_ready"] and not gps_time_synced_for_connection:
            if sync_rtc_from_gps(rtc, gps_data):
                queue_sd_log(log_line(ts, "INFO", "GPS", "RTC_SYNCED"))
                gps_time_synced_for_connection = True
            else:
                queue_sd_log(log_line(ts, "WARN", "GPS", "RTC_SYNC_FAILED"))

        # ---------- FORMAT OUTPUTS ----------
        telemetry_line = format_telemetry_line(ts, tmp36_data, bme_data, mpu_data, mag_data, gps_data, sample_id)

        if gps_data["ok"] and gps_data["connected"] and not gps_packet_sent_for_connection:
            gps_packet_sent_for_connection = True

        if gps_data["ok"] and gps_data["fix"] and not gps_fix_packet_sent_for_connection:
            gps_fix_packet_sent_for_connection = True

        rfm_packets = build_rfm_packets(sample_id, telemetry_line, ts, tmp36_data, bme_data, mpu_data, mag_data, gps_data)
        if FLASH_LOG_ENABLED:
            if not flash_log_write_enabled:
                current_sd_status = "low_space" if flash_log_last_error and str(flash_log_last_error).startswith("LOW_SPACE") else False
            else:
                current_sd_status = True
        else:
            current_sd_status = False

        # ---------- RFM SEND ----------
        current_rfm_status = rfm_was_ok
        all_rfm_ok = True
        rfm_no_ack = False
        if rfm_spi_restore_needed:
            restore_rfm_bus()

        for packet_index, packet in enumerate(rfm_packets):
            rfm_tx_line = fit_rfm_payload(packet)

            if RFM_LOG_EVERY_SEND:
                tx_attempt_log = log_line(ts, "INFO", "RFM69", "TX_ATTEMPT {}".format(rfm_tx_line))
                print(tx_attempt_log)
                queue_sd_log(tx_attempt_log)

            rfm_ok = rfm.send_line(rfm_tx_line)

            if rfm_ok:
                blink_rfm_ack()
                if RFM_LOG_EVERY_SEND:
                    tx_ok_log = log_line(ts, "INFO", "RFM69", "TX_OK {}".format(rfm_tx_line))
                    print(tx_ok_log)
                    queue_sd_log(tx_ok_log)
            else:
                all_rfm_ok = False
                rfm_no_ack = is_no_ack_error(rfm.last_error)
                error_label = "NO_ACK" if rfm_no_ack else "TX_FAIL"
                tx_fail_log = log_line(
                    ts,
                    "ERROR",
                    "RFM69",
                    "{} {} ERROR={}".format(error_label, rfm_tx_line, rfm.last_error)
                )
                print(tx_fail_log)
                queue_sd_log(tx_fail_log)
                break

            if packet_index < len(rfm_packets) - 1:
                utime.sleep_ms(RFM_PACKET_GAP_MS)

        if all_rfm_ok:
            if FLASH_LOG_ENABLED:
                module_leds._set(MODULE_SD, module_leds.BLUE if flash_log_write_enabled else module_leds.ORANGE)
                module_leds.show()
                if flash_log_append_line(telemetry_line):
                    current_sd_status = "saved"
                    sd_was_ok = True
                else:
                    if flash_log_last_error and str(flash_log_last_error).startswith("LOW_SPACE"):
                        current_sd_status = "low_space"
                    else:
                        current_sd_status = False
                    sd_was_ok = False

            if not rfm_status_ok(rfm_was_ok):
                queue_sd_log(log_line(ts, "INFO", "RFM69", "RECONNECTED"))
            if RFM_STATUS_EVERY_SAMPLES and sample_id % RFM_STATUS_EVERY_SAMPLES == 0:
                print("{} [INFO] RFM69 TX_OK sample={} packets={}".format(ts, sample_id, len(rfm_packets)))
            current_rfm_status = True
        else:
            if rfm_no_ack:
                current_rfm_status = "no_ack"
            else:
                current_rfm_status = False

            if rfm_status_ok(rfm_was_ok):
                queue_sd_log(log_line(ts, "ERROR", "RFM69", rfm.last_error))

            if not rfm_no_ack and retry_due(last_rfm_reconnect_ms, RFM_RECONNECT_INTERVAL_MS):
                rfm.reconnect()
                last_rfm_reconnect_ms = utime.ticks_ms()

        rfm_was_ok = current_rfm_status

        # ---------- LED STATUS ----------
        status_map = {
            "rtc": rtc_data["ok"],
            "tmp36": tmp36_data["ok"],
            "bme": bme_data["ok"],
            "mpu": mpu_data["ok"],
            "mag": mag_data["ok"],
            "sd": current_sd_status,
            "gps": gps_led_state(gps_data),
            "rfm": current_rfm_status,
        }
        if DEBUG_TELEMETRY and (
            not DEBUG_TELEMETRY_EVERY_SAMPLES
            or sample_id % DEBUG_TELEMETRY_EVERY_SAMPLES == 0
        ):
            print(telemetry_line)
        update_status_leds(status_map, sample_id)
        sample_id = (sample_id + 1) % 1000000

    except Exception as e:
        print("MAIN LOOP ERROR:", e)
        mission_led._set(0, mission_led.RED)
        mission_led.show()
        utime.sleep_ms(LED_MAIN_ERROR_RED_MS)
        mission_led._set(0, mission_led.OFF)
        mission_led.show()
        queue_sd_log(log_line("RTC_ERR", "ERROR", "MAIN", str(e)))

    elapsed_ms = utime.ticks_diff(utime.ticks_ms(), loop_start_ms)
    sleep_ms = LOOP_PERIOD_MS - elapsed_ms
    if sleep_ms > 0:
        utime.sleep_ms(sleep_ms)

