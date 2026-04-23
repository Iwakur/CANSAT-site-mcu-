from machine import Pin, SPI
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
WIFI_SSID = "A26"  #TP-Link_7AA4_5G
WIFI_PASSWORD = "1234567890g"     #87102048
SERVER_URL = "http://10.150.65.230/GitHub/CANSAT/Site/api/receive.php"
HTTP_SEND_ENABLED = True
HTTP_LOG_SEND_ENABLED = True
WIFI_RECONNECT_INTERVAL_MS = 5000

# SD card SPI
SD_SCK_PIN = 2
SD_MOSI_PIN = 3
SD_MISO_PIN = 4
SD_CS_PIN = 5
SD_BAUDRATE = 500000
SD_MOUNT_POINT = "/sd"
SD_DATA_FILENAME = "ground_data.txt"
SD_LOG_FILENAME = "ground_logs.txt"
SD_WRITE_ENABLED = False
SD_RECONNECT_ENABLED = False
SD_RECONNECT_INTERVAL_MS = 1000

# RFM69
RFM_SCK_PIN = SD_SCK_PIN
RFM_MOSI_PIN = SD_MOSI_PIN
RFM_MISO_PIN = SD_MISO_PIN
RFM_CS_PIN = 6
RFM_RST_PIN = 15
RFM_SPI_ID = 0
RFM_SPI_BAUDRATE = 50000
RFM_FREQ_MHZ = 433.3
RFM_BITRATE = 9600
RFM_FREQ_DEVIATION = 19000
RFM_RX_BW_REG = 0x43
RFM_AFC_BW_REG = 0x42
RFM_PREAMBLE_LENGTH = 8
RFM_TX_POWER_DBM = 20
RFM_NODE_ID = 0xA6
RFM_DESTINATION_ID = 0xCA
RFM_ENCRYPTION_KEY = b"CANSAT2026RFM69!"

# Main loop
RFM_RECEIVE_TIMEOUT_MS = 1000
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


class GroundRFM69:
    REG_VERSION = 0x10
    REG_OPMODE = 0x01
    REG_IRQFLAGS1 = 0x27
    REG_IRQFLAGS2 = 0x28
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
        self.encryption_key = encryption_key
        self.spi = None
        self.nss = None
        self.reset_pin = None
        self.radio = None
        self.ok = False
        self.last_error = None
        self.reconnect()

    def reconnect(self):
        self.ok = False
        self.last_error = None

        try:
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

            version = radio.spi_read(self.REG_VERSION)
            if version != self.EXPECTED_VERSION:
                raise OSError("rfm bad version 0x{:02X}".format(version))

            self.radio = radio
            self.ok = True
            return True

        except Exception as e:
            self.radio = None
            self.ok = False
            self.last_error = str(e)
            return False

    def receive_line(self, timeout_ms=500):
        try:
            if not self.ok:
                if not self.reconnect():
                    return None

            packet = self.radio.receive(with_ack=True, timeout=timeout_ms / 1000)
            if packet is None:
                self.ok = True
                self.last_error = None
                return None

            self.ok = True
            self.last_error = None
            return str(packet, "utf-8")

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return None

    def debug_status(self):
        try:
            if self.radio is None:
                raise OSError(self.last_error or "not initialized")

            version = self.radio.spi_read(self.REG_VERSION)
            return {
                "ok": True,
                "version": version,
                "opmode": self.radio.spi_read(self.REG_OPMODE),
                "irq1": self.radio.spi_read(self.REG_IRQFLAGS1),
                "irq2": self.radio.spi_read(self.REG_IRQFLAGS2),
                "version_ok": version == self.EXPECTED_VERSION,
            }

        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }


# =========================
# RFM PACKET DECODING
# =========================
COMPACT_PACKET_TYPES = ("E", "B", "A", "O", "C", "G")


def parse_int(text):
    try:
        return int(text)
    except Exception:
        return None


def scaled_text(text, factor=1, decimals=0, unit=""):
    value = parse_int(text)
    if value is None:
        return "None"
    if decimals <= 0:
        return "{}{}".format(value // factor if factor != 1 else value, unit)
    return ("{:." + str(decimals) + "f}{}").format(value / factor, unit)


def int_text(text):
    value = parse_int(text)
    return "None" if value is None else str(value)


def decode_timestamp(date_text, time_text):
    if time_text == "RTCERR" or date_text == "0":
        return "RTC_ERR"
    if len(date_text) == 8 and len(time_text) == 6:
        return "{}-{}-{} {}:{}:{}".format(
            date_text[0:4],
            date_text[4:6],
            date_text[6:8],
            time_text[0:2],
            time_text[2:4],
            time_text[4:6],
        )
    return "RTC_ERR"


def parse_compact_packet(packet):
    parts = packet.split(",")
    if len(parts) < 2 or parts[0] not in COMPACT_PACKET_TYPES:
        return None

    expected_lengths = {
        "E": 12,
        "B": 6,
        "A": 9,
        "O": 6,
        "C": 8,
        "G": 12,
    }
    packet_type = parts[0]
    if len(parts) != expected_lengths[packet_type]:
        return None

    return {
        "protocol": "compact",
        "id": parts[1],
        "type": packet_type,
        "parts": parts,
    }


def compact_tmp_text(env):
    if env[4] != "1":
        return "TMP36[ERR:rfm]"
    return "TMP36[T={} V={} Raw={}]".format(
        scaled_text(env[6], 10, 1, "C"),
        scaled_text(env[7], 1000, 3, "V"),
        int_text(env[8]),
    )


def compact_bme_text(env, bme):
    if env[5] != "1" or bme[2] != "1":
        return "BME[ERR]"
    return "BME[T={} P={} H={} G={}ohm A={} GV={}]".format(
        scaled_text(env[9], 10, 1, "C"),
        scaled_text(env[10], 10, 1, "hPa"),
        scaled_text(env[11], 10, 1, "%"),
        int_text(bme[3]),
        scaled_text(bme[4], 10, 1, "m"),
        int_text(bme[5]),
    )


def compact_mpu_text(accel, orientation):
    if accel[2] != "1" or orientation[2] != "1":
        return "MPU[ERR]"
    return "MPU[Ax={} Ay={} Az={} Gx={} Gy={} Gz={} Tmp={} Pit={} Rol={}]".format(
        scaled_text(accel[3], 1000, 2, "g"),
        scaled_text(accel[4], 1000, 2, "g"),
        scaled_text(accel[5], 1000, 2, "g"),
        scaled_text(accel[6], 100, 2, "dps"),
        scaled_text(accel[7], 100, 2, "dps"),
        scaled_text(accel[8], 100, 2, "dps"),
        scaled_text(orientation[3], 10, 1, "C"),
        scaled_text(orientation[4], 10, 1, "deg"),
        scaled_text(orientation[5], 10, 1, "deg"),
    )


def compact_mag_text(mag):
    if mag[2] != "1":
        return "MAG[ERR:rfm]"
    return "MAG[X={} Y={} Z={} H={} CHIP={}]".format(
        int_text(mag[3]),
        int_text(mag[4]),
        int_text(mag[5]),
        scaled_text(mag[6], 10, 1, "deg"),
        mag[7],
    )


def compact_gps_text(gps):
    if gps[2] != "1":
        return "GPS[ERR:rfm]"
    return "GPS[FIX={} SAT={} LAT={} LON={} ALT={} HDOP={} SPD={} CRS={} VS={}]".format(
        int_text(gps[3]),
        int_text(gps[4]),
        scaled_text(gps[5], 1000000, 6),
        scaled_text(gps[6], 1000000, 6),
        scaled_text(gps[7], 10, 1, "m"),
        scaled_text(gps[8], 100, 2),
        scaled_text(gps[9], 10, 1, "kmh"),
        scaled_text(gps[10], 10, 1, "deg"),
        scaled_text(gps[11], 100, 2, "ms"),
    )


def compact_bme_partial_text(env, bme):
    if env is None and bme is None:
        return "BME[ERR:missing_EB]"

    if env is not None and env[5] != "1":
        return "BME[ERR:rfm]"

    if bme is not None and bme[2] != "1":
        return "BME[ERR:rfm]"

    return "BME[T={} P={} H={} G={}ohm A={} GV={}]".format(
        scaled_text(env[9], 10, 1, "C") if env is not None else "None",
        scaled_text(env[10], 10, 1, "hPa") if env is not None else "None",
        scaled_text(env[11], 10, 1, "%") if env is not None else "None",
        int_text(bme[3]) if bme is not None else "None",
        scaled_text(bme[4], 10, 1, "m") if bme is not None else "None",
        int_text(bme[5]) if bme is not None else "None",
    )


def compact_mpu_partial_text(accel, orientation):
    if accel is None and orientation is None:
        return "MPU[ERR:missing_AO]"

    if accel is not None and accel[2] != "1":
        return "MPU[ERR:rfm]"

    if orientation is not None and orientation[2] != "1":
        return "MPU[ERR:rfm]"

    return "MPU[Ax={} Ay={} Az={} Gx={} Gy={} Gz={} Tmp={} Pit={} Rol={}]".format(
        scaled_text(accel[3], 1000, 2, "g") if accel is not None else "None",
        scaled_text(accel[4], 1000, 2, "g") if accel is not None else "None",
        scaled_text(accel[5], 1000, 2, "g") if accel is not None else "None",
        scaled_text(accel[6], 100, 2, "dps") if accel is not None else "None",
        scaled_text(accel[7], 100, 2, "dps") if accel is not None else "None",
        scaled_text(accel[8], 100, 2, "dps") if accel is not None else "None",
        scaled_text(orientation[3], 10, 1, "C") if orientation is not None else "None",
        scaled_text(orientation[4], 10, 1, "deg") if orientation is not None else "None",
        scaled_text(orientation[5], 10, 1, "deg") if orientation is not None else "None",
    )


def reconstruct_compact_line(sample_id, parts):
    env = parts["E"]
    timestamp = decode_timestamp(env[2], env[3])
    return "SID={} T={} {} {} {} {} {}".format(
        sample_id,
        timestamp,
        compact_tmp_text(env),
        compact_bme_text(env, parts["B"]),
        compact_mpu_text(parts["A"], parts["O"]),
        compact_mag_text(parts["C"]),
        compact_gps_text(parts["G"]),
    )


def missing_compact_types(parts):
    missing = []
    for packet_type in COMPACT_PACKET_TYPES:
        if packet_type not in parts:
            missing.append(packet_type)
    return missing


def reconstruct_partial_compact_line(sample_id, parts, missing):
    env = parts.get("E")
    timestamp = decode_timestamp(env[2], env[3]) if env is not None else "RTC_ERR"
    missing_text = ",".join(missing) if missing else "none"

    return "SID={} T={} PARTIAL[MISSING={}] {} {} {} {} {}".format(
        sample_id,
        timestamp,
        missing_text,
        compact_tmp_text(env) if env is not None else "TMP36[ERR:missing_E]",
        compact_bme_partial_text(env, parts.get("B")),
        compact_mpu_partial_text(parts.get("A"), parts.get("O")),
        compact_mag_text(parts["C"]) if "C" in parts else "MAG[ERR:missing_C]",
        compact_gps_text(parts["G"]) if "G" in parts else "GPS[ERR:missing_G]",
    )


def apply_compact_packet(compact_cache, parsed):
    sample_id = parsed["id"]
    entry = compact_cache.get(sample_id)
    if entry is None:
        entry = {
            "created_ms": utime.ticks_ms(),
            "parts": {},
        }
        compact_cache[sample_id] = entry

    entry["parts"][parsed["type"]] = parsed["parts"]

    for packet_type in COMPACT_PACKET_TYPES:
        if packet_type not in entry["parts"]:
            return None

    return reconstruct_compact_line(sample_id, entry["parts"])


def expire_compact_cache(compact_cache, max_age_ms=3000):
    now_ms = utime.ticks_ms()
    expired = []
    for sample_id, entry in list(compact_cache.items()):
        if utime.ticks_diff(now_ms, entry["created_ms"]) >= max_age_ms:
            missing = missing_compact_types(entry["parts"])
            expired.append((
                sample_id,
                ",".join(missing),
                reconstruct_partial_compact_line(sample_id, entry["parts"], missing),
            ))
            compact_cache.pop(sample_id, None)
    return expired


def prune_completed_ids(completed_ids, max_items=32):
    if len(completed_ids) <= max_items:
        return
    for key in list(completed_ids.keys())[:-max_items]:
        completed_ids.pop(key, None)


# Legacy multipart line parser kept for transition/testing.
def parse_line_packet(packet):
    parts = packet.split(",", 4)
    if len(parts) != 5 or parts[0] != "L":
        return None

    try:
        sample_id = parts[1]
        part = int(parts[2])
        total = int(parts[3])
        payload = parts[4]
    except Exception:
        return None

    if part < 1 or total < 1 or part > total:
        return None

    return {
        "protocol": "legacy_line",
        "id": sample_id,
        "part": part,
        "total": total,
        "payload": payload,
    }


def apply_line_packet(line_cache, parsed):
    sample_id = parsed["id"]
    entry = line_cache.get(sample_id)

    if entry is None or entry["total"] != parsed["total"]:
        entry = {
            "total": parsed["total"],
            "parts": {},
        }
        line_cache[sample_id] = entry

    entry["parts"][parsed["part"]] = parsed["payload"]

    if len(entry["parts"]) != entry["total"]:
        return None

    chunks = []
    for index in range(1, entry["total"] + 1):
        if index not in entry["parts"]:
            return None
        chunks.append(entry["parts"][index])

    return "".join(chunks)


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

    if not _writing_status_log:
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

        if log_events and DEBUG_HTTP:
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

        if log_events and DEBUG_HTTP:
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


def send_partial_compact_line(sample_id, missing, line):
    log_status("WARN", "RFM69", "DROP_PARTIAL id={} missing={}".format(sample_id, missing))

    completed_line = completed_ids.get(sample_id)
    if completed_line == line:
        return False

    if completed_line is not None and "PARTIAL[" not in completed_line:
        return False

    print(line)
    send_http_get(line)
    completed_ids[sample_id] = line
    prune_completed_ids(completed_ids)
    return True


def drop_old_compact_entries(compact_cache, max_items=8):
    if len(compact_cache) <= max_items:
        return

    for sample_id in list(compact_cache.keys())[:-max_items]:
        entry = compact_cache.pop(sample_id, None)
        if entry is None:
            continue
        missing = missing_compact_types(entry["parts"])
        send_partial_compact_line(
            sample_id,
            ",".join(missing),
            reconstruct_partial_compact_line(sample_id, entry["parts"], missing),
        )


# =========================
# HOTPLUG MODULE HELPERS
# =========================
def init_sd():
    global sdmod

    try:
        if not SD_WRITE_ENABLED:
            sdmod = None
            log_status("INFO", "SD", "WRITE_DISABLED")
            return False

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
        if not SD_WRITE_ENABLED or not SD_RECONNECT_ENABLED:
            return False

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
        if not SD_WRITE_ENABLED:
            return False

        if sdmod is None or not sdmod.ok:
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
        log_status("INFO", "RFM69", "CONNECTING CS=GP{} RST=GP{} FREQ={}MHz".format(
            RFM_CS_PIN,
            RFM_RST_PIN,
            RFM_FREQ_MHZ
        ))
        rfm = GroundRFM69(
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
            encryption_key=RFM_ENCRYPTION_KEY
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
# INIT
# =========================
message_led = Pin(LED_PIN, Pin.OUT)
message_led.off()

init_sd()
connect_wifi()
init_rfm()

log_status("INFO", "RFM69", "CONFIG SCK=GP{} MOSI=GP{} MISO=GP{} CS=GP{} RST=GP{} FREQ={}MHz BITRATE={} FDEV={} RXBW=0x{:02X} AFCBW=0x{:02X} PREAMBLE={} TX_POWER={}dBm NODE=0x{:02X} DEST=0x{:02X} AES=ON".format(
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
    RFM_DESTINATION_ID
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
compact_cache = {}
line_cache = {}
completed_ids = {}
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

        if not SD_WRITE_ENABLED:
            sd_was_ok = False
        elif current_sd_ok:
            if not sd_was_ok:
                log_status("INFO", "SD", "RECONNECTED DATA={}".format(SD_DATA_FILENAME))
            sd_was_ok = True
        else:
            if sd_was_ok:
                last_error = sdmod.last_error if sdmod is not None else "not initialized"
                log_status("WARN", "SD", "DISCONNECTED {}".format(last_error))
            sd_was_ok = False

            if SD_RECONNECT_ENABLED and utime.ticks_diff(utime.ticks_ms(), last_sd_reconnect_ms) >= SD_RECONNECT_INTERVAL_MS:
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

            parsed = parse_compact_packet(packet)
            if parsed is None:
                parsed = parse_line_packet(packet)

            if parsed is None:
                log_status("WARN", "RFM69", "BAD_PACKET {}".format(packet))
            elif parsed["protocol"] == "compact":
                line = apply_compact_packet(compact_cache, parsed)
                if line is not None and completed_ids.get(parsed["id"]) != line:
                    print(line)

                    if write_sd_data(line):
                        sd_was_ok = True
                    else:
                        sd_was_ok = False

                    send_http_get(line)
                    completed_ids[parsed["id"]] = line
                    prune_completed_ids(completed_ids)
                    compact_cache.pop(parsed["id"], None)

                for expired_id, missing, partial_line in expire_compact_cache(compact_cache):
                    send_partial_compact_line(expired_id, missing, partial_line)

                drop_old_compact_entries(compact_cache)
            else:
                line = apply_line_packet(line_cache, parsed)
                if line is not None and completed_ids.get(parsed["id"]) != line:
                    print(line)

                    if write_sd_data(line):
                        sd_was_ok = True
                    else:
                        sd_was_ok = False

                    send_http_get(line)
                    completed_ids[parsed["id"]] = line
                    prune_completed_ids(completed_ids)
                    line_cache.pop(parsed["id"], None)

                if len(line_cache) > 8:
                    for key in list(line_cache.keys())[:-8]:
                        line_cache.pop(key, None)
                        completed_ids.pop(key, None)

        else:
            now_ms = utime.ticks_ms()

            for expired_id, missing, partial_line in expire_compact_cache(compact_cache):
                send_partial_compact_line(expired_id, missing, partial_line)

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



