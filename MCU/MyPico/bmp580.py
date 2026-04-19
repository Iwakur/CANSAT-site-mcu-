import time

try:
    import struct
except ImportError:
    import ustruct as struct

from micropython import const


# =========================================================
# I2C HELPERS
# =========================================================
class CBits:
    def __init__(
        self,
        num_bits: int,
        register_address: int,
        start_bit: int,
        register_width=1,
        lsb_first=True,
    ) -> None:
        self.bit_mask = ((1 << num_bits) - 1) << start_bit
        self.register = register_address
        self.start_bit = start_bit
        self.length = register_width
        self.lsb_first = lsb_first

    def __get__(self, obj, objtype=None) -> int:
        mem_value = obj._i2c.readfrom_mem(obj._address, self.register, self.length)

        reg = 0
        order = range(len(mem_value) - 1, -1, -1)
        if not self.lsb_first:
            order = reversed(order)

        for i in order:
            reg = (reg << 8) | mem_value[i]

        reg = (reg & self.bit_mask) >> self.start_bit
        return reg

    def __set__(self, obj, value: int) -> None:
        memory_value = obj._i2c.readfrom_mem(obj._address, self.register, self.length)

        reg = 0
        order = range(len(memory_value) - 1, -1, -1)
        if not self.lsb_first:
            order = range(0, len(memory_value))

        for i in order:
            reg = (reg << 8) | memory_value[i]

        reg &= ~self.bit_mask
        value <<= self.start_bit
        reg |= value
        reg = reg.to_bytes(self.length, "big")

        obj._i2c.writeto_mem(obj._address, self.register, reg)


class RegisterStruct:
    def __init__(self, register_address: int, form: str) -> None:
        self.format = form
        self.register = register_address
        self.length = struct.calcsize(form)

    def __get__(self, obj, objtype=None):
        data = obj._i2c.readfrom_mem(obj._address, self.register, self.length)
        if self.length <= 2:
            value = struct.unpack(self.format, memoryview(data))[0]
        else:
            value = struct.unpack(self.format, memoryview(data))
        return value

    def __set__(self, obj, value):
        mem_value = struct.pack(self.format, value)
        obj._i2c.writeto_mem(obj._address, self.register, mem_value)


# =========================================================
# BMP581 / project name BMP580
# =========================================================
WORLD_AVERAGE_SEA_LEVEL_PRESSURE = 1013.25


class BMP581:
    # Power modes
    STANDBY = const(0x00)
    NORMAL = const(0x01)
    FORCED = const(0x02)
    NON_STOP = const(0x03)
    power_mode_values = (STANDBY, NORMAL, FORCED, NON_STOP)

    # Oversampling
    OSR1 = const(0x00)
    OSR2 = const(0x01)
    OSR4 = const(0x02)
    OSR8 = const(0x03)
    OSR16 = const(0x04)
    OSR32 = const(0x05)
    OSR64 = const(0x06)
    OSR128 = const(0x07)

    pressure_oversample_rate_values = (OSR1, OSR2, OSR4, OSR8, OSR16, OSR32, OSR64, OSR128)
    temperature_oversample_rate_values = (OSR1, OSR2, OSR4, OSR8, OSR16, OSR32, OSR64, OSR128)

    # IIR filter
    COEF_0 = const(0x00)
    COEF_1 = const(0x01)
    COEF_3 = const(0x02)
    COEF_7 = const(0x03)
    COEF_15 = const(0x04)
    COEF_31 = const(0x05)
    COEF_63 = const(0x06)
    COEF_127 = const(0x07)
    iir_coefficient_values = (COEF_0, COEF_1, COEF_3, COEF_7, COEF_15, COEF_31, COEF_63, COEF_127)

    BMP581_I2C_ADDRESS_DEFAULT = 0x47
    BMP581_I2C_ADDRESS_SECONDARY = 0x46

    # Registers
    _REG_WHOAMI = const(0x01)
    _INT_STATUS = const(0x27)
    _DSP_CONFIG = const(0x30)
    _DSP_IIR = const(0x31)
    _OSR_CONF = const(0x36)
    _ODR_CONFIG = const(0x37)
    _CMD_BMP581 = const(0x7E)

    _SOFTRESET = const(0xB6)

    _device_id = RegisterStruct(_REG_WHOAMI, "B")
    _cmd_register_BMP581 = CBits(8, _CMD_BMP581, 0)
    _drdy_status = CBits(1, _INT_STATUS, 0)
    _power_mode_reg = CBits(2, _ODR_CONFIG, 0)
    _temperature_oversample_rate_reg = CBits(3, _OSR_CONF, 0)
    _pressure_oversample_rate_reg = CBits(3, _OSR_CONF, 3)
    _output_data_rate_reg = CBits(5, _ODR_CONFIG, 2)
    _pressure_enabled_reg = CBits(1, _OSR_CONF, 6)
    _iir_coefficient_reg = CBits(3, _DSP_IIR, 3)
    _iir_temp_coefficient_reg = CBits(3, _DSP_IIR, 0)
    _iir_control_reg = CBits(8, _DSP_CONFIG, 0)
    _temperature_reg = CBits(24, 0x1D, 0, 3)
    _pressure_reg = CBits(24, 0x20, 0, 3)

    def __init__(
        self,
        i2c,
        address=None,
        sea_level_pressure=WORLD_AVERAGE_SEA_LEVEL_PRESSURE,
        pressure_osr=OSR128,
        temperature_osr=OSR8,
        iir_coef=COEF_7,
    ):
        self._i2c = i2c
        self._address = None

        self.ok = False
        self.last_error = None

        # wanted config, reused after reconnect
        self._wanted_sea_level_pressure = sea_level_pressure
        self._wanted_pressure_osr = pressure_osr
        self._wanted_temperature_osr = temperature_osr
        self._wanted_iir_coef = iir_coef

        self._init_sensor(address)

    def _init_sensor(self, address):
        time.sleep_ms(3)

        if address is None:
            if self._check_address(self._i2c, self.BMP581_I2C_ADDRESS_DEFAULT):
                address = self.BMP581_I2C_ADDRESS_DEFAULT
            elif self._check_address(self._i2c, self.BMP581_I2C_ADDRESS_SECONDARY):
                address = self.BMP581_I2C_ADDRESS_SECONDARY
            else:
                raise RuntimeError("BMP581 sensor not found at I2C expected address (0x47, 0x46)")
        else:
            if not self._check_address(self._i2c, address):
                raise RuntimeError("BMP581 sensor not found at specified I2C address ({})".format(hex(address)))

        self._address = address

        if self._read_device_id() != 0x50:
            raise RuntimeError("Failed to find the BMP581 sensor")

        # soft reset
        self._cmd_register_BMP581 = 0xB6
        time.sleep_ms(5)

        self._configure()

        # let it settle a bit and throw away first samples
        self._warmup_reads()

        self.ok = True
        self.last_error = None

    def _configure(self):
        # standby before config changes
        self._power_mode_reg = self.STANDBY
        time.sleep_ms(5)

        self._pressure_enabled_reg = 1
        self._output_data_rate_reg = 0
        self._temperature_oversample_rate_reg = self._wanted_temperature_osr
        self._pressure_oversample_rate_reg = self._wanted_pressure_osr
        self._iir_coefficient_reg = self._wanted_iir_coef
        self._iir_temp_coefficient_reg = self._wanted_iir_coef
        self.sea_level_pressure = self._wanted_sea_level_pressure

        self._power_mode_reg = self.NORMAL
        time.sleep_ms(5)

    def _warmup_reads(self, count=3, delay_ms=20):
        for _ in range(count):
            try:
                _ = self.temperature
                _ = self.pressure
            except Exception:
                pass
            time.sleep_ms(delay_ms)

    def _check_address(self, i2c, address: int) -> bool:
        try:
            if address in i2c.scan():
                return True
            i2c.writeto(address, b"")
            return True
        except OSError:
            return False

    def _read_device_id(self) -> int:
        return self._device_id

    @property
    def temperature(self) -> float:
        raw_temp = self._temperature_reg
        return self._twos_comp(raw_temp, 24) / 65536.0

    @property
    def pressure(self) -> float:
        raw_pressure = self._pressure_reg
        return self._twos_comp(raw_pressure, 24) / 64.0 / 100.0

    @property
    def altitude(self) -> float:
        return 44330.77 * (1.0 - ((self.pressure / self.sea_level_pressure) ** 0.1902632))

    @altitude.setter
    def altitude(self, value: float) -> None:
        self.sea_level_pressure = self.pressure / (1.0 - value / 44330.77) ** (1 / 0.1902632)

    @property
    def sea_level_pressure(self) -> float:
        return self._sea_level_pressure

    @sea_level_pressure.setter
    def sea_level_pressure(self, value: float) -> None:
        self._sea_level_pressure = value

    @staticmethod
    def _twos_comp(val: int, bits: int) -> int:
        if val & (1 << (bits - 1)):
            return val - (1 << bits)
        return val

    def _values_are_sane(self, temperature, pressure, altitude):
        # broad ranges, so future bigger changes still remain allowed
        if not (-40 <= temperature <= 85):
            return False
        if not (300 <= pressure <= 1100):
            return False
        if not (-1000 <= altitude <= 20000):
            return False
        return True

    def read(self):
        try:
            temperature = self.temperature
            pressure = self.pressure
            altitude = self.altitude

            if not self._values_are_sane(temperature, pressure, altitude):
                raise ValueError(
                    "invalid BMP581 reading: T={:.2f}C P={:.2f}hPa A={:.2f}m".format(
                        temperature, pressure, altitude
                    )
                )

            self.ok = True
            self.last_error = None

            return {
                "ok": True,
                "temperature_c": temperature,
                "pressure_hpa": pressure,
                "altitude_m": altitude,
                "error": None,
            }

        except Exception as e:
            self.ok = False
            self.last_error = str(e)

            return {
                "ok": False,
                "temperature_c": None,
                "pressure_hpa": None,
                "altitude_m": None,
                "error": str(e),
            }

    def reconnect(self):
        try:
            current_address = self._address

            # small delay so power / bus can settle
            time.sleep_ms(50)

            self._init_sensor(current_address)

            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return False


# project naming alias
BMP580 = BMP581
