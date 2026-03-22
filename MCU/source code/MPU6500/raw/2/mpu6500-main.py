from machine import I2C
import time
import struct
import math

class MPU6500:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr

        if self.read_reg(0x75) != 0x70:
            raise RuntimeError("MPU6500 non détecté")

        # Réveil
        self.write_reg(0x6B, 0x00)
        time.sleep_ms(100)

        # Configuration
        self.write_reg(0x19, 0x07)  # Sample rate = 1kHz / (1+7) = 125 Hz
        self.write_reg(0x1A, 0x03)  # DLPF ~44 Hz
        self.write_reg(0x1B, 0x00)  # Gyro ±250 dps
        self.write_reg(0x1C, 0x00)  # Accel ±2g

    def write_reg(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def read_reg(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def read_accel_gyro(self):
        data = self.i2c.readfrom_mem(self.addr, 0x3B, 14)
        ax, ay, az, _, gx, gy, gz = struct.unpack(">hhhhhhh", data)
        return ax, ay, az, gx, gy, gz

    def calibrate(self, samples=500):
        print("Calibration... Ne pas bouger")
        gx_off = gy_off = gz_off = 0
        ax_off = ay_off = az_off = 0

        for _ in range(samples):
            ax, ay, az, gx, gy, gz = self.read_accel_gyro()
            gx_off += gx
            gy_off += gy
            gz_off += gz
            ax_off += ax
            ay_off += ay
            az_off += az - 16384  # 1g sur Z
            time.sleep_ms(5)

        self.gx_off = gx_off / samples
        self.gy_off = gy_off / samples
        self.gz_off = gz_off / samples
        self.ax_off = ax_off / samples
        self.ay_off = ay_off / samples
        self.az_off = az_off / samples

        print("Calibration OK")

    def read(self):
        ax, ay, az, gx, gy, gz = self.read_accel_gyro()
        ax -= self.ax_off
        ay -= self.ay_off
        az -= self.az_off
        gx -= self.gx_off
        gy -= self.gy_off
        gz -= self.gz_off
        return ax, ay, az, gx, gy, gz

######
    
from machine import I2C, Pin
import time

i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

imu = MPU6500(i2c)

"""while True:
    ax, ay, az, gx, gy, gz = imu.read_accel_gyro()
    print("ACC:", ax, ay, az, "GYRO:", gx, gy, gz)
    ax_g = ax / 16384
    ay_g = ay / 16384
    az_g = az / 16384
    print(ax_g, ay_g, az_g)
    gx_dps = gx / 131
    gy_dps = gy / 131
    gz_dps = gz / 131
    print(gx_dps,gy_dps,gz_dps)
    time.sleep(1)"""

pitch = 0.0
roll = 0.0
alpha = 0.98
dt = 0.01  # 100 Hz
dt=0.1

imu = MPU6500(i2c)
imu.calibrate()

while True:
    ax, ay, az, gx, gy, gz = imu.read()

    ax_g = ax / 16384
    ay_g = ay / 16384
    az_g = az / 16384

    pitch_acc = math.atan2(ay_g, math.sqrt(ax_g*ax_g + az_g*az_g)) * 57.3
    roll_acc  = math.atan2(-ax_g, az_g) * 57.3

    pitch += (gx / 131) * dt
    roll  += (gy / 131) * dt

    pitch = alpha * pitch + (1 - alpha) * pitch_acc
    roll  = alpha * roll  + (1 - alpha) * roll_acc

    print("Pitch:", pitch, "Roll:", roll)
    time.sleep(dt)
