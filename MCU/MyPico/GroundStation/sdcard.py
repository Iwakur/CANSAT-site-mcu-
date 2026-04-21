"""
MicroPython driver for SD cards using SPI bus + simple logger.

Provides:
- SDCard: low-level SPI block device
- SDCardLogger: file appending for telemetry + logs
"""
from machine import Pin, SoftSPI
from micropython import const
import time
import os
import utime


_CMD_TIMEOUT = const(100)

_R1_IDLE_STATE = const(1 << 0)
_R1_ILLEGAL_COMMAND = const(1 << 2)
_TOKEN_CMD25 = const(0xFC)
_TOKEN_STOP_TRAN = const(0xFD)
_TOKEN_DATA = const(0xFE)


class SDCard:
    def __init__(self, spi, cs, baudrate=1320000):
        self.spi = spi
        self.cs = cs

        self.cmdbuf = bytearray(6)
        self.dummybuf = bytearray(512)
        self.tokenbuf = bytearray(1)

        for i in range(512):
            self.dummybuf[i] = 0xFF

        self.dummybuf_memoryview = memoryview(self.dummybuf)

        self.init_card(baudrate)

    def init_spi(self, baudrate):
        try:
            master = self.spi.MASTER
        except AttributeError:
            self.spi.init(baudrate=baudrate, phase=0, polarity=0)
        else:
            self.spi.init(master, baudrate=baudrate, phase=0, polarity=0)

    def init_card(self, baudrate):
        self.cs.init(self.cs.OUT, value=1)

        self.init_spi(100000)

        for _ in range(16):
            self.spi.write(b"\xff")

        for _ in range(5):
            if self.cmd(0, 0, 0x95) == _R1_IDLE_STATE:
                break
        else:
            raise OSError("no SD card")

        r = self.cmd(8, 0x01AA, 0x87, 4)
        if r == _R1_IDLE_STATE:
            self.init_card_v2()
        elif r == (_R1_IDLE_STATE | _R1_ILLEGAL_COMMAND):
            self.init_card_v1()
        else:
            raise OSError("couldn't determine SD card version")

        if self.cmd(9, 0, 0, 0, False) != 0:
            raise OSError("no response from SD card")

        csd = bytearray(16)
        self.readinto(csd)

        if csd[0] & 0xC0 == 0x40:
            self.sectors = ((csd[7] << 16 | csd[8] << 8 | csd[9]) + 1) * 1024
        elif csd[0] & 0xC0 == 0x00:
            c_size = (csd[6] & 0b11) << 10 | csd[7] << 2 | csd[8] >> 6
            c_size_mult = (csd[9] & 0b11) << 1 | csd[10] >> 7
            read_bl_len = csd[5] & 0b1111
            capacity = (c_size + 1) * (2 ** (c_size_mult + 2)) * (2 ** read_bl_len)
            self.sectors = capacity // 512
        else:
            raise OSError("SD card CSD format not supported")

        if self.cmd(16, 512, 0) != 0:
            raise OSError("can't set 512 block size")

        self.init_spi(baudrate)

    def init_card_v1(self):
        for _ in range(_CMD_TIMEOUT):
            time.sleep_ms(50)
            self.cmd(55, 0, 0)
            if self.cmd(41, 0, 0) == 0:
                self.cdv = 512
                return
        raise OSError("timeout waiting for v1 card")

    def init_card_v2(self):
        for _ in range(_CMD_TIMEOUT):
            time.sleep_ms(50)
            self.cmd(58, 0, 0, 4)
            self.cmd(55, 0, 0)
            if self.cmd(41, 0x40000000, 0) == 0:
                self.cmd(58, 0, 0, -4)
                ocr = self.tokenbuf[0]
                if not ocr & 0x40:
                    self.cdv = 512
                else:
                    self.cdv = 1
                return
        raise OSError("timeout waiting for v2 card")

    def cmd(self, cmd, arg, crc, final=0, release=True, skip1=False):
        self.cs(0)

        buf = self.cmdbuf
        buf[0] = 0x40 | cmd
        buf[1] = arg >> 24
        buf[2] = arg >> 16
        buf[3] = arg >> 8
        buf[4] = arg
        buf[5] = crc
        self.spi.write(buf)

        if skip1:
            self.spi.readinto(self.tokenbuf, 0xFF)

        for _ in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            response = self.tokenbuf[0]
            if not (response & 0x80):
                if final < 0:
                    self.spi.readinto(self.tokenbuf, 0xFF)
                    final = -1 - final
                for _ in range(final):
                    self.spi.write(b"\xff")
                if release:
                    self.cs(1)
                    self.spi.write(b"\xff")
                return response

        self.cs(1)
        self.spi.write(b"\xff")
        return -1

    def readinto(self, buf):
        self.cs(0)

        for _ in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == _TOKEN_DATA:
                break
            time.sleep_ms(1)
        else:
            self.cs(1)
            raise OSError("timeout waiting for response")

        mv = self.dummybuf_memoryview
        if len(buf) != len(mv):
            mv = mv[: len(buf)]
        self.spi.write_readinto(mv, buf)

        self.spi.write(b"\xff")
        self.spi.write(b"\xff")

        self.cs(1)
        self.spi.write(b"\xff")

    def write(self, token, buf):
        self.cs(0)

        self.spi.read(1, token)
        self.spi.write(buf)
        self.spi.write(b"\xff")
        self.spi.write(b"\xff")

        if (self.spi.read(1, 0xFF)[0] & 0x1F) != 0x05:
            self.cs(1)
            self.spi.write(b"\xff")
            return

        while self.spi.read(1, 0xFF)[0] == 0:
            pass

        self.cs(1)
        self.spi.write(b"\xff")

    def write_token(self, token):
        self.cs(0)
        self.spi.read(1, token)
        self.spi.write(b"\xff")

        while self.spi.read(1, 0xFF)[0] == 0x00:
            pass

        self.cs(1)
        self.spi.write(b"\xff")

    def readblocks(self, block_num, buf):
        self.spi.write(b"\xff")

        nblocks = len(buf) // 512
        assert nblocks and not len(buf) % 512, "Buffer length is invalid"

        if nblocks == 1:
            if self.cmd(17, block_num * self.cdv, 0, release=False) != 0:
                self.cs(1)
                raise OSError(5)
            self.readinto(buf)
        else:
            if self.cmd(18, block_num * self.cdv, 0, release=False) != 0:
                self.cs(1)
                raise OSError(5)

            offset = 0
            mv = memoryview(buf)
            while nblocks:
                self.readinto(mv[offset : offset + 512])
                offset += 512
                nblocks -= 1

            if self.cmd(12, 0, 0xFF, skip1=True):
                raise OSError(5)

    def writeblocks(self, block_num, buf):
        self.spi.write(b"\xff")

        nblocks, err = divmod(len(buf), 512)
        assert nblocks and not err, "Buffer length is invalid"

        if nblocks == 1:
            if self.cmd(24, block_num * self.cdv, 0) != 0:
                raise OSError(5)
            self.write(_TOKEN_DATA, buf)
        else:
            if self.cmd(25, block_num * self.cdv, 0) != 0:
                raise OSError(5)

            offset = 0
            mv = memoryview(buf)
            while nblocks:
                self.write(_TOKEN_CMD25, mv[offset : offset + 512])
                offset += 512
                nblocks -= 1

            self.write_token(_TOKEN_STOP_TRAN)

    def ioctl(self, op, arg):
        if op == 4:
            return self.sectors
        if op == 5:
            return 512


class SDCardLogger:
    def __init__(self, sd, mount_point="/sd", data_filename="data.txt", log_filename="logs.txt"):
        self.sd = sd
        self.mount_point = mount_point
        self.data_path = mount_point + "/" + data_filename
        self.log_path = mount_point + "/" + log_filename

        self.ok = False
        self.mounted = False
        self.last_error = None

        self._mount()

    def _mount(self):
        try:
            try:
                os.mount(self.sd, self.mount_point)
            except OSError:
                pass

            os.listdir(self.mount_point)

            self._ensure_file(self.data_path)
            self._ensure_file(self.log_path)

            self.ok = True
            self.mounted = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.mounted = False
            self.last_error = str(e)
            return False

    def reconnect(self):
        try:
            try:
                os.umount(self.mount_point)
            except Exception:
                pass

            utime.sleep_ms(100)
            return self._mount()

        except Exception as e:
            self.ok = False
            self.mounted = False
            self.last_error = str(e)
            return False

    def _ensure_file(self, path):
        with open(path, "a"):
            pass

    def _append_line(self, path, line):
        with open(path, "a") as f:
            f.write(line + "\n")

    def write_data(self, line):
        try:
            if not self.mounted:
                if not self.reconnect():
                    return False

            self._append_line(self.data_path, line)
            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.mounted = False
            self.last_error = str(e)
            return False

    def write_log(self, line):
        try:
            if not self.mounted:
                if not self.reconnect():
                    return False

            self._append_line(self.log_path, line)
            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.mounted = False
            self.last_error = str(e)
            return False
        
        
        
        
        
        
        
        
        
        
class SDModule:
    def __init__(
        self,
        sck_pin,
        mosi_pin,
        miso_pin,
        cs_pin,
        baudrate=500000,
        mount_point="/sd",
        data_filename="data.txt",
        log_filename="logs.txt"
    ):
        self.sck_pin = sck_pin
        self.mosi_pin = mosi_pin
        self.miso_pin = miso_pin
        self.cs_pin = cs_pin
        self.baudrate = baudrate
        self.mount_point = mount_point
        self.data_filename = data_filename
        self.log_filename = log_filename

        self.spi = None
        self.cs = None
        self.sd = None
        self.logger = None

        self.ok = False
        self.last_error = None

        self._init_all()

    def _init_all(self):
        try:
            self.spi = SoftSPI(
                baudrate=self.baudrate,
                polarity=0,
                phase=0,
                sck=Pin(self.sck_pin),
                mosi=Pin(self.mosi_pin),
                miso=Pin(self.miso_pin)
            )

            self.cs = Pin(self.cs_pin, Pin.OUT)

            self.sd = SDCard(self.spi, self.cs, baudrate=self.baudrate)
            self.logger = SDCardLogger(
                self.sd,
                mount_point=self.mount_point,
                data_filename=self.data_filename,
                log_filename=self.log_filename
            )

            self.ok = self.logger.ok
            self.last_error = None if self.ok else self.logger.last_error
            return self.ok

        except Exception as e:
            self.spi = None
            self.cs = None
            self.sd = None
            self.logger = None
            self.ok = False
            self.last_error = str(e)
            return False

    def reconnect(self):
        try:
            self.ok = False
            self.last_error = None

            # full rebuild from scratch
            return self._init_all()

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            return False

    def write_data(self, line):
        try:
            if self.logger is None:
                if not self.reconnect():
                    return False

            if not self.logger.write_data(line):
                self.ok = False
                self.last_error = self.logger.last_error
                self.logger = None
                self.sd = None
                return False

            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            self.logger = None
            self.sd = None
            return False

    def write_log(self, line):
        try:
            if self.logger is None:
                if not self.reconnect():
                    return False

            if not self.logger.write_log(line):
                self.ok = False
                self.last_error = self.logger.last_error
                self.logger = None
                self.sd = None
                return False

            self.ok = True
            self.last_error = None
            return True

        except Exception as e:
            self.ok = False
            self.last_error = str(e)
            self.logger = None
            self.sd = None
            return False
