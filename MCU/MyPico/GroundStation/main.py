from machine import Pin
import utime

from sdcard import SDModule
from rfm69 import RFM69


# =========================
# CONFIG
# =========================

# SD card SPI
SD_SCK_PIN = 3
SD_MOSI_PIN = 2
SD_MISO_PIN = 4
SD_CS_PIN = 16
SD_BAUDRATE = 500000
SD_MOUNT_POINT = "/sd"
SD_DATA_FILENAME = "ground_data.txt"
SD_LOG_FILENAME = "ground_logs.txt"

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
RFM_RECEIVE_TIMEOUT_MS = 250
RFM_RECONNECT_INTERVAL_MS = 3000
NO_PACKET_LOG_INTERVAL_MS = 3000
DEBUG_RFM = True
LOOP_DELAY_MS = 20

# Onboard LED
LED_PIN = "LED"
LED_BLINK_MS = 80


# =========================
# HELPERS
# =========================
def now_text():
    return "MS={}".format(utime.ticks_ms())


def log_line(timestamp, level, source, message):
    return "{} [{}] {} {}".format(timestamp, level, source, message)


def received_line(timestamp, packet):
    return "{} RX {}".format(timestamp, packet)


def debug_line(timestamp, status):
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


def print_and_log(line):
    print(line)
    sdmod.write_log(line)


def blink_message_led():
    try:
        message_led.on()
        utime.sleep_ms(LED_BLINK_MS)
        message_led.off()
    except Exception:
        pass


# =========================
# INIT LED
# =========================
message_led = Pin(LED_PIN, Pin.OUT)
message_led.off()


# =========================
# INIT SD MODULE
# =========================
sdmod = SDModule(
    sck_pin=SD_SCK_PIN,
    mosi_pin=SD_MOSI_PIN,
    miso_pin=SD_MISO_PIN,
    cs_pin=SD_CS_PIN,
    baudrate=SD_BAUDRATE,
    mount_point=SD_MOUNT_POINT,
    data_filename=SD_DATA_FILENAME,
    log_filename=SD_LOG_FILENAME
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

print("GROUND RFM CONFIG: SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} FREQ={}MHz BITRATE={}".format(
    RFM_SCK_PIN,
    RFM_MOSI_PIN,
    RFM_MISO_PIN,
    RFM_CS_PIN,
    RFM_FREQ_MHZ,
    RFM_BITRATE
))

print("GROUND SD CONFIG: SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} DATA={} LOG={}".format(
    SD_SCK_PIN,
    SD_MOSI_PIN,
    SD_MISO_PIN,
    SD_CS_PIN,
    SD_DATA_FILENAME,
    SD_LOG_FILENAME
))

sdmod.write_log(log_line(now_text(), "INFO", "GROUND", "STARTED"))

if DEBUG_RFM:
    line = debug_line(now_text(), rfm.debug_status())
    print_and_log(line)


# =========================
# STATUS FLAGS
# =========================
sd_was_ok = sdmod.ok
rfm_was_ok = rfm.ok
last_no_packet_log_ms = utime.ticks_ms()
last_rfm_reconnect_ms = utime.ticks_ms()
last_rfm_error = None


# =========================
# MAIN LOOP
# =========================
while True:
    ts = now_text()

    try:
        if not rfm.ok:
            now_ms = utime.ticks_ms()

            if utime.ticks_diff(now_ms, last_rfm_reconnect_ms) >= RFM_RECONNECT_INTERVAL_MS:
                line = log_line(ts, "WARN", "RFM69", "TRYING_RECONNECT {}".format(rfm.last_error))
                print_and_log(line)
                last_rfm_reconnect_ms = now_ms

                if rfm.reconnect():
                    print_and_log(log_line(now_text(), "INFO", "RFM69", "RECONNECTED"))
                    if DEBUG_RFM:
                        print_and_log(debug_line(now_text(), rfm.debug_status()))
                else:
                    print_and_log(log_line(now_text(), "ERROR", "RFM69", "RECONNECT_FAILED {}".format(rfm.last_error)))

            rfm_was_ok = rfm.ok
            utime.sleep_ms(LOOP_DELAY_MS)
            continue

        packet = rfm.receive_line(timeout_ms=RFM_RECEIVE_TIMEOUT_MS)

        if rfm.ok:
            if not rfm_was_ok:
                print_and_log(log_line(ts, "INFO", "RFM69", "RECONNECTED"))
            rfm_was_ok = True
        else:
            if rfm_was_ok:
                print_and_log(log_line(ts, "ERROR", "RFM69", rfm.last_error))
            rfm_was_ok = False

        if packet is not None:
            last_no_packet_log_ms = utime.ticks_ms()
            blink_message_led()
            line = received_line(ts, packet)
            print(line)

            data_ok = sdmod.write_data(line)

            if data_ok:
                if not sd_was_ok:
                    sdmod.write_log(log_line(ts, "INFO", "SD", "RECONNECTED"))
                sd_was_ok = True
            else:
                if sd_was_ok:
                    print("SD WRITE ERROR:", sdmod.last_error)
                sd_was_ok = False
        else:
            now_ms = utime.ticks_ms()

            if rfm.last_error is not None and rfm.last_error != last_rfm_error:
                print_and_log(log_line(ts, "WARN", "RFM69", rfm.last_error))
                last_rfm_error = rfm.last_error

            if utime.ticks_diff(now_ms, last_no_packet_log_ms) >= NO_PACKET_LOG_INTERVAL_MS:
                line = log_line(ts, "DEBUG", "RFM69", "NO_MESSAGE")
                print_and_log(line)

                if DEBUG_RFM:
                    print_and_log(debug_line(ts, rfm.debug_status()))

                last_no_packet_log_ms = now_ms

    except Exception as e:
        print("GROUND LOOP ERROR:", e)
        sdmod.write_log(log_line(ts, "ERROR", "MAIN", str(e)))

    utime.sleep_ms(LOOP_DELAY_MS)
