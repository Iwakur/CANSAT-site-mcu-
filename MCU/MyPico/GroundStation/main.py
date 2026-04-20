from machine import Pin
import math
import socket
import utime

try:
    import network
except ImportError:
    network = None

from sdcard import SDModule
from rfm69 import RFM69


# =========================
# CONFIG
# =========================

# WiFi / HTTP forwarding
WIFI_SSID = "Proximus-Home-01E0"
WIFI_PASSWORD = "wyyf9j26shyac"
SERVER_URL = "http://192.168.1.14/GitHub/CANSAT/Site/api/receive.php"
HTTP_SEND_ENABLED = True
HTTP_LOG_SEND_ENABLED = True
WIFI_RECONNECT_INTERVAL_MS = 5000

# SD card SPI
SD_SCK_PIN = 3
SD_MOSI_PIN = 2
SD_MISO_PIN = 4
SD_CS_PIN = 16
SD_BAUDRATE = 500000
SD_MOUNT_POINT = "/sd"
SD_DATA_FILENAME = "ground_data.txt"
SD_LOG_FILENAME = "ground_logs.txt"
SD_RECONNECT_INTERVAL_MS = 3000

# RFM69
RFM_SCK_PIN = SD_SCK_PIN
RFM_MOSI_PIN = SD_MOSI_PIN
RFM_MISO_PIN = SD_MISO_PIN
RFM_CS_PIN = 14
RFM_RST_PIN = None
RFM_FREQ_MHZ = 434.0
RFM_BITRATE = 4800
RFM_TX_POWER_DBM = 13

# Calculations
BME_SEA_LEVEL_PRESSURE = 1013.25

# Main loop
RFM_RECEIVE_TIMEOUT_MS = 120
RFM_RECONNECT_INTERVAL_MS = 3000
NO_PACKET_LOG_INTERVAL_MS = 3000
DEBUG_RFM = True
DEBUG_HTTP = True
DEBUG_SD = True
LOOP_DELAY_MS = 10

# Onboard LED
LED_PIN = "LED"
LED_BLINK_MS = 40


# =========================
# HELPERS
# =========================
def now_text():
    return "UP_MS={}".format(utime.ticks_ms())


def fmt_value(value, decimals=None, unit=""):
    if value is None:
        return "None"
    if decimals is None:
        return "{}{}".format(value, unit)
    fmt = "{:." + str(decimals) + "f}{}"
    return fmt.format(value, unit)


def safe_int(text):
    if text == "?":
        return None
    try:
        return int(text)
    except Exception:
        return None


def unscale(text, factor=1):
    value = safe_int(text)
    if value is None:
        return None
    return value / factor


def altitude_from_pressure(pressure_hpa, sea_level_pressure):
    if pressure_hpa is None or pressure_hpa <= 0:
        return None
    return 44330.77 * (1.0 - ((pressure_hpa / sea_level_pressure) ** 0.1902632))


def heading_from_mag(x, y):
    if x is None or y is None:
        return None
    heading = math.degrees(math.atan2(y, x))
    if heading < 0:
        heading += 360.0
    return heading


def pitch_roll_from_accel(ax, ay, az):
    if ax is None or ay is None or az is None:
        return None, None
    pitch = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
    roll = math.degrees(math.atan2(ay, math.sqrt(ax * ax + az * az)))
    return pitch, roll


def urlencode(text):
    safe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    out = ""
    for ch in str(text):
        if ch in safe:
            out += ch
        elif ch == " ":
            out += "+"
        else:
            for b in ch.encode("utf-8"):
                out += "%{:02X}".format(b)
    return out


def parse_http_url(url):
    if url.startswith("http://"):
        url = url[7:]
    if "/" in url:
        host_port, path = url.split("/", 1)
        path = "/" + path
    else:
        host_port = url
        path = "/"

    if ":" in host_port:
        host, port_text = host_port.rsplit(":", 1)
        port = int(port_text)
    else:
        host = host_port
        port = 80

    return host, port, path


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


def blink_message_led():
    try:
        message_led.on()
        utime.sleep_ms(LED_BLINK_MS)
        message_led.off()
    except Exception:
        pass


# =========================
# PACKET PARSING
# =========================
def parse_packet(packet):
    parts = packet.split(",")
    if len(parts) < 2:
        return None

    packet_type = parts[0]
    sample_id = parts[1]

    if packet_type == "E" and len(parts) >= 8:
        if len(parts) >= 10:
            bme_offset = 5
            tmp36_index = 9
        else:
            tmp36_index = 3
            bme_offset = 4

        return {
            "type": "E",
            "id": sample_id,
            "rtc": parts[2],
            "bme_t": unscale(parts[bme_offset], 10),
            "bme_p": unscale(parts[bme_offset + 1], 10),
            "bme_h": unscale(parts[bme_offset + 2], 10),
            "bme_g": safe_int(parts[bme_offset + 3]),
            "tmp36_t": unscale(parts[tmp36_index], 10) if len(parts) > tmp36_index else None,
        }

    if packet_type == "M" and len(parts) >= 4:
        subtype = parts[2]

        if subtype == "A" and len(parts) >= 9:
            return {
                "type": "A",
                "id": sample_id,
                "ax": unscale(parts[3], 1000),
                "ay": unscale(parts[4], 1000),
                "az": unscale(parts[5], 1000),
                "gx": unscale(parts[6], 100),
                "gy": unscale(parts[7], 100),
                "gz": unscale(parts[8], 100),
            }

        if subtype == "C" and len(parts) >= 6:
            return {
                "type": "C",
                "id": sample_id,
                "mx": safe_int(parts[3]),
                "my": safe_int(parts[4]),
                "mz": safe_int(parts[5]),
            }

    if packet_type == "G" and len(parts) >= 9:
        return {
            "type": "G",
            "id": sample_id,
            "gps_fix": safe_int(parts[2]) or 0,
            "gps_sat": safe_int(parts[3]),
            "gps_lat": unscale(parts[4], 1000000),
            "gps_lon": unscale(parts[5], 1000000),
            "gps_alt": unscale(parts[6], 10),
            "gps_date": None if parts[7] == "?" else parts[7],
            "gps_time": None if parts[8] == "?" else parts[8],
        }

    return None


def apply_packet(sample_cache, parsed):
    sample_id = parsed["id"]
    sample = sample_cache.get(sample_id, {"id": sample_id})
    sample.update(parsed)
    sample_cache[sample_id] = sample
    return sample


def readable_line(sample):
    rtc = sample.get("rtc") or "RTCERR"
    bme_p = sample.get("bme_p")
    ax = sample.get("ax")
    ay = sample.get("ay")
    az = sample.get("az")
    mx = sample.get("mx")
    my = sample.get("my")

    bme_alt = altitude_from_pressure(bme_p, BME_SEA_LEVEL_PRESSURE)
    pitch, roll = pitch_roll_from_accel(ax, ay, az)
    heading = heading_from_mag(mx, my)

    return (
        "T={} TMP36[T={}] "
        "BME[T={} P={} H={} G={}ohm A={}] "
        "MPU[Ax={} Ay={} Az={} Gx={} Gy={} Gz={} Pit={} Rol={}] "
        "MAG[X={} Y={} Z={} H={}] "
        "GPS[FIX={} SAT={} LAT={} LON={} ALT={}]"
    ).format(
        rtc,
        fmt_value(sample.get("tmp36_t"), 1, "C"),
        fmt_value(sample.get("bme_t"), 1, "C"),
        fmt_value(bme_p, 1, "hPa"),
        fmt_value(sample.get("bme_h"), 1, "%"),
        fmt_value(sample.get("bme_g")),
        fmt_value(bme_alt, 1, "m"),
        fmt_value(ax, 2, "g"),
        fmt_value(ay, 2, "g"),
        fmt_value(az, 2, "g"),
        fmt_value(sample.get("gx"), 2, "dps"),
        fmt_value(sample.get("gy"), 2, "dps"),
        fmt_value(sample.get("gz"), 2, "dps"),
        fmt_value(pitch, 1, "deg"),
        fmt_value(roll, 1, "deg"),
        fmt_value(mx),
        fmt_value(my),
        fmt_value(sample.get("mz")),
        fmt_value(heading, 1, "deg"),
        fmt_value(sample.get("gps_fix", 0)),
        fmt_value(sample.get("gps_sat")),
        fmt_value(sample.get("gps_lat")),
        fmt_value(sample.get("gps_lon")),
        fmt_value(sample.get("gps_alt"), 1, "m"),
    )


# =========================
# WIFI / HTTP
# =========================
wifi = None
last_wifi_reconnect_ms = 0
sdmod = None
rfm = None
_writing_status_log = False
_sending_status_log = False


def log_status(level, source, message):
    global _writing_status_log, _sending_status_log

    line = "{} [{}] {} {}".format(now_text(), level, source, message)
    print(line)

    if _writing_status_log:
        return

    try:
        if sdmod is not None and sdmod.ok:
            _writing_status_log = True
            sdmod.write_log(line)
    except Exception:
        pass
    _writing_status_log = False

    if HTTP_LOG_SEND_ENABLED and HTTP_SEND_ENABLED and wifi_connected() and not _sending_status_log:
        try:
            _sending_status_log = True
            send_http_payload(line, "log", source, False)
        except Exception:
            pass
        _sending_status_log = False


def wifi_connected():
    return wifi is not None and wifi.isconnected()


def connect_wifi():
    global wifi

    if not HTTP_SEND_ENABLED:
        log_status("INFO", "WIFI", "HTTP_SEND_DISABLED")
        return False

    if network is None:
        log_status("ERROR", "WIFI", "NETWORK_MODULE_NOT_AVAILABLE")
        return False

    try:
        if wifi is None:
            wifi = network.WLAN(network.STA_IF)
            wifi.active(True)

        if wifi.isconnected():
            return True

        log_status("INFO", "WIFI", "CONNECTING SSID={}".format(WIFI_SSID))
        wifi.connect(WIFI_SSID, WIFI_PASSWORD)

        start = utime.ticks_ms()
        while not wifi.isconnected():
            if utime.ticks_diff(utime.ticks_ms(), start) > 5000:
                log_status("ERROR", "WIFI", "CONNECT_TIMEOUT SSID={}".format(WIFI_SSID))
                return False
            utime.sleep_ms(100)

        log_status("INFO", "WIFI", "CONNECTED SSID={} IF={}".format(WIFI_SSID, wifi.ifconfig()))
        return True

    except Exception as e:
        log_status("ERROR", "WIFI", str(e))
        return False


def send_http_payload(line, payload_type="telemetry", source="ground_station", log_events=True):
    if not HTTP_SEND_ENABLED:
        if log_events:
            log_status("INFO", "HTTP", "SEND_DISABLED")
        return False

    if not wifi_connected():
        if log_events:
            log_status("WARN", "HTTP", "SKIP_WIFI_DOWN URL={}".format(SERVER_URL))
        return False

    url_text = SERVER_URL
    sock = None

    try:
        host, port, path = parse_http_url(SERVER_URL)
        query = "type={}&source={}&line={}".format(
            urlencode(payload_type),
            urlencode(source),
            urlencode(line)
        )
        full_path = "{}{}{}".format(path, "&" if "?" in path else "?", query)
        url_text = "http://{}:{}{}".format(host, port, full_path)

        if log_events:
            log_status("INFO", "HTTP", "GET type={}".format(payload_type))

        addr = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket()
        sock.settimeout(3)
        sock.connect(addr)
        request = (
            "GET {} HTTP/1.0\r\n"
            "Host: {}\r\n"
            "Connection: close\r\n\r\n"
        ).format(full_path, host)
        sock.send(request.encode("utf-8"))
        sock.close()
        if log_events:
            log_status("INFO", "HTTP", "SENT type={}".format(payload_type))
        return True

    except Exception as e:
        if log_events:
            log_status("ERROR", "HTTP", "GET_FAILED URL={} ERROR={}".format(url_text, e))
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
        return False


def send_http_get(line):
    return send_http_payload(line, "telemetry", "ground_station", True)


# =========================
# HOTPLUG MODULE HELPERS
# =========================
def init_sd():
    global sdmod

    try:
        log_status("INFO", "SD", "CONNECTING CS=GP{} DATA={}".format(SD_CS_PIN, SD_DATA_FILENAME))
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
            log_status("INFO", "SD", "CONNECTED DATA={}".format(SD_DATA_FILENAME))
            return True

        log_status("ERROR", "SD", "NOT_READY {}".format(sdmod.last_error))
        return False

    except Exception as e:
        sdmod = None
        log_status("ERROR", "SD", "INIT_FAILED {}".format(e))
        return False


def ensure_sd():
    global sdmod

    try:
        if sdmod is None:
            return init_sd()

        if sdmod.ok:
            return True

        log_status("WARN", "SD", "TRYING_RECONNECT {}".format(sdmod.last_error))
        if sdmod.reconnect():
            log_status("INFO", "SD", "RECONNECTED DATA={}".format(SD_DATA_FILENAME))
            return True

        log_status("ERROR", "SD", "RECONNECT_FAILED {}".format(sdmod.last_error))
        return False

    except Exception as e:
        log_status("ERROR", "SD", "ENSURE_FAILED {}".format(e))
        return False


def write_sd_data(line):
    global sdmod

    try:
        if not ensure_sd():
            return False

        if sdmod.write_data(line):
            if DEBUG_SD:
                log_status("INFO", "SD", "WRITE_OK DATA={}".format(SD_DATA_FILENAME))
            return True

        log_status("ERROR", "SD", "WRITE_FAILED {}".format(sdmod.last_error))
        return False

    except Exception as e:
        log_status("ERROR", "SD", "WRITE_EXCEPTION {}".format(e))
        try:
            sdmod.ok = False
            sdmod.last_error = str(e)
        except Exception:
            pass
        return False


def init_rfm():
    global rfm

    try:
        log_status("INFO", "RFM69", "CONNECTING CS=GP{} FREQ={}MHz".format(RFM_CS_PIN, RFM_FREQ_MHZ))
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
            log_status("INFO", "RFM69", "CONNECTED")
            return True

        log_status("ERROR", "RFM69", "NOT_READY {}".format(rfm.last_error))
        return False

    except Exception as e:
        rfm = None
        log_status("ERROR", "RFM69", "INIT_FAILED {}".format(e))
        return False


def ensure_rfm():
    global rfm

    try:
        if rfm is None:
            return init_rfm()

        if rfm.ok:
            return True

        log_status("WARN", "RFM69", "TRYING_RECONNECT {}".format(rfm.last_error))
        if rfm.reconnect():
            log_status("INFO", "RFM69", "RECONNECTED")
            if DEBUG_RFM:
                status_line = debug_line(now_text(), rfm.debug_status())
                print(status_line)
                try:
                    if sdmod is not None and sdmod.ok:
                        sdmod.write_log(status_line)
                except Exception:
                    pass
            return True

        log_status("ERROR", "RFM69", "RECONNECT_FAILED {}".format(rfm.last_error))
        return False

    except Exception as e:
        log_status("ERROR", "RFM69", "ENSURE_FAILED {}".format(e))
        return False


# =========================
# INIT LED
# =========================
message_led = Pin(LED_PIN, Pin.OUT)
message_led.off()


# =========================
# INIT SD MODULE
# =========================
init_sd()


# =========================
# INIT WIFI
# =========================
connect_wifi()


# =========================
# INIT RFM69
# =========================
init_rfm()

log_status("INFO", "RFM69", "CONFIG SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} FREQ={}MHz BITRATE={}".format(
    RFM_SCK_PIN,
    RFM_MOSI_PIN,
    RFM_MISO_PIN,
    RFM_CS_PIN,
    RFM_FREQ_MHZ,
    RFM_BITRATE
))

log_status("INFO", "SD", "CONFIG SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} DATA={} LOG={}".format(
    SD_SCK_PIN,
    SD_MOSI_PIN,
    SD_MISO_PIN,
    SD_CS_PIN,
    SD_DATA_FILENAME,
    SD_LOG_FILENAME
))

if DEBUG_RFM:
    if rfm is not None:
        status_line = debug_line(now_text(), rfm.debug_status())
        print(status_line)
        try:
            if sdmod is not None and sdmod.ok:
                sdmod.write_log(status_line)
        except Exception:
            pass
    else:
        log_status("DEBUG", "RFM69", "DEBUG_ERROR not initialized")


# =========================
# STATUS FLAGS
# =========================
sample_cache = {}
written_ids = {}
last_written_by_id = {}
sd_was_ok = sdmod.ok if sdmod is not None else False
rfm_was_ok = rfm.ok if rfm is not None else False
wifi_was_ok = wifi_connected()
last_no_packet_log_ms = utime.ticks_ms()
last_rfm_reconnect_ms = utime.ticks_ms()
last_sd_reconnect_ms = utime.ticks_ms()
last_rfm_error = None


# =========================
# MAIN LOOP
# =========================
while True:
    ts = now_text()

    try:
        current_sd_ok = sdmod is not None and sdmod.ok

        if current_sd_ok:
            if not sd_was_ok:
                log_status("INFO", "SD", "RECONNECTED DATA={}".format(SD_DATA_FILENAME))
            sd_was_ok = True
        else:
            if sd_was_ok:
                last_error = sdmod.last_error if sdmod is not None else "not initialized"
                log_status("WARN", "SD", "DISCONNECTED {}".format(last_error))
            sd_was_ok = False

            if utime.ticks_diff(utime.ticks_ms(), last_sd_reconnect_ms) >= SD_RECONNECT_INTERVAL_MS:
                ensure_sd()
                last_sd_reconnect_ms = utime.ticks_ms()

        current_wifi_ok = wifi_connected()

        if current_wifi_ok:
            if not wifi_was_ok:
                log_status("INFO", "WIFI", "RECONNECTED IF={}".format(wifi.ifconfig()))
            wifi_was_ok = True
        else:
            if wifi_was_ok:
                log_status("WARN", "WIFI", "DISCONNECTED")
            wifi_was_ok = False

        if HTTP_SEND_ENABLED and not current_wifi_ok:
            if utime.ticks_diff(utime.ticks_ms(), last_wifi_reconnect_ms) >= WIFI_RECONNECT_INTERVAL_MS:
                if connect_wifi():
                    wifi_was_ok = True
                last_wifi_reconnect_ms = utime.ticks_ms()

        if rfm is None or not rfm.ok:
            now_ms = utime.ticks_ms()

            if utime.ticks_diff(now_ms, last_rfm_reconnect_ms) >= RFM_RECONNECT_INTERVAL_MS:
                last_error = rfm.last_error if rfm is not None else "not initialized"
                log_status("WARN", "RFM69", "TRYING_RECONNECT {}".format(last_error))
                last_rfm_reconnect_ms = now_ms

                ensure_rfm()

            rfm_was_ok = rfm.ok if rfm is not None else False
            utime.sleep_ms(LOOP_DELAY_MS)
            continue

        packet = rfm.receive_line(timeout_ms=RFM_RECEIVE_TIMEOUT_MS)

        if rfm.ok:
            if not rfm_was_ok:
                log_status("INFO", "RFM69", "RECONNECTED")
            rfm_was_ok = True
        else:
            if rfm_was_ok:
                log_status("ERROR", "RFM69", str(rfm.last_error))
            rfm_was_ok = False

        if packet is not None:
            last_no_packet_log_ms = utime.ticks_ms()
            blink_message_led()
            log_status("INFO", "RFM69", "RX {}".format(packet))

            parsed = parse_packet(packet)
            if parsed is None:
                log_status("WARN", "RFM69", "BAD_PACKET {}".format(packet))
            else:
                sample = apply_packet(sample_cache, parsed)

                if parsed["type"] in ("G", "C"):
                    line = readable_line(sample)
                    if last_written_by_id.get(sample["id"]) != line:
                        print(line)

                        data_ok = write_sd_data(line)
                        if data_ok:
                            sd_was_ok = True
                        else:
                            sd_was_ok = False

                        send_http_get(line)
                        written_ids[sample["id"]] = True
                        last_written_by_id[sample["id"]] = line

                if len(sample_cache) > 8:
                    for key in list(sample_cache.keys()):
                        if key != sample.get("id"):
                            sample_cache.pop(key, None)
                            written_ids.pop(key, None)
                            last_written_by_id.pop(key, None)

        else:
            now_ms = utime.ticks_ms()

            if rfm.last_error is not None and rfm.last_error != last_rfm_error:
                log_status("WARN", "RFM69", str(rfm.last_error))
                last_rfm_error = rfm.last_error

            if utime.ticks_diff(now_ms, last_no_packet_log_ms) >= NO_PACKET_LOG_INTERVAL_MS:
                log_status("DEBUG", "RFM69", "NO_MESSAGE")

                if DEBUG_RFM:
                    status_line = debug_line(ts, rfm.debug_status())
                    print(status_line)
                    if HTTP_LOG_SEND_ENABLED and HTTP_SEND_ENABLED and wifi_connected():
                        send_http_payload(status_line, "log", "RFM69", False)
                    try:
                        if sdmod is not None and sdmod.ok:
                            sdmod.write_log(status_line)
                    except Exception:
                        pass

                last_no_packet_log_ms = now_ms

    except Exception as e:
        log_status("ERROR", "MAIN", str(e))

    utime.sleep_ms(LOOP_DELAY_MS)
