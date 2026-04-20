import math
import socket
import time

try:
    import network
except ImportError:
    network = None


# Run this file on the Pico / MicroPython from Thonny.
# It sends simulated flight telemetry and logs to the dashboard.

WIFI_SSID = "Proximus-Home-01E0"
WIFI_PASSWORD = "wyyf9j26shyac"
SERVER_URL = "http://192.168.1.14/GitHub/CANSAT/Site/api/receive.php"

SAMPLES = 42
DELAY_MS = 150
HTTP_TIMEOUT_S = 4

BME_SEA_LEVEL_PRESSURE = 1013.25
BASE_LAT = 50.85045
BASE_LON = 4.34878


def fmt_value(value, decimals=None, unit=""):
    if value is None:
        return "None"
    if decimals is None:
        return "{}{}".format(value, unit)
    fmt = "{:." + str(decimals) + "f}{}"
    return fmt.format(value, unit)


def safe_int(text):
    if text == "?" or text == "":
        return None
    try:
        return int(text)
    except Exception:
        return None


def scale_int(value, factor=1):
    if value is None:
        return "0"
    try:
        return str(int(round(value * factor)))
    except Exception:
        return "0"


def unscale(text, factor=1):
    value = safe_int(text)
    if value is None:
        return None
    return value / factor


def altitude_from_pressure(pressure_hpa, sea_level_pressure):
    if pressure_hpa is None or pressure_hpa <= 0:
        return None
    return 44330.77 * (1.0 - ((pressure_hpa / sea_level_pressure) ** 0.1902632))


def pressure_from_altitude(altitude_m, sea_level_pressure):
    return sea_level_pressure * ((1.0 - altitude_m / 44330.77) ** (1.0 / 0.1902632))


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


def connect_wifi():
    if network is None:
        print("WIFI ERROR: network module not available")
        return False

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("WIFI already connected:", wlan.ifconfig())
        return True

    print("WIFI connecting to", WIFI_SSID)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    start = time.ticks_ms()

    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 12000:
            print("WIFI timeout")
            return False
        time.sleep_ms(200)

    print("WIFI connected:", wlan.ifconfig())
    return True


def post_payload(payload_type, source, line):
    host, port, path = parse_http_url(SERVER_URL)
    query = "type={}&source={}&line={}".format(
        urlencode(payload_type),
        urlencode(source),
        urlencode(line)
    )
    full_path = "{}{}{}".format(path, "&" if "?" in path else "?", query)
    sock = None

    try:
        addr = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket()
        sock.settimeout(HTTP_TIMEOUT_S)
        sock.connect(addr)
        request = (
            "GET {} HTTP/1.0\r\n"
            "Host: {}\r\n"
            "Connection: close\r\n\r\n"
        ).format(full_path, host)
        sock.send(request.encode("utf-8"))
        response = sock.recv(128)
        sock.close()
        ok = b"OK" in response
        if not ok:
            print("HTTP WARN:", response)
        return ok
    except Exception as e:
        print("HTTP ERROR:", e)
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
        return False


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


def mission_profile(index, total):
    progress = index / max(total - 1, 1)
    if progress < 0.18:
        altitude = 2 + progress / 0.18 * 140
    elif progress < 0.58:
        altitude = 140 + (progress - 0.18) / 0.40 * 875
    elif progress < 0.74:
        altitude = 1015 - (progress - 0.58) / 0.16 * 220
    else:
        altitude = 795 - (progress - 0.74) / 0.26 * 760
    return max(8.0, altitude)


def clock_text(sample_id):
    total_seconds = 12 * 3600 + sample_id * 2
    hour = (total_seconds // 3600) % 24
    minute = (total_seconds // 60) % 60
    second = total_seconds % 60
    return "{:02d}{:02d}{:02d}".format(hour, minute, second)


def log_time(sample_id):
    raw = clock_text(sample_id)
    return "{}:{}:{}".format(raw[0:2], raw[2:4], raw[4:6])


def build_packets(sample_id, altitude, problem=None):
    wobble = math.sin(sample_id / 3.0)
    temp_drop = altitude / 1000.0 * 6.0
    bme_temp = 22.2 - temp_drop + math.sin(sample_id / 5.0) * 0.4
    tmp36_temp = bme_temp + 0.4
    bme_pressure = pressure_from_altitude(altitude, BME_SEA_LEVEL_PRESSURE)
    humidity = max(34.0, 61.0 - altitude / 35.0 + math.sin(sample_id / 4.0) * 1.6)
    gas = 12800 + int(altitude * 3.4) + int(math.sin(sample_id / 2.5) * 280)

    ax = 0.015 + wobble * 0.055
    ay = -0.02 + math.cos(sample_id / 4.0) * 0.035
    az = 1.08 + math.sin(sample_id / 2.0) * 0.025
    gx = 0.7 + wobble * 3.2
    gy = -0.4 + math.cos(sample_id / 5.0) * 2.1
    gz = 0.2 + math.sin(sample_id / 6.0) * 2.7

    mx = 110 + int(math.cos(sample_id / 6.0) * 42)
    my = 45 + int(math.sin(sample_id / 6.0) * 38)
    mz = -18 + int(math.sin(sample_id / 9.0) * 11)

    gps_fix = 1
    satellites = 7 + (sample_id % 5)
    lat = BASE_LAT + sample_id * 0.000018
    lon = BASE_LON + sample_id * 0.000027
    gps_alt = altitude + 4.0 + math.sin(sample_id / 4.0) * 3.0

    if problem == "gps_drop":
        gps_fix = 0
        satellites = 0
        lat = 0
        lon = 0
        gps_alt = 0
    elif problem == "sensor_spike":
        bme_temp += 8.0
        tmp36_temp += 10.0
        az += 0.55
    elif problem == "radio_wobble":
        gx += 12.0
        gy -= 8.0

    return [
        "E,{},{},{},{},{},{},{}".format(
            sample_id,
            clock_text(sample_id),
            scale_int(tmp36_temp, 10),
            scale_int(bme_temp, 10),
            scale_int(bme_pressure, 10),
            scale_int(humidity, 10),
            scale_int(gas),
        ),
        "M,{},A,{},{},{},{},{},{}".format(
            sample_id,
            scale_int(ax, 1000),
            scale_int(ay, 1000),
            scale_int(az, 1000),
            scale_int(gx, 100),
            scale_int(gy, 100),
            scale_int(gz, 100),
        ),
        "M,{},C,{},{},{}".format(sample_id, mx, my, mz),
        "G,{},{},{},{},{},{},{},{}".format(
            sample_id,
            gps_fix,
            satellites,
            scale_int(lat, 1000000),
            scale_int(lon, 1000000),
            scale_int(gps_alt, 10),
            "2026-04-19" if gps_fix else "?",
            log_time(sample_id) if gps_fix else "?",
        ),
    ]


def send_log(sample_id, level, source, message):
    line = "{} [{}] {} {}".format(log_time(sample_id), level, source, message)
    print("LOG", line)
    post_payload("log", source, line)


def run_test():
    if not connect_wifi():
        return

    sample_cache = {}
    last_sent_by_id = {}

    send_log(0, "INFO", "WIFI", "CONNECTED SSID=GroundTest")
    send_log(0, "INFO", "RFM69", "CONFIG SCK=GP3 MOSI=GP2 MISO=GP4 CS=GP14 FREQ=434.0MHz BITRATE=4800")
    send_log(0, "DEBUG", "RFM69", "VERSION=0x24 OPMODE=0x90 IRQ1=0xC0 IRQ2=0x00 VERSION_STATUS=OK")
    send_log(0, "INFO", "SD", "CONNECTED DATA=ground_data.txt LOG=ground_logs.txt")

    for sample_id in range(SAMPLES):
        problem = None
        if sample_id == 8:
            problem = "gps_drop"
            send_log(sample_id, "WARN", "GPS", "FIX_LOST satellites=0")
        elif sample_id == 9:
            send_log(sample_id, "INFO", "GPS", "FIX_ACQUIRED satellites=7")
        elif sample_id == 17:
            problem = "radio_wobble"
            send_log(sample_id, "WARN", "RFM69", "NO_MESSAGE gap=360ms")
        elif sample_id == 18:
            send_log(sample_id, "DEBUG", "RFM69", "VERSION=0x24 OPMODE=0x90 IRQ1=0xC0 IRQ2=0x00 VERSION_STATUS=OK")
        elif sample_id == 24:
            send_log(sample_id, "WARN", "SD", "WRITE_RETRY DATA=ground_data.txt")
        elif sample_id == 25:
            send_log(sample_id, "INFO", "SD", "WRITE_OK DATA=ground_data.txt")
        elif sample_id == 31:
            problem = "sensor_spike"
            send_log(sample_id, "WARN", "TMP36", "TEMP_SPIKE possible_sun_exposure")

        packets = build_packets(sample_id, mission_profile(sample_id, SAMPLES), problem)

        for packet in packets:
            print("RFM RX", packet)
            parsed = parse_packet(packet)
            if parsed is None:
                send_log(sample_id, "WARN", "RFM69", "BAD_PACKET {}".format(packet))
                continue

            sample = apply_packet(sample_cache, parsed)
            if parsed["type"] in ("G", "C"):
                line = readable_line(sample)
                if last_sent_by_id.get(sample["id"]) != line:
                    print("TELEMETRY", line)
                    post_payload("telemetry", "ground_station_test", line)
                    last_sent_by_id[sample["id"]] = line

        time.sleep_ms(DELAY_MS)

    send_log(SAMPLES, "INFO", "MISSION", "TEST_FLIGHT_COMPLETE samples={} source=ground_station_test".format(SAMPLES))


run_test()
