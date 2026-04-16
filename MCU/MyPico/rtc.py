from machine import Pin
import utime


def dec2bcd(x):
    return ((x // 10) << 4) | (x % 10)


def bcd2dec(x):
    return ((x >> 4) * 10) + (x & 0x0F)


def is_valid_bcd(x):
    return ((x >> 4) & 0x0F) <= 9 and (x & 0x0F) <= 9


class DS1302:
    STUCK_TIMEOUT_MS = 5000

    REG_SECONDS = 0x80
    REG_MINUTES = 0x82
    REG_HOURS   = 0x84
    REG_DATE    = 0x86
    REG_MONTH   = 0x88
    REG_DAY     = 0x8A
    REG_YEAR    = 0x8C
    REG_WP      = 0x8E

    def __init__(self, clk=2, dat=3, rst=4):
        self.clk_pin = clk
        self.dat_pin = dat
        self.rst_pin = rst

        self.clk = Pin(clk, Pin.OUT, value=0)
        self.dat = Pin(dat, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=0)

        self.ok = False
        self.last_error = None
        self._last_datetime = None
        self._last_datetime_change_ms = None

        # Try one initial read so status reflects reality
        self.read()

    # -------------------------
    # Low-level
    # -------------------------
    def _start(self):
        self.clk.value(0)
        self.rst.value(1)
        utime.sleep_us(4)

    def _stop(self):
        self.rst.value(0)
        self.clk.value(0)
        utime.sleep_us(4)

    def _write_byte(self, value):
        self.dat.init(Pin.OUT)
        for _ in range(8):
            self.dat.value(value & 1)
            utime.sleep_us(1)
            self.clk.value(1)
            utime.sleep_us(1)
            self.clk.value(0)
            utime.sleep_us(1)
            value >>= 1

    def _read_byte(self):
        self.dat.init(Pin.IN)
        value = 0
        for i in range(8):
            bit = self.dat.value()
            value |= (bit << i)
            utime.sleep_us(1)
            self.clk.value(1)
            utime.sleep_us(1)
            self.clk.value(0)
            utime.sleep_us(1)
        return value

    def write_reg(self, reg, value):
        self._start()
        self._write_byte(reg & 0xFE)   # write command
        self._write_byte(value)
        self._stop()

    def read_reg(self, reg):
        self._start()
        self._write_byte(reg | 0x01)   # read command
        value = self._read_byte()
        self._stop()
        return value

    # -------------------------
    # Validation helpers
    # -------------------------
    def _read_raw_datetime_regs(self):
        sec_raw   = self.read_reg(self.REG_SECONDS)
        min_raw   = self.read_reg(self.REG_MINUTES)
        hour_raw  = self.read_reg(self.REG_HOURS)
        date_raw  = self.read_reg(self.REG_DATE)
        month_raw = self.read_reg(self.REG_MONTH)
        day_raw   = self.read_reg(self.REG_DAY)
        year_raw  = self.read_reg(self.REG_YEAR)

        return {
            "sec_raw": sec_raw,
            "min_raw": min_raw,
            "hour_raw": hour_raw,
            "date_raw": date_raw,
            "month_raw": month_raw,
            "day_raw": day_raw,
            "year_raw": year_raw,
        }

    def _validate_raw_datetime(self, raw):
        values = [
            raw["sec_raw"],
            raw["min_raw"],
            raw["hour_raw"],
            raw["date_raw"],
            raw["month_raw"],
            raw["day_raw"],
            raw["year_raw"],
        ]

        # Common "floating / disconnected" patterns
        if all(v == 0x00 for v in values):
            raise RuntimeError("DS1302 missing or not running (all registers read 0x00)")

        if all(v == 0xFF for v in values):
            raise RuntimeError("DS1302 missing or data line floating (all registers read 0xFF)")

        sec_bcd   = raw["sec_raw"] & 0x7F   # CH bit removed
        min_bcd   = raw["min_raw"] & 0x7F
        hour_bcd  = raw["hour_raw"] & 0x3F  # assuming 24h mode
        date_bcd  = raw["date_raw"] & 0x3F
        month_bcd = raw["month_raw"] & 0x1F
        day_bcd   = raw["day_raw"] & 0x07
        year_bcd  = raw["year_raw"]

        bcd_fields = [sec_bcd, min_bcd, hour_bcd, date_bcd, month_bcd, day_bcd, year_bcd]
        names = ["seconds", "minutes", "hours", "date", "month", "weekday", "year"]

        for name, value in zip(names, bcd_fields):
            if not is_valid_bcd(value):
                raise RuntimeError("DS1302 invalid BCD in {}".format(name))

        second = bcd2dec(sec_bcd)
        minute = bcd2dec(min_bcd)
        hour   = bcd2dec(hour_bcd)
        day    = bcd2dec(date_bcd)
        month  = bcd2dec(month_bcd)
        weekday = bcd2dec(day_bcd)
        year   = bcd2dec(year_bcd)

        # CH bit = 1 means oscillator halted
        if raw["sec_raw"] & 0x80:
            raise RuntimeError("DS1302 clock halted (CH bit set)")

        if not (0 <= second <= 59):
            raise RuntimeError("DS1302 invalid seconds")
        if not (0 <= minute <= 59):
            raise RuntimeError("DS1302 invalid minutes")
        if not (0 <= hour <= 23):
            raise RuntimeError("DS1302 invalid hours")
        if not (1 <= day <= 31):
            raise RuntimeError("DS1302 invalid day")
        if not (1 <= month <= 12):
            raise RuntimeError("DS1302 invalid month")
        if not (1 <= weekday <= 7):
            raise RuntimeError("DS1302 invalid weekday")

        return {
            "year": 2000 + year,
            "month": month,
            "day": day,
            "weekday": weekday,
            "hour": hour,
            "minute": minute,
            "second": second,
        }

    # -------------------------
    # Public
    # -------------------------
    def reconnect(self):
        try:
            self.clk = Pin(self.clk_pin, Pin.OUT, value=0)
            self.dat = Pin(self.dat_pin, Pin.OUT, value=0)
            self.rst = Pin(self.rst_pin, Pin.OUT, value=0)
            self._last_datetime = None
            self._last_datetime_change_ms = None
            result = self.read()
            return result["ok"]
        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return False

    def set_datetime(self, year, month, day, weekday, hour, minute, second):
        try:
            if not (2000 <= year <= 2099):
                raise ValueError("year must be 2000..2099")
            if not (1 <= month <= 12):
                raise ValueError("month must be 1..12")
            if not (1 <= day <= 31):
                raise ValueError("day must be 1..31")
            if not (1 <= weekday <= 7):
                raise ValueError("weekday must be 1..7")
            if not (0 <= hour <= 23):
                raise ValueError("hour must be 0..23")
            if not (0 <= minute <= 59):
                raise ValueError("minute must be 0..59")
            if not (0 <= second <= 59):
                raise ValueError("second must be 0..59")

            # disable write protection
            self.write_reg(self.REG_WP, 0x00)

            # clear CH bit so oscillator runs
            self.write_reg(self.REG_SECONDS, dec2bcd(second) & 0x7F)
            self.write_reg(self.REG_MINUTES, dec2bcd(minute))
            self.write_reg(self.REG_HOURS, dec2bcd(hour))     # 24h mode
            self.write_reg(self.REG_DATE, dec2bcd(day))
            self.write_reg(self.REG_MONTH, dec2bcd(month))
            self.write_reg(self.REG_DAY, dec2bcd(weekday))
            self.write_reg(self.REG_YEAR, dec2bcd(year % 100))

            # re-enable write protection
            self.write_reg(self.REG_WP, 0x80)

            self.ok = True
            self.last_error = None
            self._last_datetime = None
            self._last_datetime_change_ms = None
            return True

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return False

    def get_datetime(self):
        raw = self._read_raw_datetime_regs()
        return self._validate_raw_datetime(raw)

    def read(self):
        try:
            dt = self.get_datetime()
            now_ms = utime.ticks_ms()
            datetime_text = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                dt["year"], dt["month"], dt["day"],
                dt["hour"], dt["minute"], dt["second"]
            )

            if datetime_text != self._last_datetime:
                self._last_datetime = datetime_text
                self._last_datetime_change_ms = now_ms
            elif (
                self._last_datetime_change_ms is not None
                and utime.ticks_diff(now_ms, self._last_datetime_change_ms) > self.STUCK_TIMEOUT_MS
            ):
                raise RuntimeError("DS1302 time not advancing")

            data = {
                "ok": True,
                "year": dt["year"],
                "month": dt["month"],
                "day": dt["day"],
                "weekday": dt["weekday"],
                "hour": dt["hour"],
                "minute": dt["minute"],
                "second": dt["second"],
                "date": "{:04d}-{:02d}-{:02d}".format(dt["year"], dt["month"], dt["day"]),
                "time": "{:02d}:{:02d}:{:02d}".format(dt["hour"], dt["minute"], dt["second"]),
                "datetime": datetime_text
            }

            self.ok = True
            self.last_error = None
            return data

        except Exception as e:
            self.ok = False
            self.last_error = str(e)

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
                "error": str(e)
            }
