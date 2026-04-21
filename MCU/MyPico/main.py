from machine import Pin, I2C, SPI
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
MPU_DO_CALIBRATION = False
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
SD_BAUDRATE = 500000

# LED modules
MISSION_LED_PIN = 9
MODULE_LED_PIN = 10
MODULE_LED_COUNT = 8

MODULE_RTC = 0
MODULE_TMP36 = 1
MODULE_BME = 2
MODULE_MPU = 3
MODULE_MAG = 4
MODULE_GPS = 5
MODULE_SD = 6
MODULE_RFM = 7

# RFM69
RFM_SCK_PIN = SD_SCK_PIN
RFM_MOSI_PIN = SD_MOSI_PIN
RFM_MISO_PIN = SD_MISO_PIN
RFM_CS_PIN = 6
RFM_RST_PIN = None
RFM_SPI_ID = 0
RFM_SPI_BAUDRATE = 50000
RFM_FREQ_MHZ = 434.0
RFM_BITRATE = 4800
RFM_FREQ_DEVIATION = 90000
RFM_TX_POWER_DBM = 13
RFM_MAX_PAYLOAD_BYTES = 60
RFM_LOG_EVERY_SEND = False
DEBUG_TELEMETRY = True
DEBUG_TELEMETRY_EVERY_SAMPLES = 1
RFM_STATUS_EVERY_SAMPLES = 1

# Main loop
LOOP_PERIOD_MS = 1000
SENSOR_RECONNECT_INTERVAL_MS = 30000
RFM_RECONNECT_INTERVAL_MS = 10000

LED_MAIN_ERROR_RED_MS = 60



# =========================
# HELPERS
# =========================
# Helper functions and wrapper classes live in helpers.py.


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
        tx_power_dbm,
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
        self.tx_power_dbm = tx_power_dbm
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
                radio = RFM69(
                    sck_pin=self.sck_pin,
                    mosi_pin=self.mosi_pin,
                    miso_pin=self.miso_pin,
                    cs_pin=self.cs_pin,
                    rst_pin=self.rst_pin,
                    frequency_mhz=self.frequency_mhz,
                    bitrate=self.bitrate,
                    tx_power_dbm=self.tx_power_dbm
                )
                self.native_send_line = hasattr(radio, "send_line")
            except TypeError as e:
                if "sck_pin" not in str(e):
                    raise

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
                if hasattr(radio, "spi_write"):
                    radio.spi_write(0x02, 0x00)
                radio.frequency_mhz = self.frequency_mhz
                radio.bitrate = self.bitrate
                if hasattr(radio, "frequency_deviation"):
                    radio.frequency_deviation = self.frequency_deviation
                if hasattr(type(radio), "preamble_length"):
                    radio.preamble_length = 3
                if hasattr(type(radio), "packet_format"):
                    radio.packet_format = 1
                if hasattr(type(radio), "dc_free"):
                    radio.dc_free = 0
                if hasattr(type(radio), "crc_on"):
                    radio.crc_on = 1
                if hasattr(type(radio), "aes_on"):
                    radio.aes_on = 0
                if hasattr(radio, "tx_power"):
                    radio.tx_power = self.tx_power_dbm
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

    def send_line(self, text):
        try:
            if not self.ok:
                if not self.reconnect():
                    return False

            if self.native_send_line:
                result = self.radio.send_line(text)
                self.ok = getattr(self.radio, "ok", bool(result))
                self.last_error = getattr(self.radio, "last_error", None)
                return result

            payload = text.encode("utf-8")
            if len(payload) > RFM_MAX_PAYLOAD_BYTES:
                payload = payload[:RFM_MAX_PAYLOAD_BYTES]

            self._set_mode(self.MODE_STDBY)
            self._read_reg(self.REG_IRQFLAGS1)
            self._read_reg(self.REG_IRQFLAGS2)
            self.radio.spi_write_fifo(payload)
            self._set_mode(self.MODE_TX)

            start = utime.ticks_ms()
            while True:
                if self._read_reg(self.REG_IRQFLAGS2) & 0x08:
                    break
                if utime.ticks_diff(utime.ticks_ms(), start) > 500:
                    raise OSError("rfm tx timeout")
                utime.sleep_ms(5)

            self._set_mode(self.MODE_STDBY)
            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            try:
                self._set_mode(self.MODE_STDBY)
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


def format_telemetry_line(ts, tmp_data, bme_data, mpu_data, mag_data, gps_data):
    return "T={} {} {} {} {} {}".format(
        ts,
        format_tmp36_text(tmp_data),
        format_bme_text(bme_data),
        format_mpu_text(mpu_data),
        format_mag_text(mag_data),
        format_gps_text(gps_data)
    )


def build_env_packet(sample_id, ts, tmp_data, bme_data):
    tmp_temp = tmp_data["temperature_c"] if tmp_data["ok"] else None
    bme_temp = bme_data["temperature_c"] if bme_data["ok"] else None
    bme_pressure = bme_data["pressure_hpa"] if bme_data["ok"] else None
    bme_humidity = bme_data["humidity_pct"] if bme_data["ok"] else None
    bme_gas = bme_data["gas_ohms"] if bme_data["ok"] else None

    return "E,{},{},{},{},{},{},{}".format(
        sample_id,
        short_time(ts),
        scale_int(tmp_temp, 10),
        scale_int(bme_temp, 10),
        scale_int(bme_pressure, 10),
        scale_int(bme_humidity, 10),
        scale_int(bme_gas),
    )


def build_rfm_packets(sample_id, ts, tmp_data, bme_data, mpu_data, mag_data, gps_data):
    return [
        build_env_packet(sample_id, ts, tmp_data, bme_data),
        build_motion_packet(sample_id, mpu_data),
        build_mag_packet(sample_id, mag_data),
        build_gps_packet(sample_id, gps_data),
    ]


def bool_status_color(ok):
    return module_leds.GREEN if ok else module_leds.RED


def gps_status_color(gps_state):
    if gps_state == "fix":
        return module_leds.GREEN
    if gps_state == "connected":
        return module_leds.BLUE
    return module_leds.RED


def mission_health_level(status_map):
    module_failures = 0

    for key in ("rtc", "tmp36", "bme", "mpu", "mag", "sd", "rfm"):
        if not status_map.get(key):
            module_failures += 1

    if status_map.get("gps") != "fix":
        module_failures += 1

    if module_failures >= 3:
        return "critical"

    if not status_map.get("rfm"):
        return "warning"

    if module_failures == 0:
        return "good"

    return "warning"


def update_module_leds(status_map):
    module_leds._set(MODULE_RTC, bool_status_color(status_map["rtc"]))
    module_leds._set(MODULE_TMP36, bool_status_color(status_map["tmp36"]))
    module_leds._set(MODULE_BME, bool_status_color(status_map["bme"]))
    module_leds._set(MODULE_MPU, bool_status_color(status_map["mpu"]))
    module_leds._set(MODULE_MAG, bool_status_color(status_map["mag"]))
    module_leds._set(MODULE_GPS, gps_status_color(status_map["gps"]))
    module_leds._set(MODULE_SD, bool_status_color(status_map["sd"]))
    module_leds._set(MODULE_RFM, bool_status_color(status_map["rfm"]))
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

    mission_led._set(0, color if pulse_on else mission_led.OFF)
    mission_led.show()


def update_status_leds(status_map, sample_id):
    update_module_leds(status_map)
    update_mission_led(status_map, sample_id)


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
rtc.set_datetime(2026, 4, 19, 7, 18, 25, 40)
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
# PREPARE SHARED SPI BUS
# =========================
Pin(SD_CS_PIN, Pin.OUT, value=1)
Pin(RFM_CS_PIN, Pin.OUT, value=1)


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
    sdmod = NullSDModule(sdmod.last_error)


# =========================
# INIT RFM69
# =========================
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
        tx_power_dbm=RFM_TX_POWER_DBM
    ),
    lambda error_text: {"ok": False, "error": error_text}
)

if rfm.ok:
    print("RFM69 READY")
else:
    print("RFM69 NOT READY:", rfm.last_error)

print("CANSAT RFM CONFIG: SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} FREQ={}MHz BITRATE={} FDEV={} TX_POWER={}dBm".format(
    RFM_SCK_PIN,
    RFM_MOSI_PIN,
    RFM_MISO_PIN,
    RFM_CS_PIN,
    RFM_FREQ_MHZ,
    RFM_BITRATE,
    RFM_FREQ_DEVIATION,
    RFM_TX_POWER_DBM
))

sdmod.write_log(log_line(
    now_text(rtc_test),
    "INFO",
    "RFM69",
    "CONFIG SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} FREQ={}MHz BITRATE={} FDEV={} TX_POWER={}dBm".format(
        RFM_SCK_PIN,
        RFM_MOSI_PIN,
        RFM_MISO_PIN,
        RFM_CS_PIN,
        RFM_FREQ_MHZ,
        RFM_BITRATE,
        RFM_FREQ_DEVIATION,
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
    "tmp36": tmp36_test["ok"],
    "bme": bme_test["ok"],
    "mpu": mpu_test["ok"],
    "mag": mag_test["ok"],
    "sd": sdmod.ok,
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
sd_was_ok = sdmod.ok
rfm_was_ok = rfm.ok
sample_id = 0
gps_time_synced_for_connection = False
gps_packet_sent_for_connection = False
gps_fix_packet_sent_for_connection = False

last_rtc_reconnect_ms = utime.ticks_ms()
last_bme_reconnect_ms = utime.ticks_ms()
last_mpu_reconnect_ms = utime.ticks_ms()
last_tmp36_reconnect_ms = utime.ticks_ms()
last_mag_reconnect_ms = utime.ticks_ms()
last_gps_reconnect_ms = utime.ticks_ms()
last_rfm_reconnect_ms = utime.ticks_ms()


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
                sdmod.write_log(log_line(ts, "INFO", "RTC", "RECONNECTED"))
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
                sdmod.write_log(log_line(ts, "INFO", "TMP36", "RECONNECTED"))
            tmp36_was_ok = True
        else:
            if tmp36_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "TMP36", tmp36_data.get("error", "unknown")))
            if retry_due(last_tmp36_reconnect_ms, SENSOR_RECONNECT_INTERVAL_MS):
                tmp36.reconnect()
                last_tmp36_reconnect_ms = utime.ticks_ms()
            tmp36_was_ok = False

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
        telemetry_line = format_telemetry_line(ts, tmp36_data, bme_data, mpu_data, mag_data, gps_data)

        if gps_data["ok"] and gps_data["connected"] and not gps_packet_sent_for_connection:
            gps_packet_sent_for_connection = True

        if gps_data["ok"] and gps_data["fix"] and not gps_fix_packet_sent_for_connection:
            gps_fix_packet_sent_for_connection = True

        rfm_packets = build_rfm_packets(
            sample_id,
            ts,
            tmp36_data,
            bme_data,
            mpu_data,
            mag_data,
            gps_data
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
            if RFM_STATUS_EVERY_SAMPLES and sample_id % RFM_STATUS_EVERY_SAMPLES == 0:
                print("{} [INFO] RFM69 TX_OK sample={} packets={}".format(ts, sample_id, len(rfm_packets)))
            current_rfm_ok = True
        else:
            if rfm_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "RFM69", rfm.last_error))
            if retry_due(last_rfm_reconnect_ms, RFM_RECONNECT_INTERVAL_MS):
                rfm.reconnect()
                last_rfm_reconnect_ms = utime.ticks_ms()
            current_rfm_ok = False

        rfm_was_ok = current_rfm_ok

        # ---------- LED STATUS ----------
        status_map = {
            "rtc": rtc_data["ok"],
            "tmp36": tmp36_data["ok"],
            "bme": bme_data["ok"],
            "mpu": mpu_data["ok"],
            "mag": mag_data["ok"],
            "sd": current_sd_ok,
            "gps": gps_led_state(gps_data),
            "rfm": current_rfm_ok,
        }
        if DEBUG_TELEMETRY and (
            not DEBUG_TELEMETRY_EVERY_SAMPLES
            or sample_id % DEBUG_TELEMETRY_EVERY_SAMPLES == 0
        ):
            print(telemetry_line)
        update_status_leds(status_map, sample_id)
        sample_id = (sample_id + 1) % 10000

    except Exception as e:
        print("MAIN LOOP ERROR:", e)
        mission_led._set(0, mission_led.RED)
        mission_led.show()
        utime.sleep_ms(LED_MAIN_ERROR_RED_MS)
        mission_led._set(0, mission_led.OFF)
        mission_led.show()
        sdmod.write_log(log_line("RTC_ERR", "ERROR", "MAIN", str(e)))

    elapsed_ms = utime.ticks_diff(utime.ticks_ms(), loop_start_ms)
    sleep_ms = LOOP_PERIOD_MS - elapsed_ms
    if sleep_ms > 0:
        utime.sleep_ms(sleep_ms)
