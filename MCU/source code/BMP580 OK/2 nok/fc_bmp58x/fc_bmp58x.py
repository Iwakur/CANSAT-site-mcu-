'''
BMP580, BMP581 and BMP585 Temperature and
Barometric Pressure sensors
MicroPython driver for micro:bit

EXAMPLE USAGE:
from fc_bmp58x import *
sensor = BMP58X()
Temperature = sensor.T
Pressure = sensor.P

4 x Sampling Modes as defined in datasheets:
  0 : Lowest power
  1 : Standard resolution (default)
  2 : High resolution
  3 : Highest resolution


Temperature returned in Celsius.
Pressure returned in hPa.

AUTHOR: fredscave.com
DATE  : 2025/07
VERSION : 1.00
'''

from microbit import *
from micropython import const

_REG_CHIP_ID     = const(0x01)
_REG_REV_ID      = const(0x02)
_REG_MEASURE     = const(0x1D)
_REG_DSP_IIR     = const(0x31)
_REG_OSR_CONFIG  = const(0x36)
_REG_ODR_CONFIG  = const(0x37)
_REG_OSR_REF     = const(0x38)
_REG_CMD         = const(0x7E)
_REG_INT_SOURCE  = const(0x15)
_REG_FIFO_CONFIG = const(0x16)
_REG_FIFO_LENGTH = const(0x17)
_REG_FIFO_SELECT = const(0x18)
_REG_FIFO_DATA   = const(0x29)
_REG_INT_STATUS  = const(0x27)

# Store temperature & pressure
_FIFO_SELECT = const(0x03)
_FIFO_STOP = const(0x00)
# Stop when FIFO is full.
_FIFO_MODE = const(0x20)
# FIFO full interrupt
_FIFO_FULL_INT = const(0x02)
_FIFO_EMPTY_FRAME = const(0x7F)

STANDBY       = const(0)
NORMAL        = const(1)
FORCED        = const(2)
CONTINUOUS    = const(3)
_CMD_PWR_MODE = (0, 1, 2, 3)

# OVERSAMPLE RATE configurations
# for Modes 0, 1, 2 and 3.
# As per datasheet page 20.
_MODE_OSR = (0x40, 0x50, 0x60, 0x7B)

# *** OUTPUT DATA RATE ***
#  Mode = 0
#    Sensor can be sampled every 4ms.
#  Mode = 1, 2 or 3
#    Default set to once per sec.
#    This can be changed by setting
#    another ODR value from table in
#    datasheet on page 60.
_DEFAULT_ODR = const(0x1C)
_MIN_ODR = (0, 0x04, 0x0D, 0x17)

# Forced power mode sampling time.
_ADCT_FORCED = 2

# IIR Filter Coefficient applied to pressure.
# There are eight levels (0 to 7) from bypass (off)
# through to maximum filtering level.
# Default is no filtering.
_IIR_COEFF = (0x00, 0x08, 0x10, 0x18,
              0x20, 0x28, 0x30, 0x38)

# Convert Celsius to Fahrenheit
CtoF = lambda C, d=1: round((C * 9/5) +32, d)

class BMP58X():
    def __init__(self, ADDR=0x47):
        self.ADDR = ADDR
        self.ODR = _DEFAULT_ODR
        self.IIR = 0
        # Enable FIFO full interrupt.
        self._writeReg([_REG_INT_SOURCE, _FIFO_FULL_INT])
        self.SetMode()

    # Mode 0 : Forced power mode
    # Mode 1 to 3 : Normal power mode
    # Higher modes use more power
    # but return higher resolution.
    def SetMode(self, Mode=1):
        if Mode in (0, 1, 2, 3):
            self.Mode = Mode
        else:
            self.Mode = 1
        self._writeReg([_REG_OSR_CONFIG, _MODE_OSR[Mode]])
        if Mode != 0:
            # Turn on Normal power mode
            self.SetODR(self.ODR)
            self._setPowerMode(NORMAL)

    # Sets the Output Data Rate (ODR).
    # This setting is only used in NORMAL
    # power mode. (Mode = 1, 2 or 3)
    # If the user attempts to set an ODR that
    # is too fast then this method adjusts
    # rate to highest possible that works.
    # Valid values are 0x04 .. 0x1F.
    def SetODR(self, ODR=_DEFAULT_ODR):
        if ODR < _MIN_ODR[self.Mode]:
            odr = _MIN_ODR[self.Mode]
        else:
            odr = ODR
        buf = self._readReg(_REG_ODR_CONFIG, 1)
        reg = buf[0]
        reg = reg & 0b10000011
        reg = reg | (odr << 2)
        self._writeReg([_REG_ODR_CONFIG, reg])
        self.ODR = odr

    # Sets the IIR filtering level.
    # Valid value is 0..7
    # 0 = filter off, 7 = max filtering.
    def SetIIR(self, IIR=0):
        if IIR in range(8):
            self.IIR = IIR
        else:
            self.IIR = 0
        # Stop conversions
        self._setPowerMode(STANDBY)
        # Write filter setting
        self._writeReg([_REG_DSP_IIR, _IIR_COEFF[self.IIR]])
        # Turn on sampling
        self.SetMode(self.Mode)

# *******************************************
#              Properties
# *******************************************

    # Trigger and return both temperature
    # and pressure measurements.
    @property
    def Reading(self):
       # Read unconverted temperature and pressure.
        if self.Mode == 0:
            self._setPowerMode(FORCED)
            sleep(_ADCT_FORCED)
        buf = self._readReg(_REG_MEASURE, 6)
        temperature = (buf[2] << 16) + (buf[1] << 8) + buf[0]
        pressure = (buf[5] << 16) + (buf[4] << 8) + buf[3]
        # Convert to actual values
        return self._convert(temperature, pressure)

    # Returns temperature only
    @property
    def T(self):
        return self.Reading[0]

    # Returns pressure only
    @property
    def P(self):
        return self.Reading[1]

    # Returns the chip's ID
    @property
    def ID(self):
        id = self._readReg(_REG_CHIP_ID, 1)
        return hex(id[0])

    # Chip revision number
    @property
    def RevID(self):
        id = self._readReg(_REG_REV_ID, 1)
        return hex(id[0])


    # Returns Mode where:
    # 0 : Forced power mode.
    # 1..3 : Normal power mode.
    @property
    def GetMode(self):
        return self.Mode

    # Returns odr_set parameter.
    # This value determines the sampling period
    # when the sensor is in Mode 1 i.e Normal
    @property
    def GetODR(self):
        return hex(self.ODR)

    # Returns the IIR filter setting.
    # Value is in 0..7
    @property
    def GetIIR(self):
        return self.IIR

# *******************************************
#          FIFO Methods and Properties
# *******************************************

    # Starts writing temperature and pressure
    # unconverted values to the FIFO queue.
    def FIFOStart(self):
        # Ensure Normal sampling mode is on.
        if self.Mode == 0:
            self.SetMode(1)
        # Must be in STANDBY power mode to config.
        self._setPowerMode(STANDBY)
        self._writeReg([_REG_FIFO_CONFIG, _FIFO_MODE])
        self._writeReg([_REG_FIFO_SELECT, _FIFO_SELECT])
        # Turn on sampling & FIFO
        self.SetMode(self.Mode)

    # Stops writing to the FIFO queue.
    # The FIFO is flushed.
    def FIFOStop(self):
        # Must be in STANDBY power mode.
        self._setPowerMode(STANDBY)
        self._writeReg([_REG_FIFO_SELECT, _FIFO_STOP])
        sleep(3)
        # Turn on sampling
        self.SetMode(self.Mode)

    # Returns the number of records in the FIFO queue.
    @property
    def FIFOLength(self):
        buf = self._readReg(_REG_FIFO_LENGTH, 1)
        return buf[0]

    # Reads all bytes in the FIFO queue.
    # Sensor data frames are parsed to retrieve
    # all stored raw temperature and
    # pressure values. They are converted and
    # returned as a list of tuples of actual values.
    @property
    def FIFORead(self):
        length = self.FIFOLength
        buf = self._readReg(_REG_FIFO_DATA, length*6)
        i = 0
        data = []
        while i < length:
            count = i * 6
            if buf[count] == _FIFO_EMPTY_FRAME:
                break
            else:
                temperature = (buf[count+2] << 16) + (buf[count+1] << 8) + buf[count]
                pressure = (buf[count+5] << 16) + (buf[count+4] << 8) + buf[count+3]
                i += 1
                data.append(self._convert(temperature, pressure))
        return data

    # Returns True if the FIFO queue is full.
    @property
    def IsFIFOFull(self):
        buf = self._readReg(_REG_INT_STATUS, 1)
        return (buf[0] & 0b10) == 0b10

# *******************************************
#             Altitude Calculations
# *******************************************

    # Calculate mean sea level pressure (MSLP)
    # If the altitude of the sensor is known then
    # the absolute pressure can be adjusted to its
    # equivalent sea level pressure.
    #
    # This is the pressure that is reported by
    # official weather services.
    def MSLP(self, Altitude=None):
        if Altitude == None:
            return None
        else:
            P0 = 1013.25
            a = 2.25577E-5
            b = 5.25588
            P = self.Reading[1]
            PS = P0 * (1 - a * Altitude) ** b
            offset = P0 - PS
            return P + offset

    # If pressure readings are taken at different
    # altitudes then this method will calculate
    # the difference between these two altitudes
    # in meters.
    def AltDiff(self, P1, P2):
        a = 0.1157227
        return (P1 - P2) / a

    # If the Mean Sea Level pressure is known
    # (usually obtained from the local weather service)
    # then this method will calculate the altitude
    # of the sensor in meters.
    # The sensor is read to obtain the absolute
    # pressure value.
    def Altitude(self, MSLP=None):
        if MSLP == None:
            return None
        else:
            p = self.P
            a = -2.25577E-5
            b = 0.1902631
            h = (((p/MSLP) ** b) - 1) / a
            return int(round(h, 0))

# *******************************************
#              Private Methods
# *******************************************

    # Sets the power mode. One of:
    # STANDBY, NORMAL, FORCED, CONTINUOUS.
    def _setPowerMode(self, PwrMode):
        buf = self._readReg(_REG_ODR_CONFIG, 1)
        reg = buf[0]
        reg = (reg >> 2) << 2
        reg = reg | _CMD_PWR_MODE[PwrMode]
        self._writeReg([_REG_ODR_CONFIG, reg])

    # Convert raw temperature and pressure
    # to Celsius and hectopascals.
    def _convert(self, temperature, pressure):
        if temperature > 8388607:
            temp = temperature - 16777216
        else:
            temp = temperature
        return (temp / 65536, pressure / 6400)


    # Writes one or more bytes to register.
    # Bytes is expected to be a list.
    # First element is the register address.
    def _writeReg(self, Bytes):
        i2c.write(self.ADDR, bytes(Bytes))

    # Read a given number of bytes from
    # a register.
    def _readReg(self, Reg, Num):
        self._writeReg([Reg])
        buf = i2c.read(self.ADDR, Num)
        return buf

