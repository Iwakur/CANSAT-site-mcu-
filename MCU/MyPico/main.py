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

# BMP580
BMP_ADDRESS = None
BMP_SEA_LEVEL_PRESSURE = 1013.25
 
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
RFM_CS_PIN = 6
RFM_RST_PIN = None
RFM_FREQ_MHZ = 434.0
RFM_BITRATE = 4800
RFM_TX_POWER_DBM = 13
RFM_MAX_PAYLOAD_BYTES = 60
RFM_LOG_EVERY_SEND = False
DEBUG_TELEMETRY = True
DEBUG_TELEMETRY_EVERY_SAMPLES = 10
RFM_STATUS_EVERY_SAMPLES = 10

# Main loop
LOOP_DELAY_MS = 200
SENSOR_RECONNECT_INTERVAL_MS = 30000
RFM_RECONNECT_INTERVAL_MS = 10000

# =========================
# LED TIMINGS
# =========================
LED_INIT_CHECK_MS = 20
LED_INIT_RESULT_MS = 40

LED_CYCLE_CHECK_MS = 10
LED_CYCLE_RESULT_MS = 20

LED_BETWEEN_CYCLES_MS = 20
LED_BLUE_BIP_MS = 15
LED_DARK_BIP_MS = 10

LED_MAIN_ERROR_RED_MS = 60



# =========================
# HELPERS
# =========================
# Helper functions and wrapper classes live in helpers.py.


# =========================
# INIT LEDS
# =========================
leds = StatusLEDs(pin_num=LED_PIN, count=LED_COUNT, brightness=20)
configure_helpers(
    rfm_max_payload_bytes=RFM_MAX_PAYLOAD_BYTES,
    leds_obj=leds,
    led_count=LED_COUNT,
    led_rtc=LED_RTC,
    led_bmp=LED_BMP,
    led_bme=LED_BME,
    led_mpu=LED_MPU,
    led_sd=LED_SD,
    led_gps=LED_GPS,
    led_rfm=LED_RFM,
    led_mag=LED_MAG,
    led_init_check_ms=LED_INIT_CHECK_MS,
    led_init_result_ms=LED_INIT_RESULT_MS,
    led_cycle_check_ms=LED_CYCLE_CHECK_MS,
    led_cycle_result_ms=LED_CYCLE_RESULT_MS,
    led_between_cycles_ms=LED_BETWEEN_CYCLES_MS,
    led_blue_bip_ms=LED_BLUE_BIP_MS,
    led_dark_bip_ms=LED_DARK_BIP_MS,
)
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
rtc.set_datetime(2026, 4, 19, 7, 18, 25, 40)
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
last_bmp_reconnect_ms = utime.ticks_ms()
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
        telemetry_line = format_telemetry_line(ts, bmp_data, bme_data, mpu_data, tmp36_data, mag_data, gps_data)

        if gps_data["ok"] and gps_data["connected"] and not gps_packet_sent_for_connection:
            gps_packet_sent_for_connection = True

        if gps_data["ok"] and gps_data["fix"] and not gps_fix_packet_sent_for_connection:
            gps_fix_packet_sent_for_connection = True

        rfm_packets = build_rfm_packets(
            sample_id,
            ts,
            bmp_data,
            bme_data,
            tmp36_data,
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
        if DEBUG_TELEMETRY and (
            not DEBUG_TELEMETRY_EVERY_SAMPLES
            or sample_id % DEBUG_TELEMETRY_EVERY_SAMPLES == 0
        ):
            print(telemetry_line)
        show_two_status_cycles(status_map)
        sample_id = (sample_id + 1) % 10000

    except Exception as e:
        print("MAIN LOOP ERROR:", e)
        leds.blink_all(leds.RED, LED_MAIN_ERROR_RED_MS)
        sdmod.write_log(log_line("RTC_ERR", "ERROR", "MAIN", str(e)))

    utime.sleep_ms(LOOP_DELAY_MS)
