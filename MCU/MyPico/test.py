from machine import Pin, I2C, UART, SoftSPI, ADC
import utime


# =========================================================
# CANSAT focused hardware tester
# =========================================================
# One file only. No project driver imports.
#
# This version uses the pins discovered from your solder tests.
# It avoids broad "look everywhere" scans except for a small GPS fallback,
# because GPS is still the unresolved module.


PINS = {
    # Confirmed working I2C bus
    "i2c_sda": 0,
    "i2c_scl": 1,
    "i2c_freq": 100000,

    # Confirmed working shared SPI bus
    "spi_sck": 2,
    "spi_mosi": 3,
    "spi_miso": 4,
    "sd_cs": 5,
    "rfm_cs": 6,

    # Schematic extras
    "reset": 7,
    "int": 8,
    "led_1": 9,
    "led_2": 10,

    # GPS still expected here, but not found yet
    "gps_rx": 13,

    # Confirmed RTC discovery from logs
    "rtc_clk": 27,
    "rtc_io": 28,
    "rtc_rst": 29,

    # Confirmed TMP36
    "tmp36": 26,
}


CHECK_PINS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 10, 13,
    26, 27, 28, 29,
)

EXPOSED_PINS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 10, 11, 12, 13, 14, 15,
    18, 19, 20,
    26, 27, 28, 29,
)

GPS_RX_CANDIDATES = EXPOSED_PINS
GPS_BAUDS = (4800, 9600, 19200, 38400, 57600, 115200)
MAG_ADDRESSES = (0x2C, 0x0D, 0x0C, 0x1E)

KNOWN_I2C = {
    0x2C: "QMC5883P magnetometer",
    0x0C: "QMC5883L magnetometer alt",
    0x0D: "QMC5883L magnetometer",
    0x1E: "HMC5883L magnetometer",
    0x68: "MPU6500/MPU6050 IMU or DS3231 RTC",
    0x69: "MPU6500/MPU6050 IMU alternate",
    0x76: "environmental sensor",
    0x77: "BME688/BME680 environmental sensor",
}


def line(title):
    print("")
    print("=" * 64)
    print(title)
    print("=" * 64)


def pin_name(pin):
    return "GP{}".format(pin)


def pin_list(pins):
    if not pins:
        return "none"
    return ", ".join(pin_name(p) for p in pins)


def hex_list(values):
    return "[" + ", ".join(hex(v) for v in values) + "]"


def sleep_ms(ms):
    utime.sleep_ms(ms)


def ticks_ms():
    return utime.ticks_ms()


def ticks_diff(a, b):
    return utime.ticks_diff(a, b)


def print_pin_summary():
    line("CONFIRMED PIN MAP")
    print("I2C:    SDA={} SCL={} FREQ={}".format(
        pin_name(PINS["i2c_sda"]), pin_name(PINS["i2c_scl"]), PINS["i2c_freq"]
    ))
    print("SPI:    SCK={} MOSI={} MISO={}".format(
        pin_name(PINS["spi_sck"]), pin_name(PINS["spi_mosi"]), pin_name(PINS["spi_miso"])
    ))
    print("SD:     CS={}".format(pin_name(PINS["sd_cs"])))
    print("RFM69:  CS={}".format(pin_name(PINS["rfm_cs"])))
    print("RTC:    CLK={} IO={} RST={}".format(
        pin_name(PINS["rtc_clk"]), pin_name(PINS["rtc_io"]), pin_name(PINS["rtc_rst"])
    ))
    print("GPS:    expected Pico RX={}".format(pin_name(PINS["gps_rx"])))
    print("TMP36:  ADC={}".format(pin_name(PINS["tmp36"])))
    print("LEDs:   LED_1={} LED_2={}".format(pin_name(PINS["led_1"]), pin_name(PINS["led_2"])))
    print("Extra:  RST={} INT={}".format(pin_name(PINS["reset"]), pin_name(PINS["int"])))


# =========================================================
# GPIO health
# =========================================================
def read_pin_with_pull(pin, pull):
    p = Pin(pin, Pin.IN, pull)
    sleep_ms(2)
    return p.value()


def passive_gpio_health():
    line("FOCUSED GPIO LEVELS")
    print("Only checking pins that matter now.")
    print("I2C/SPI pins may read high because connected modules pull them high.")

    stuck_high = []
    stuck_low = []
    movable = []

    for pin in CHECK_PINS:
        try:
            down = read_pin_with_pull(pin, Pin.PULL_DOWN)
            up = read_pin_with_pull(pin, Pin.PULL_UP)

            if down == 1 and up == 1:
                note = "external HIGH"
                stuck_high.append(pin)
            elif down == 0 and up == 0:
                note = "external LOW"
                stuck_low.append(pin)
            else:
                note = "moves with pull"
                movable.append(pin)

            print("{:<4} pulldown={} pullup={} {}".format(pin_name(pin), down, up, note))
        except Exception as e:
            print("{:<4} read error {}".format(pin_name(pin), e))

    print("")
    print("External HIGH: {}".format(pin_list(stuck_high)))
    print("External LOW:  {}".format(pin_list(stuck_low)))
    print("Movable:       {}".format(pin_list(movable)))


# =========================================================
# I2C modules
# =========================================================
def scan_i2c():
    line("I2C MODULES")
    try:
        i2c = I2C(
            0,
            sda=Pin(PINS["i2c_sda"]),
            scl=Pin(PINS["i2c_scl"]),
            freq=PINS["i2c_freq"],
        )
        sleep_ms(20)
        addresses = i2c.scan()
    except Exception as e:
        print("I2C init/scan failed:", e)
        return []

    if not addresses:
        print("No I2C devices found on confirmed bus.")
        return []

    print("I2C0 SDA={} SCL={} {}Hz -> {}".format(
        pin_name(PINS["i2c_sda"]), pin_name(PINS["i2c_scl"]),
        PINS["i2c_freq"], hex_list(addresses)
    ))
    for addr in addresses:
        print("  {}: {}".format(hex(addr), KNOWN_I2C.get(addr, "unknown I2C device")))

    if 0x68 in addresses:
        print("  MPU: detected")
    if 0x77 in addresses:
        print("  BME688/BME680: detected")
    if 0x2C not in addresses and 0x0C not in addresses and 0x0D not in addresses and 0x1E not in addresses:
        print("  MAG: not detected")
    if 0x2C in addresses:
        print("  MAG QMC5883P: detected")

    return addresses


def probe_i2c_address(i2c, address):
    try:
        i2c.writeto(address, b"")
        return True, "empty-write ACK"
    except Exception as e1:
        try:
            i2c.readfrom(address, 1)
            return True, "read ACK"
        except Exception as e2:
            return False, "{} / {}".format(e1, e2)


def scan_all_i2c_addresses():
    line("FULL I2C ADDRESS PROBE ON GP0/GP1")
    print("Probing every normal 7-bit I2C address from 0x03 to 0x77.")
    print("Magnetometer targets: QMC5883P=0x2C, QMC5883L/DA5883=0x0D, HMC5883L/L883=0x1E.")

    try:
        i2c = I2C(
            0,
            sda=Pin(PINS["i2c_sda"]),
            scl=Pin(PINS["i2c_scl"]),
            freq=PINS["i2c_freq"],
        )
        sleep_ms(20)
    except Exception as e:
        print("I2C init failed:", e)
        return []

    found = []
    for addr in range(0x03, 0x78):
        ok, method = probe_i2c_address(i2c, addr)
        if ok:
            found.append(addr)
            print("  ACK {}: {} {}".format(
                hex(addr), KNOWN_I2C.get(addr, "unknown device"), method
            ))

    if not found:
        print("No I2C addresses ACKed on GP0/GP1.")
    else:
        print("All ACKed addresses:", hex_list(found))

    for target, name in (
        (0x2C, "QMC5883P"),
        (0x0D, "QMC5883L / DA5883"),
        (0x1E, "HMC5883L / L883"),
        (0x0C, "QMC5883L alternate"),
    ):
        if target in found:
            print("MAG TARGET FOUND: {} at {}".format(name, hex(target)))
        else:
            print("MAG TARGET NOT FOUND: {} at {}".format(name, hex(target)))

    return found


def i2c_pair_candidates():
    pairs = [(0, PINS["i2c_sda"], PINS["i2c_scl"])]

    # RP2040 valid I2C pin patterns on the exposed pins.
    for i2c_id in (0, 1):
        for sda in EXPOSED_PINS:
            scl = sda + 1
            if scl not in EXPOSED_PINS:
                continue
            if i2c_id == 0 and sda % 4 == 0 and scl % 4 == 1:
                pairs.append((i2c_id, sda, scl))
            if i2c_id == 1 and sda % 4 == 2 and scl % 4 == 3:
                pairs.append((i2c_id, sda, scl))

    result = []
    for pair in pairs:
        if pair not in result:
            result.append(pair)
    return result


def safe_read_i2c_reg(i2c, address, register, length=1):
    try:
        return i2c.readfrom_mem(address, register, length)
    except Exception:
        return None


def scan_magnetometer_deep():
    line("MAGNETOMETER HW-246 / GY-271 SEARCH")
    print("Looking for QMC5883P at 0x2C, QMC5883L/DA5883 at 0x0D, or HMC5883L/L883 at 0x1E.")
    print("Also checks QMC5883L alternate address 0x0C.")

    found = []
    floating = []

    try:
        main_i2c = I2C(
            0,
            sda=Pin(PINS["i2c_sda"]),
            scl=Pin(PINS["i2c_scl"]),
            freq=PINS["i2c_freq"],
        )
        sleep_ms(20)
        print("Direct target probes on confirmed bus GP0/GP1:")
        for addr, name in (
            (0x2C, "QMC5883P"),
            (0x0D, "QMC5883L / DA5883"),
            (0x1E, "HMC5883L / L883"),
            (0x0C, "QMC5883L alternate"),
        ):
            ok, method = probe_i2c_address(main_i2c, addr)
            print("  {} {} -> {}".format(hex(addr), name, "ACK " + method if ok else "no ACK"))
            if ok:
                if addr == 0x2C:
                    ident = safe_read_i2c_reg(main_i2c, addr, 0x00, 1)
                    status = safe_read_i2c_reg(main_i2c, addr, 0x09, 1)
                    print("    QMC5883P ID/status: ID_0x00={} STATUS_0x09={}".format(
                        hex(ident[0]) if ident else "read-failed",
                        hex(status[0]) if status else "read-failed"
                    ))
                elif addr in (0x0D, 0x0C):
                    ident = safe_read_i2c_reg(main_i2c, addr, 0x0D, 1)
                    status = safe_read_i2c_reg(main_i2c, addr, 0x06, 1)
                    print("    QMC ID/status: ID_0x0D={} STATUS_0x06={}".format(
                        hex(ident[0]) if ident else "read-failed",
                        hex(status[0]) if status else "read-failed"
                    ))
                else:
                    ident = safe_read_i2c_reg(main_i2c, addr, 0x0A, 3)
                    print("    HMC ID registers 0x0A..0x0C={}".format(
                        list(ident) if ident else "read-failed"
                    ))
                found.append((0, PINS["i2c_sda"], PINS["i2c_scl"], addr))
    except Exception as e:
        print("Direct magnetometer probe failed:", e)

    for i2c_id, sda, scl in i2c_pair_candidates():
        if i2c_id == 0 and sda == PINS["i2c_sda"] and scl == PINS["i2c_scl"]:
            continue
        try:
            i2c = I2C(i2c_id, sda=Pin(sda), scl=Pin(scl), freq=100000)
            sleep_ms(20)
            addresses = i2c.scan()
        except Exception:
            continue

        if len(addresses) > 20:
            floating.append((i2c_id, sda, scl, len(addresses)))
            continue

        mag_addresses = [addr for addr in addresses if addr in MAG_ADDRESSES]
        if not mag_addresses:
            continue

        for addr in mag_addresses:
            chip = KNOWN_I2C.get(addr, "GY-271 magnetometer")
            print("MAG candidate: I2C{} SDA={} SCL={} addr={} {}".format(
                i2c_id, pin_name(sda), pin_name(scl), hex(addr), chip
            ))

            if addr == 0x2C:
                ident = safe_read_i2c_reg(i2c, addr, 0x00, 1)
                status = safe_read_i2c_reg(i2c, addr, 0x09, 1)
                print("  QMC5883P probe: ID_REG_0x00={} STATUS_0x09={}".format(
                    hex(ident[0]) if ident else "read-failed",
                    hex(status[0]) if status else "read-failed"
                ))
            elif addr in (0x0D, 0x0C):
                ident = safe_read_i2c_reg(i2c, addr, 0x0D, 1)
                status = safe_read_i2c_reg(i2c, addr, 0x06, 1)
                print("  QMC probe: ID_REG_0x0D={} STATUS_0x06={}".format(
                    hex(ident[0]) if ident else "read-failed",
                    hex(status[0]) if status else "read-failed"
                ))
            elif addr == 0x1E:
                ident = safe_read_i2c_reg(i2c, addr, 0x0A, 3)
                print("  HMC probe: ID_0x0A..0x0C={}".format(
                    list(ident) if ident else "read-failed"
                ))

            found.append((i2c_id, sda, scl, addr))

    if not found:
        print("MAG status: not found on valid exposed I2C pin pairs.")
        print("Expected if soldered to main bus: SDA={} SCL={} and address 0x2C, 0x0D, 0x0C, or 0x1E.".format(
            pin_name(PINS["i2c_sda"]), pin_name(PINS["i2c_scl"])
        ))
        print("Check magnetometer VCC, GND, SDA, SCL, and whether the module is actually installed.")

    if floating:
        print("Ignored floating/noisy I2C pairs:")
        for i2c_id, sda, scl, count in floating[:8]:
            print("  I2C{} SDA={} SCL={} returned {} addresses".format(
                i2c_id, pin_name(sda), pin_name(scl), count
            ))

    return found


# =========================================================
# DS1302 RTC
# =========================================================
def ds1302_bcd_ok(value):
    return ((value >> 4) & 0x0F) <= 9 and (value & 0x0F) <= 9


def bcd_to_dec(value):
    return ((value >> 4) * 10) + (value & 0x0F)


def ds1302_read_byte(clk, dat, rst, command):
    clk.value(0)
    rst.value(1)
    utime.sleep_us(4)

    dat.init(Pin.OUT)
    value = command | 0x01
    for _ in range(8):
        dat.value(value & 1)
        utime.sleep_us(1)
        clk.value(1)
        utime.sleep_us(1)
        clk.value(0)
        utime.sleep_us(1)
        value >>= 1

    dat.init(Pin.IN)
    result = 0
    for bit_index in range(8):
        result |= dat.value() << bit_index
        utime.sleep_us(1)
        clk.value(1)
        utime.sleep_us(1)
        clk.value(0)
        utime.sleep_us(1)

    rst.value(0)
    clk.value(0)
    utime.sleep_us(4)
    return result


def read_rtc():
    line("DS1302 RTC")
    try:
        clk = Pin(PINS["rtc_clk"], Pin.OUT, value=0)
        dat = Pin(PINS["rtc_io"], Pin.OUT, value=0)
        rst = Pin(PINS["rtc_rst"], Pin.OUT, value=0)

        regs = [
            ds1302_read_byte(clk, dat, rst, 0x80),
            ds1302_read_byte(clk, dat, rst, 0x82),
            ds1302_read_byte(clk, dat, rst, 0x84),
            ds1302_read_byte(clk, dat, rst, 0x86),
            ds1302_read_byte(clk, dat, rst, 0x88),
            ds1302_read_byte(clk, dat, rst, 0x8A),
            ds1302_read_byte(clk, dat, rst, 0x8C),
        ]
    except Exception as e:
        print("RTC read failed:", e)
        return False

    print("RTC pins CLK={} IO={} RST={}".format(
        pin_name(PINS["rtc_clk"]), pin_name(PINS["rtc_io"]), pin_name(PINS["rtc_rst"])
    ))
    print("Raw registers:", hex_list(regs))

    if all(v == 0x00 for v in regs):
        print("RTC status: not responding, all registers 0x00")
        return False
    if all(v == 0xFF for v in regs):
        print("RTC status: not responding/floating, all registers 0xFF")
        return False

    sec_bcd = regs[0] & 0x7F
    min_bcd = regs[1] & 0x7F
    hour_bcd = regs[2] & 0x3F
    day_bcd = regs[3] & 0x3F
    month_bcd = regs[4] & 0x1F
    weekday_bcd = regs[5] & 0x07
    year_bcd = regs[6]
    fields = (sec_bcd, min_bcd, hour_bcd, day_bcd, month_bcd, weekday_bcd, year_bcd)

    if not all(ds1302_bcd_ok(v) for v in fields):
        print("RTC status: responding, but values are not valid BCD")
        return False

    second = bcd_to_dec(sec_bcd)
    minute = bcd_to_dec(min_bcd)
    hour = bcd_to_dec(hour_bcd)
    day = bcd_to_dec(day_bcd)
    month = bcd_to_dec(month_bcd)
    weekday = bcd_to_dec(weekday_bcd)
    year = 2000 + bcd_to_dec(year_bcd)

    valid_date = (
        0 <= second <= 59 and
        0 <= minute <= 59 and
        0 <= hour <= 23 and
        1 <= day <= 31 and
        1 <= month <= 12 and
        1 <= weekday <= 7
    )

    if regs[0] & 0x80:
        print("RTC status: responding, but clock halted bit is set")
    elif valid_date:
        print("RTC status: OK")
        print("RTC datetime: {:04d}-{:02d}-{:02d} weekday={} {:02d}:{:02d}:{:02d}".format(
            year, month, day, weekday, hour, minute, second
        ))
    else:
        print("RTC status: responds, but date/time is not initialized correctly")
        print("Decoded: {:04d}-{:02d}-{:02d} weekday={} {:02d}:{:02d}:{:02d}".format(
            year, month, day, weekday, hour, minute, second
        ))

    return True


# =========================================================
# SPI modules
# =========================================================
def make_spi(baud=100000):
    return SoftSPI(
        baudrate=baud,
        polarity=0,
        phase=0,
        sck=Pin(PINS["spi_sck"]),
        mosi=Pin(PINS["spi_mosi"]),
        miso=Pin(PINS["spi_miso"]),
    )


def rfm_read_reg(spi, cs, reg):
    cs.value(0)
    spi.write(bytes([reg & 0x7F]))
    data = spi.read(1, 0x00)
    cs.value(1)
    return data[0]


def check_rfm69():
    line("RFM69 RADIO")
    try:
        spi = make_spi(baud=200000)
        cs = Pin(PINS["rfm_cs"], Pin.OUT, value=1)
        sleep_ms(2)
        version = rfm_read_reg(spi, cs, 0x10)
    except Exception as e:
        print("RFM69 check failed:", e)
        return False

    print("RFM69 pins SCK={} MOSI={} MISO={} CS={}".format(
        pin_name(PINS["spi_sck"]), pin_name(PINS["spi_mosi"]),
        pin_name(PINS["spi_miso"]), pin_name(PINS["rfm_cs"])
    ))
    print("RFM69 VERSION=0x{:02X}".format(version))

    if version == 0x24:
        print("RFM69 status: OK")
        return True

    print("RFM69 status: not OK, expected VERSION=0x24")
    return False


def sd_send_cmd(spi, cs, cmd, arg, crc):
    buf = bytes([
        0x40 | cmd,
        (arg >> 24) & 0xFF,
        (arg >> 16) & 0xFF,
        (arg >> 8) & 0xFF,
        arg & 0xFF,
        crc,
    ])
    cs.value(0)
    spi.write(buf)
    response = 0xFF
    for _ in range(32):
        response = spi.read(1, 0xFF)[0]
        if response & 0x80 == 0:
            break
    cs.value(1)
    spi.write(b"\xff")
    return response


def check_sd_card():
    line("SD CARD")
    try:
        spi = make_spi(baud=100000)
        cs = Pin(PINS["sd_cs"], Pin.OUT, value=1)
        for _ in range(12):
            spi.write(b"\xff")
        response = sd_send_cmd(spi, cs, 0, 0, 0x95)
    except Exception as e:
        print("SD check failed:", e)
        return False

    print("SD pins SCK={} MOSI={} MISO={} CS={}".format(
        pin_name(PINS["spi_sck"]), pin_name(PINS["spi_mosi"]),
        pin_name(PINS["spi_miso"]), pin_name(PINS["sd_cs"])
    ))
    print("SD CMD0 response=0x{:02X}".format(response))

    if response == 0x01:
        print("SD status: OK basic response")
        return True

    print("SD status: not OK, expected CMD0 response 0x01")
    return False


# =========================================================
# GPS
# =========================================================
def uart_read_text(uart, ms):
    start = ticks_ms()
    data = b""
    while ticks_diff(ticks_ms(), start) < ms:
        try:
            if uart.any():
                chunk = uart.read()
                if chunk:
                    data += chunk
        except Exception:
            break
        sleep_ms(20)

    if not data:
        return ""

    try:
        return data.decode("utf-8", "ignore")
    except TypeError:
        try:
            return data.decode("utf-8")
        except Exception:
            return str(data)


def nmea_score(text):
    if not text:
        return 0
    score = 0
    for token in ("$GP", "$GN", "GGA", "RMC", "VTG", "GSA", "GSV"):
        if token in text:
            score += 1
    return score


def try_uart(uart_id, rx_pin, baud, ms):
    try:
        uart = UART(
            uart_id,
            baudrate=baud,
            bits=8,
            parity=None,
            stop=1,
            timeout=100,
            rx=Pin(rx_pin),
        )
        return uart_read_text(uart, ms)
    except Exception:
        return ""


def line_activity(pin, ms=900):
    try:
        p = Pin(pin, Pin.IN)
        sleep_ms(2)
        last = p.value()
        transitions = 0
        high = 0
        samples = 0
        start = ticks_ms()

        while ticks_diff(ticks_ms(), start) < ms:
            value = p.value()
            if value != last:
                transitions += 1
                last = value
            if value:
                high += 1
            samples += 1
            utime.sleep_us(250)

        return transitions, high, samples
    except Exception:
        return 0, 0, 0


def text_preview(text, limit=120):
    if not text:
        return ""
    clean = text.replace("\r", "\\r").replace("\n", "\\n")
    if len(clean) > limit:
        clean = clean[:limit] + "..."
    return clean


def check_gps():
    line("GPS UART")
    print("GY-GPS6MV2 usually outputs NMEA at 9600 baud even without satellite fix.")
    print("Primary expected connection: GPS TX -> Pico RX {}".format(pin_name(PINS["gps_rx"])))

    print("")
    print("GPS line activity check:")
    active_pins = []
    for rx_pin in GPS_RX_CANDIDATES:
        transitions, high, samples = line_activity(rx_pin, ms=450)
        if samples == 0:
            continue
        high_pct = int((high * 100) / samples)
        marker = " expected" if rx_pin == PINS["gps_rx"] else ""
        if transitions > 2:
            active_pins.append(rx_pin)
            print("  {} transitions={} high={}%%{}".format(
                pin_name(rx_pin), transitions, high_pct, marker
            ))

    if not active_pins:
        print("  No obvious serial activity on exposed pins.")
        print("  A powered GPS TX line is usually idle HIGH and pulses when NMEA is sent.")
    elif PINS["gps_rx"] not in active_pins:
        print("  Activity exists, but not on expected RX {}.".format(pin_name(PINS["gps_rx"])))

    found = []
    raw_seen = []
    for uart_id in (0, 1):
        for baud in GPS_BAUDS:
            text = try_uart(uart_id, PINS["gps_rx"], baud, 1200)
            if nmea_score(text):
                found.append((uart_id, PINS["gps_rx"], baud, text))
            elif text:
                raw_seen.append((uart_id, PINS["gps_rx"], baud, text))

    if not found:
        candidate_order = []
        for pin in [PINS["gps_rx"]] + active_pins + list(GPS_RX_CANDIDATES):
            if pin not in candidate_order:
                candidate_order.append(pin)

        print("")
        print("Trying UART decode on RX pins: {}".format(pin_list(candidate_order)))
        for rx_pin in candidate_order:
            if rx_pin == PINS["gps_rx"]:
                continue
            for uart_id in (0, 1):
                for baud in GPS_BAUDS:
                    text = try_uart(uart_id, rx_pin, baud, 450)
                    if nmea_score(text):
                        found.append((uart_id, rx_pin, baud, text))
                    elif text:
                        raw_seen.append((uart_id, rx_pin, baud, text))

    if found:
        for uart_id, rx_pin, baud, text in found:
            preview = text.replace("\r", "").replace("\n", " | ")
            print("GPS status: OK UART{} RX={} BAUD={} -> {}".format(
                uart_id, pin_name(rx_pin), baud, preview[:180]
            ))
        return True

    if raw_seen:
        print("GPS status: raw UART-like data seen, but no valid NMEA tokens.")
        for uart_id, rx_pin, baud, text in raw_seen[:8]:
            print("  RAW UART{} RX={} BAUD={} -> {}".format(
                uart_id, pin_name(rx_pin), baud, text_preview(text)
            ))
        print("This can mean wrong baud, noisy line, wrong module pin, or binary/non-NMEA output.")
        return False

    print("GPS status: no NMEA text found")
    print("Check GPS power, GND, and GPS TX -> Pico RX {}.".format(pin_name(PINS["gps_rx"])))
    print("Also check that you did not connect GPS RX to the Pico; the needed wire is GPS TX.")
    print("No satellite fix is usually not the cause; GPS modules normally output NMEA without a fix.")
    return False


# =========================================================
# ADC / LEDs
# =========================================================
def check_tmp36():
    line("TMP36 ADC")
    try:
        adc = ADC(Pin(PINS["tmp36"]))
        sleep_ms(5)
        raw = adc.read_u16()
        voltage = raw * 3.3 / 65535.0
        tmp36_c = (voltage - 0.5) * 100.0
    except Exception as e:
        print("TMP36 check failed:", e)
        return False

    print("{} raw={} voltage={:.3f}V TMP36_estimate={:.1f}C".format(
        pin_name(PINS["tmp36"]), raw, voltage, tmp36_c
    ))
    if 0.4 <= voltage <= 1.2:
        print("TMP36 status: OK plausible voltage")
        return True
    print("TMP36 status: suspicious voltage")
    return False


def pulse_led_pins():
    line("LED PIN PULSE")
    pins = (PINS["led_1"], PINS["led_2"])
    print("Pulsing LED pins: {}".format(pin_list(pins)))
    print("If the LEDs are simple LEDs, they should blink. NeoPixels may not blink from this simple pulse.")

    for pin in pins:
        try:
            p = Pin(pin, Pin.OUT, value=0)
            for _ in range(3):
                p.value(1)
                sleep_ms(80)
                p.value(0)
                sleep_ms(80)
            Pin(pin, Pin.IN, Pin.PULL_DOWN)
            print("{} pulsed".format(pin_name(pin)))
        except Exception as e:
            print("{} pulse error: {}".format(pin_name(pin), e))


def final_summary(i2c, mag, rtc, rfm, sd, gps, tmp36):
    line("SUMMARY")
    print("I2C modules: {}".format("OK" if i2c else "NOT FOUND"))
    print("Magnetometer: {}".format("FOUND" if mag else "NOT FOUND"))
    print("RTC DS1302:  {}".format("RESPONDS" if rtc else "NOT OK"))
    print("RFM69:       {}".format("OK" if rfm else "NOT OK"))
    print("SD card:     {}".format("OK basic response" if sd else "NOT OK"))
    print("GPS:         {}".format("OK" if gps else "NO DATA"))
    print("TMP36:       {}".format("OK" if tmp36 else "SUSPICIOUS"))
    print("")
    print("Main unresolved item should now be GPS if the magnetometer is detected at 0x2c.")


def main():
    print("")
    print("CANSAT focused hardware test")
    print("Soft reboot/startup complete.")

    print_pin_summary()
    passive_gpio_health()
    i2c = bool(scan_i2c())
    scan_all_i2c_addresses()
    mag = bool(scan_magnetometer_deep())
    rtc = read_rtc()
    tmp36 = check_tmp36()
    rfm = check_rfm69()
    sd = check_sd_card()
    gps = check_gps()
    pulse_led_pins()
    final_summary(i2c, mag, rtc, rfm, sd, gps, tmp36)

    print("")
    print("DONE")


main()
