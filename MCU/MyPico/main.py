from machine import Pin, I2C
import utime

from rtc import DS1302
from bmp580 import BMP580
from bme688 import BME688
from mpu6500 import MPU6500
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
BMP_ADDRESS = 0x47
BMP_SEA_LEVEL_PRESSURE = 1013.25

# BME688
BME_ADDRESS = 0x77
BME_SEA_LEVEL_PRESSURE = 1013.25

# MPU6500
MPU_ADDRESS = 0x68
MPU_DO_CALIBRATION = True
MPU_CALIBRATION_SAMPLES = 300

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
LED_EMPTY = 3

# RFM69
RFM_SCK_PIN = SD_SCK_PIN
RFM_MOSI_PIN = SD_MOSI_PIN
RFM_MISO_PIN = SD_MISO_PIN
RFM_CS_PIN = 14
RFM_RST_PIN = None
RFM_FREQ_MHZ = 434.0
RFM_BITRATE = 4800
RFM_TX_POWER_DBM = 13

# Main loop
LOOP_DELAY_MS = 1000

# =========================
# LED TIMINGS
# =========================
LED_INIT_CHECK_MS = 120
LED_INIT_RESULT_MS = 180

LED_CYCLE_CHECK_MS = 80
LED_CYCLE_RESULT_MS = 120

LED_BETWEEN_CYCLES_MS = 180
LED_BLUE_BIP_MS = 80
LED_DARK_BIP_MS = 80

LED_MAIN_ERROR_RED_MS = 200


# =========================
# HELPERS
# =========================
def now_text(rtc_data):
    if rtc_data["ok"]:
        return rtc_data["datetime"]
    return "RTC_ERR"


def log_line(timestamp, level, source, message):
    return "{} [{}] {} {}".format(timestamp, level, source, message)


def led_off(index):
    # Try common method names because I don't have your exact class here.
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

    # Cycle 2: SD, GPS, RFM, empty
    show_led_status(LED_SD, status_map["sd"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_GPS, status_map["gps"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)
    show_led_status(LED_RFM, status_map["rfm"], LED_CYCLE_CHECK_MS, LED_CYCLE_RESULT_MS)

    led_off(LED_EMPTY)
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
    show_init_module(LED_SD, init_status_map["sd"])
    show_init_module(LED_GPS, init_status_map["gps"])
    show_init_module(LED_RFM, init_status_map["rfm"])

    led_off(LED_EMPTY)
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
rtc = DS1302(
    clk=RTC_CLK_PIN,
    dat=RTC_DAT_PIN,
    rst=RTC_RST_PIN
)
rtc_test = rtc.read()
print("RTC INIT:", rtc_test)


# =========================
# INIT BMP580
# =========================
bmp = BMP580(
    i2c=i2c,
    address=BMP_ADDRESS,
    sea_level_pressure=BMP_SEA_LEVEL_PRESSURE,
    pressure_osr=BMP580.OSR128,
    temperature_osr=BMP580.OSR8,
    iir_coef=BMP580.COEF_7,
)
bmp_test = bmp.read()
print("BMP INIT:", bmp_test)


# =========================
# INIT BME688
# =========================
bme = BME688(
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
)
bme_test = bme.read()
print("BME INIT:", bme_test)


# =========================
# INIT MPU6500
# =========================
mpu = MPU6500(
    i2c=i2c,
    addr=MPU_ADDRESS
)

if MPU_DO_CALIBRATION and mpu.ok:
    print("MPU6500 CALIBRATION: keep the board still")
    mpu.calibrate(samples=MPU_CALIBRATION_SAMPLES)
    print("MPU6500 CALIBRATION DONE")

mpu_test = mpu.read()
print("MPU INIT:", mpu_test)


# =========================
# INIT GPS
# =========================
print("GPS INIT: UART{} RX={} TX={}".format(GPS_UART_ID, GPS_RX_PIN, GPS_TX_PIN))
gps = GPS6MV2(
    uart_id=GPS_UART_ID,
    rx_pin=GPS_RX_PIN,
    tx_pin=GPS_TX_PIN,
    baudrate=GPS_BAUDRATE,
    debug=GPS_DEBUG
)
gps_test = gps.read()
print("GPS INIT:", gps_test)


# =========================
# INIT SD MODULE
# =========================
sdmod = SDModule(
    sck_pin=SD_SCK_PIN,
    mosi_pin=SD_MOSI_PIN,
    miso_pin=SD_MISO_PIN,
    cs_pin=SD_CS_PIN,
    baudrate=SD_BAUDRATE,
    mount_point="/sd",
    data_filename="data.txt",
    log_filename="logs.txt"
)

if sdmod.ok:
    print("SD CARD READY")
else:
    print("SD CARD NOT READY:", sdmod.last_error)


# =========================
# INIT RFM69
# =========================
rfm = RFM69(
    sck_pin=RFM_SCK_PIN,
    mosi_pin=RFM_MOSI_PIN,
    miso_pin=RFM_MISO_PIN,
    cs_pin=RFM_CS_PIN,
    rst_pin=RFM_RST_PIN,
    frequency_mhz=RFM_FREQ_MHZ,
    bitrate=RFM_BITRATE,
    tx_power_dbm=RFM_TX_POWER_DBM
)

if rfm.ok:
    print("RFM69 READY")
else:
    print("RFM69 NOT READY:", rfm.last_error)


# =========================
# SHOW INIT STATUS CYCLES
# =========================
init_status_map = {
    "rtc": rtc_test["ok"],
    "bmp": bmp_test["ok"],
    "bme": bme_test["ok"],
    "mpu": mpu_test["ok"],
    "sd": sdmod.ok,
    "gps": gps_test["ok"],
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
gps_was_ok = gps_test["ok"]
gps_had_fix = gps_test["fix"] if gps_test["ok"] else False
sd_was_ok = sdmod.ok
rfm_was_ok = rfm.ok


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
                print("RTC RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "RTC", "RECONNECTED"))
            rtc_was_ok = True
        else:
            print("RTC FAILED:", rtc_data.get("error", "unknown"))
            rtc.reconnect()
            rtc_was_ok = False

        # ---------- BMP580 ----------
        bmp_data = bmp.read()

        if bmp_data["ok"]:
            if not bmp_was_ok:
                print("BMP580 RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "BMP580", "RECONNECTED"))
            bmp_was_ok = True
        else:
            if bmp_was_ok:
                print("BMP580 FAILED:", bmp_data.get("error", "unknown"))
                sdmod.write_log(log_line(ts, "ERROR", "BMP580", bmp_data.get("error", "unknown")))
            bmp.reconnect()
            bmp_was_ok = False

        # ---------- BME688 ----------
        bme_data = bme.read()

        if bme_data["ok"]:
            if not bme_was_ok:
                print("BME688 RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "BME688", "RECONNECTED"))
            bme_was_ok = True
        else:
            if bme_was_ok:
                print("BME688 FAILED:", bme_data.get("error", "unknown"))
                sdmod.write_log(log_line(ts, "ERROR", "BME688", bme_data.get("error", "unknown")))
            bme.reconnect()
            bme_was_ok = False

        # ---------- MPU6500 ----------
        mpu_data = mpu.read()

        if mpu_data["ok"]:
            if not mpu_was_ok:
                print("MPU6500 RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "MPU6500", "RECONNECTED"))
            mpu_was_ok = True
        else:
            if mpu_was_ok:
                print("MPU6500 FAILED:", mpu_data.get("error", "unknown"))
                sdmod.write_log(log_line(ts, "ERROR", "MPU6500", mpu_data.get("error", "unknown")))
            mpu.reconnect()
            mpu_was_ok = False

        # ---------- GPS ----------
        gps_data = gps.read()

        if gps_data["ok"]:
            if not gps_was_ok:
                print("GPS RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "GPS", "RECONNECTED"))
            gps_was_ok = True
        else:
            print("GPS FAILED:", gps_data.get("error", "unknown"))
            if gps_was_ok:
                sdmod.write_log(log_line(ts, "ERROR", "GPS", gps_data.get("error", "unknown")))
            gps.reconnect()
            gps_was_ok = False

        if gps_data["ok"] and gps_data["fix"]:
            if not gps_had_fix:
                print("GPS FIX ACQUIRED")
                sdmod.write_log(log_line(ts, "INFO", "GPS", "FIX_ACQUIRED"))
            gps_had_fix = True
        else:
            if gps_had_fix:
                print("GPS FIX LOST")
                sdmod.write_log(log_line(ts, "WARN", "GPS", "FIX_LOST"))
            gps_had_fix = False

        # ---------- SD WRITE / HEALTH ----------
        # SD health is judged by successful write later.
        # Start from previous value.
        current_sd_ok = sd_was_ok

        # ---------- RFM HEALTH ----------
        current_rfm_ok = rfm_was_ok

        # ---------- TELEMETRY FORMAT ----------
        if bmp_data["ok"]:
            bmp_text = "BMP[T={:.1f}C P={:.1f}hPa A={:.1f}m]".format(
                bmp_data["temperature_c"],
                bmp_data["pressure_hpa"],
                bmp_data["altitude_m"]
            )
        else:
            bmp_text = "BMP[ERR]"

        if bme_data["ok"]:
            gas_ohms = bme_data["gas_ohms"]
            gas_valid = bme_data["gas_valid"]

            if gas_ohms is None:
                gas_text = "None"
            else:
                gas_text = str(gas_ohms)

            bme_text = "BME[T={:.1f}C P={:.1f}hPa H={:.1f}% G={}ohm V={} A={:.1f}m]".format(
                bme_data["temperature_c"],
                bme_data["pressure_hpa"],
                bme_data["humidity_pct"],
                gas_text,
                int(gas_valid),
                bme_data["altitude_m"]
            )
        else:
            bme_text = "BME[ERR]"

        if mpu_data["ok"]:
            mpu_text = "MPU[Ax={:.2f}g Ay={:.2f}g Az={:.2f}g Gx={:.2f}dps Gy={:.2f}dps Gz={:.2f}dps Tmp={:.1f}C Pit={:.1f}deg Rol={:.1f}deg]".format(
                mpu_data["ax"],
                mpu_data["ay"],
                mpu_data["az"],
                mpu_data["gx"],
                mpu_data["gy"],
                mpu_data["gz"],
                mpu_data["temp"],
                mpu_data["pitch"],
                mpu_data["roll"]
            )
        else:
            mpu_text = "MPU[ERR]"

        if gps_data["ok"]:
            gps_text = (
                "GPS[CON={} FIX={} RTC={} UTC={} {} LAT={} LON={} ALT={}m "
                "HSPD={}kmh VSPD={}ms CRS={}deg SAT={}]"
            ).format(
                int(gps_data["connected"]),
                int(gps_data["fix"]),
                int(gps_data["rtc_update_ready"]),
                gps_data["utc_date"],
                gps_data["utc_time"],
                gps_data["latitude"],
                gps_data["longitude"],
                gps_data["absolute_altitude_m"],
                gps_data["horizontal_speed_kmh"],
                gps_data["vertical_speed_ms"],
                gps_data["compass_deg"],
                gps_data["satellites"],
            )
        else:
            gps_text = "GPS[ERR:{}]".format(gps_data.get("error", "unknown"))

        telemetry_line = "T={} {} {} {} {}".format(
            ts,
            bmp_text,
            bme_text,
            mpu_text,
            gps_text
        )

        print(telemetry_line)

        # ---------- SD WRITE ----------
        data_ok = sdmod.write_data(telemetry_line)

        if data_ok:
            if not sd_was_ok:
                print("SD RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "SD", "RECONNECTED"))
            current_sd_ok = True
        else:
            if sd_was_ok:
                print("SD FAILED:", sdmod.last_error)
            current_sd_ok = False

        sd_was_ok = current_sd_ok

        # ---------- RFM SEND ----------
        rfm_ok = rfm.send_line(telemetry_line)

        if rfm_ok:
            if not rfm_was_ok:
                print("RFM69 RECONNECTED")
                sdmod.write_log(log_line(ts, "INFO", "RFM69", "RECONNECTED"))
            current_rfm_ok = True
        else:
            if rfm_was_ok:
                print("RFM69 FAILED:", rfm.last_error)
                sdmod.write_log(log_line(ts, "ERROR", "RFM69", rfm.last_error))
            rfm.reconnect()
            current_rfm_ok = False

        rfm_was_ok = current_rfm_ok

        # ---------- LED STATUS CYCLES ----------
        status_map = {
            "rtc": rtc_data["ok"],
            "bmp": bmp_data["ok"],
            "bme": bme_data["ok"],
            "mpu": mpu_data["ok"],
            "sd": current_sd_ok,
            "gps": gps_data["ok"],
            "rfm": current_rfm_ok,
        }
        show_two_status_cycles(status_map)

    except Exception as e:
        print("MAIN LOOP ERROR:", e)
        leds.blink_all(leds.RED, LED_MAIN_ERROR_RED_MS)
        sdmod.write_log(log_line("RTC_ERR", "ERROR", "MAIN", str(e)))

    utime.sleep_ms(LOOP_DELAY_MS)