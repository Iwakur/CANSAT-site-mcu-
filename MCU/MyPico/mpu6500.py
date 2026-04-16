import time
import struct
import math


class MPU6500:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        self.ok = False
        self.last_error = None

        # Offsets from calibration
        self.gx_off = 0
        self.gy_off = 0
        self.gz_off = 0
        self.ax_off = 0
        self.ay_off = 0
        self.az_off = 0

        self._init_sensor()

    # -------------------------
    # LOW LEVEL
    # -------------------------
    def write_reg(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def read_reg(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    # -------------------------
    # INIT
    # -------------------------
    def _init_sensor(self):
        try:
            who_am_i = self.read_reg(0x75)
            if who_am_i != 0x70:
                raise RuntimeError("MPU6500 not detected, WHO_AM_I=0x{:02X}".format(who_am_i))

            # Wake up
            self.write_reg(0x6B, 0x00)
            time.sleep_ms(100)

            # Sample rate / filtering / ranges
            self.write_reg(0x19, 0x07)  # sample rate divider
            self.write_reg(0x1A, 0x03)  # DLPF ~44 Hz
            self.write_reg(0x1B, 0x00)  # gyro ±250 dps
            self.write_reg(0x1C, 0x00)  # accel ±2g

            self.ok = True
            self.last_error = None

        except Exception as e:
            self.ok = False
            self.last_error = str(e)

    # -------------------------
    # RAW READ
    # -------------------------
    def _read_raw(self):
        data = self.i2c.readfrom_mem(self.addr, 0x3B, 14)
        ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", data)
        return ax, ay, az, gx, gy, gz, temp

    # -------------------------
    # CALIBRATION
    # -------------------------
    def calibrate(self, samples=300):
        gx_off = gy_off = gz_off = 0
        ax_off = ay_off = az_off = 0

        good = 0
        max_attempts = samples * 3
        attempts = 0

        while good < samples and attempts < max_attempts:
            attempts += 1
            try:
                ax, ay, az, gx, gy, gz, _ = self._read_raw()

                gx_off += gx
                gy_off += gy
                gz_off += gz

                ax_off += ax
                ay_off += ay
                az_off += (az - 16384)  # remove 1g from Z axis

                good += 1
                time.sleep_ms(5)

            except OSError:
                time.sleep_ms(10)

        if good == 0:
            raise RuntimeError("MPU6500 calibration failed: no valid samples")

        self.gx_off = gx_off / good
        self.gy_off = gy_off / good
        self.gz_off = gz_off / good

        self.ax_off = ax_off / good
        self.ay_off = ay_off / good
        self.az_off = az_off / good

    # -------------------------
    # PITCH / ROLL
    # -------------------------
    def _calculate_pitch_roll(self, ax_g, ay_g, az_g):
        pitch = math.degrees(math.atan2(ax_g, math.sqrt(ay_g * ay_g + az_g * az_g)))
        roll = math.degrees(math.atan2(ay_g, math.sqrt(ax_g * ax_g + az_g * az_g)))
        return pitch, roll

    # -------------------------
    # MAIN READ
    # -------------------------
    def read(self):
        try:
            ax, ay, az, gx, gy, gz, temp = self._read_raw()

            # apply calibration offsets
            ax -= self.ax_off
            ay -= self.ay_off
            az -= self.az_off

            gx -= self.gx_off
            gy -= self.gy_off
            gz -= self.gz_off

            # convert raw values to real units
            ax_g = ax / 16384.0
            ay_g = ay / 16384.0
            az_g = az / 16384.0

            gx_dps = gx / 131.0
            gy_dps = gy / 131.0
            gz_dps = gz / 131.0

            temp_c = temp / 333.87 + 21.0

            pitch_deg, roll_deg = self._calculate_pitch_roll(ax_g, ay_g, az_g)

            self.ok = True
            self.last_error = None

            return {
                "ok": True,
                "ax": ax_g,
                "ay": ay_g,
                "az": az_g,
                "gx": gx_dps,
                "gy": gy_dps,
                "gz": gz_dps,
                "temp": temp_c,
                "pitch": pitch_deg,
                "roll": roll_deg,
                "error": None
            }

        except Exception as e:
            self.ok = False
            self.last_error = str(e)

            return {
                "ok": False,
                "ax": None,
                "ay": None,
                "az": None,
                "gx": None,
                "gy": None,
                "gz": None,
                "temp": None,
                "pitch": None,
                "roll": None,
                "error": str(e)
            }

    # -------------------------
    # RECONNECT
    # -------------------------
    def reconnect(self):
        self._init_sensor()