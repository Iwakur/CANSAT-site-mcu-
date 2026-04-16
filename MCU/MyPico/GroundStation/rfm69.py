from machine import Pin, SoftSPI
import utime


class RFM69:
    # Registers
    REG_FIFO = 0x00
    REG_OPMODE = 0x01
    REG_DATAMODUL = 0x02
    REG_BITRATEMSB = 0x03
    REG_BITRATELSB = 0x04
    REG_FDEVMSB = 0x05
    REG_FDEVLSB = 0x06
    REG_FRFMSB = 0x07
    REG_FRFMID = 0x08
    REG_FRFLSB = 0x09
    REG_VERSION = 0x10
    REG_PALEVEL = 0x11
    REG_LNA = 0x18
    REG_RXBW = 0x19
    REG_DIOMAPPING1 = 0x25
    REG_IRQFLAGS1 = 0x27
    REG_IRQFLAGS2 = 0x28
    REG_RSSITHRESH = 0x29
    REG_PREAMBLEMSB = 0x2C
    REG_PREAMBLELSB = 0x2D
    REG_SYNCCONFIG = 0x2E
    REG_SYNCVALUE1 = 0x2F
    REG_PACKETCONFIG1 = 0x37
    REG_PAYLOADLENGTH = 0x38
    REG_FIFOTHRESH = 0x3C
    REG_PACKETCONFIG2 = 0x3D

    # Modes
    MODE_SLEEP = 0x00
    MODE_STDBY = 0x04
    MODE_TX = 0x0C
    MODE_RX = 0x10
    EXPECTED_VERSION = 0x24

    def __init__(
        self,
        sck_pin=27,
        mosi_pin=28,
        miso_pin=26,
        cs_pin=14,
        rst_pin=None,
        frequency_mhz=434.0,
        bitrate=4800,
        sync_word=b"\x2D\xD4",
        tx_power_dbm=13,
        spi_baudrate=1000000
    ):
        self.sck_pin = sck_pin
        self.mosi_pin = mosi_pin
        self.miso_pin = miso_pin
        self.cs_pin = cs_pin
        self.rst_pin = rst_pin
        self.frequency_mhz = frequency_mhz
        self.bitrate = bitrate
        self.sync_word = sync_word
        self.tx_power_dbm = tx_power_dbm
        self.spi_baudrate = spi_baudrate

        self.spi = None
        self.cs = None
        self.rst = None

        self.ok = False
        self.last_error = None

        self._init_radio()

    # -------------------------
    # Low level
    # -------------------------
    def _select(self):
        self.cs.value(0)

    def _unselect(self):
        self.cs.value(1)

    def _write_reg(self, reg, value):
        self._select()
        self.spi.write(bytes([reg | 0x80, value]))
        self._unselect()

    def _read_reg(self, reg):
        self._select()
        self.spi.write(bytes([reg & 0x7F]))
        value = self.spi.read(1, 0x00)[0]
        self._unselect()
        return value

    def _burst_write(self, reg, data):
        self._select()
        self.spi.write(bytes([reg | 0x80]))
        self.spi.write(data)
        self._unselect()

    def _burst_read(self, reg, length):
        self._select()
        self.spi.write(bytes([reg & 0x7F]))
        data = self.spi.read(length, 0x00)
        self._unselect()
        return data

    # -------------------------
    # Config helpers
    # -------------------------
    def _set_mode(self, mode):
        self._write_reg(self.REG_OPMODE, 0x80 | mode)
        utime.sleep_ms(10)

    def _set_frequency(self, mhz):
        # FSTEP = 32 MHz / 2^19 = 61.03515625 Hz
        frf = int((mhz * 1000000.0) / 61.03515625)
        self._write_reg(self.REG_FRFMSB, (frf >> 16) & 0xFF)
        self._write_reg(self.REG_FRFMID, (frf >> 8) & 0xFF)
        self._write_reg(self.REG_FRFLSB, frf & 0xFF)

    def _set_bitrate(self, bitrate):
        rate = int(32000000 / bitrate)
        self._write_reg(self.REG_BITRATEMSB, (rate >> 8) & 0xFF)
        self._write_reg(self.REG_BITRATELSB, rate & 0xFF)

    def _hardware_reset(self):
        if self.rst is None:
            return
        self.rst.value(1)
        utime.sleep_ms(1)
        self.rst.value(0)
        utime.sleep_ms(20)

    def _clear_fifo(self):
        self._set_mode(self.MODE_STDBY)
        self._write_reg(self.REG_IRQFLAGS2, 0x10)
        self._set_mode(self.MODE_RX)

    # -------------------------
    # Init
    # -------------------------
    def _init_radio(self):
        try:
            self.spi = SoftSPI(
                baudrate=self.spi_baudrate,
                polarity=0,
                phase=0,
                sck=Pin(self.sck_pin),
                mosi=Pin(self.mosi_pin),
                miso=Pin(self.miso_pin)
            )

            self.cs = Pin(self.cs_pin, Pin.OUT, value=1)

            if self.rst_pin is None:
                self.rst = None
            else:
                self.rst = Pin(self.rst_pin, Pin.OUT, value=0)

            self._hardware_reset()
            utime.sleep_ms(30)

            self._set_mode(self.MODE_STDBY)

            # Packet mode, FSK
            self._write_reg(self.REG_DATAMODUL, 0x00)

            # Bitrate and deviation
            self._set_bitrate(self.bitrate)
            self._write_reg(self.REG_FDEVMSB, 0x05)
            self._write_reg(self.REG_FDEVLSB, 0xC3)

            # Frequency
            self._set_frequency(self.frequency_mhz)

            # PA0 on, output power
            power = max(0, min(31, self.tx_power_dbm + 18))
            self._write_reg(self.REG_PALEVEL, 0x80 | power)

            # LNA / bandwidth / RSSI threshold
            self._write_reg(self.REG_LNA, 0x88)
            self._write_reg(self.REG_RXBW, 0x55)
            self._write_reg(self.REG_RSSITHRESH, 220)

            # Preamble
            self._write_reg(self.REG_PREAMBLEMSB, 0x00)
            self._write_reg(self.REG_PREAMBLELSB, 0x03)

            # Sync config
            self._write_reg(
                self.REG_SYNCCONFIG,
                0x88 | ((len(self.sync_word) - 1) & 0x07)
            )
            for i, b in enumerate(self.sync_word):
                self._write_reg(self.REG_SYNCVALUE1 + i, b)

            # Variable length, CRC on
            self._write_reg(self.REG_PACKETCONFIG1, 0x90)
            self._write_reg(self.REG_PAYLOADLENGTH, 66)
            self._write_reg(self.REG_FIFOTHRESH, 0x8F)
            self._write_reg(self.REG_PACKETCONFIG2, 0x02)

            # DIO mapping not used, but keep TX PacketSent default
            self._write_reg(self.REG_DIOMAPPING1, 0x00)

            version = self._read_reg(self.REG_VERSION)
            if version != self.EXPECTED_VERSION:
                raise OSError("rfm bad version 0x{:02X}".format(version))

            self._set_mode(self.MODE_RX)

            self.ok = True
            self.last_error = None

        except Exception as e:
            self.ok = False
            self.last_error = str(e)

    # -------------------------
    # Public
    # -------------------------
    def reconnect(self):
        self.ok = False
        self.last_error = None
        self._init_radio()
        return self.ok

    def debug_status(self):
        try:
            version = self._read_reg(self.REG_VERSION)
            opmode = self._read_reg(self.REG_OPMODE)
            irq1 = self._read_reg(self.REG_IRQFLAGS1)
            irq2 = self._read_reg(self.REG_IRQFLAGS2)
            return {
                "ok": True,
                "version": version,
                "opmode": opmode,
                "irq1": irq1,
                "irq2": irq2,
                "version_ok": version == self.EXPECTED_VERSION,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }

    def send_line(self, text):
        try:
            if not self.ok:
                if not self.reconnect():
                    return False

            payload = text.encode("utf-8")

            if len(payload) > 60:
                payload = payload[:60]

            self._set_mode(self.MODE_STDBY)

            # Clear IRQ flags by reading
            _ = self._read_reg(self.REG_IRQFLAGS1)
            _ = self._read_reg(self.REG_IRQFLAGS2)

            # First byte = payload length
            self._burst_write(self.REG_FIFO, bytes([len(payload)]) + payload)

            self._set_mode(self.MODE_TX)

            # Poll PacketSent: IRQFLAGS2 bit 3
            start = utime.ticks_ms()
            while True:
                irq2 = self._read_reg(self.REG_IRQFLAGS2)

                if irq2 & 0x08:
                    break

                if utime.ticks_diff(utime.ticks_ms(), start) > 500:
                    raise OSError("rfm tx timeout")

                utime.sleep_ms(5)

            self._set_mode(self.MODE_STDBY)

            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            try:
                self._set_mode(self.MODE_STDBY)
            except Exception:
                pass
            return False

    def receive_line(self, timeout_ms=0):
        try:
            if not self.ok:
                if not self.reconnect():
                    return None

            version = self._read_reg(self.REG_VERSION)
            if version != self.EXPECTED_VERSION:
                raise OSError("rfm bad version 0x{:02X}".format(version))

            self._set_mode(self.MODE_RX)

            start = utime.ticks_ms()
            while True:
                irq2 = self._read_reg(self.REG_IRQFLAGS2)

                # PayloadReady
                if irq2 & 0x04:
                    length = self._read_reg(self.REG_FIFO)

                    if length <= 0 or length > 60:
                        self.last_error = "rfm invalid packet length {}".format(length)
                        self._clear_fifo()
                        return None

                    payload = self._burst_read(self.REG_FIFO, length)
                    text = payload.decode("utf-8")

                    self.ok = True
                    self.last_error = None
                    return text

                if timeout_ms == 0:
                    self.ok = True
                    self.last_error = None
                    return None

                if utime.ticks_diff(utime.ticks_ms(), start) > timeout_ms:
                    self.ok = True
                    self.last_error = None
                    return None

                utime.sleep_ms(5)

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            try:
                self._set_mode(self.MODE_STDBY)
            except Exception:
                pass
            return None
