import math
import time


class GY271:
    QMC5883P_ADDRESS = 0x2C
    QMC5883L_ADDRESS = 0x0D
    QMC5883L_ALT_ADDRESS = 0x0C
    HMC5883L_ADDRESS = 0x1E

    CHIP_QMC5883P = "QMC5883P"
    CHIP_QMC5883L = "QMC5883L"
    CHIP_HMC5883L = "HMC5883L"

    def __init__(self, i2c, address=None):
        self.i2c = i2c
        self.address = address
        self.chip = None
        self.ok = False
        self.last_error = None

        self._init_sensor()

    # -------------------------
    # LOW LEVEL
    # -------------------------
    def _write_reg(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes([value]))

    def _read_reg(self, register):
        return self.i2c.readfrom_mem(self.address, register, 1)[0]

    def _read_regs(self, register, length):
        return self.i2c.readfrom_mem(self.address, register, length)

    def _check_address(self, address):
        try:
            self.i2c.writeto(address, b"")
            return True
        except OSError:
            return False

    def _int16_le(self, lsb, msb):
        value = (msb << 8) | lsb
        if value & 0x8000:
            value -= 0x10000
        return value

    def _int16_be(self, msb, lsb):
        value = (msb << 8) | lsb
        if value & 0x8000:
            value -= 0x10000
        return value

    # -------------------------
    # INIT
    # -------------------------
    def _init_sensor(self):
        try:
            self.chip = None

            if self.address is None:
                if self._check_address(self.QMC5883P_ADDRESS):
                    self.address = self.QMC5883P_ADDRESS
                    self.chip = self.CHIP_QMC5883P
                elif self._check_address(self.QMC5883L_ADDRESS):
                    self.address = self.QMC5883L_ADDRESS
                    self.chip = self.CHIP_QMC5883L
                elif self._check_address(self.QMC5883L_ALT_ADDRESS):
                    self.address = self.QMC5883L_ALT_ADDRESS
                    self.chip = self.CHIP_QMC5883L
                elif self._check_address(self.HMC5883L_ADDRESS):
                    self.address = self.HMC5883L_ADDRESS
                    self.chip = self.CHIP_HMC5883L
                else:
                    raise RuntimeError("GY-271 magnetometer not found at 0x2C, 0x0D, 0x0C, or 0x1E")
            elif self.address == self.QMC5883P_ADDRESS:
                if not self._check_address(self.address):
                    raise RuntimeError("QMC5883P not found at 0x2C")
                self.chip = self.CHIP_QMC5883P
            elif self.address == self.QMC5883L_ADDRESS or self.address == self.QMC5883L_ALT_ADDRESS:
                if not self._check_address(self.address):
                    raise RuntimeError("QMC5883L not found at {}".format(hex(self.address)))
                self.chip = self.CHIP_QMC5883L
            elif self.address == self.HMC5883L_ADDRESS:
                if not self._check_address(self.address):
                    raise RuntimeError("HMC5883L not found at 0x1E")
                self.chip = self.CHIP_HMC5883L
            else:
                raise ValueError("unsupported GY-271 address {}".format(hex(self.address)))

            if self.chip == self.CHIP_QMC5883P:
                self._init_qmc5883p()
            elif self.chip == self.CHIP_QMC5883L:
                self._init_qmc5883l()
            else:
                self._init_hmc5883l()

            time.sleep_ms(20)
            self.ok = True
            self.last_error = None

        except Exception as e:
            self.ok = False
            self.last_error = str(e)

    def _init_qmc5883p(self):
        chip_id = self._read_reg(0x00)
        if chip_id != 0x80:
            raise RuntimeError("QMC5883P bad chip id 0x{:02X}".format(chip_id))

        # Soft reset, then continuous mode, 50Hz, 8G range.
        self._write_reg(0x0B, 0x80)
        time.sleep_ms(50)
        self._write_reg(0x0B, 0x08)
        self._write_reg(0x0A, 0x07)
        time.sleep_ms(20)

    def _init_qmc5883l(self):
        # Soft reset, define set/reset period, then continuous mode.
        self._write_reg(0x0A, 0x80)
        time.sleep_ms(10)
        self._write_reg(0x0B, 0x01)
        # OSR=512, RNG=8G, ODR=50Hz, MODE=continuous.
        self._write_reg(0x09, 0x1D)

    def _init_hmc5883l(self):
        # 8-average, 15Hz, normal measurement; gain +/-4.7G; continuous mode.
        self._write_reg(0x00, 0x70)
        self._write_reg(0x01, 0xA0)
        self._write_reg(0x02, 0x00)

    # -------------------------
    # PUBLIC
    # -------------------------
    def reconnect(self):
        wanted_address = self.address
        self.ok = False
        self.last_error = None
        self.address = wanted_address
        self._init_sensor()
        return self.ok

    def read(self):
        try:
            if not self.ok:
                if not self.reconnect():
                    return self._error_result(self.last_error or "magnetometer reconnect failed")

            if self.chip == self.CHIP_QMC5883P:
                result = self._read_qmc5883p()
            elif self.chip == self.CHIP_QMC5883L:
                result = self._read_qmc5883l()
            else:
                result = self._read_hmc5883l()

            self.ok = result["ok"]
            self.last_error = None if result["ok"] else result["error"]
            return result

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return self._error_result(str(e))

    # -------------------------
    # CHIP READS
    # -------------------------
    def _read_qmc5883p(self):
        status = self._read_reg(0x09)
        data = self._read_regs(0x01, 6)

        x = self._int16_le(data[0], data[1])
        y = self._int16_le(data[2], data[3])
        z = self._int16_le(data[4], data[5])

        overflow = bool(status & 0x02)
        if overflow:
            return self._error_result("QMC5883P magnetic overflow", overflow=True)

        return self._result(x, y, z, bool(status & 0x01), overflow)

    def _read_qmc5883l(self):
        status = self._read_reg(0x06)
        data = self._read_regs(0x00, 6)

        x = self._int16_le(data[0], data[1])
        y = self._int16_le(data[2], data[3])
        z = self._int16_le(data[4], data[5])

        overflow = bool(status & 0x02)
        if overflow:
            return self._error_result("QMC5883L magnetic overflow", overflow=True)

        return self._result(x, y, z, bool(status & 0x01), overflow)

    def _read_hmc5883l(self):
        status = self._read_reg(0x09)
        data = self._read_regs(0x03, 6)

        x = self._int16_be(data[0], data[1])
        z = self._int16_be(data[2], data[3])
        y = self._int16_be(data[4], data[5])

        return self._result(x, y, z, bool(status & 0x01), False)

    # -------------------------
    # RESULT HELPERS
    # -------------------------
    def _heading(self, x, y):
        heading = math.degrees(math.atan2(y, x))
        if heading < 0:
            heading += 360.0
        return heading

    def _result(self, x, y, z, data_ready, overflow):
        return {
            "ok": True,
            "chip": self.chip,
            "x": x,
            "y": y,
            "z": z,
            "heading_deg": self._heading(x, y),
            "data_ready": data_ready,
            "overflow": overflow,
            "error": None,
        }

    def _error_result(self, error_text, overflow=False):
        return {
            "ok": False,
            "chip": self.chip,
            "x": None,
            "y": None,
            "z": None,
            "heading_deg": None,
            "data_ready": False,
            "overflow": overflow,
            "error": error_text,
        }
