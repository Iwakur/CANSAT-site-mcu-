from machine import Pin, I2C
import time

# Configuration I2C
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
MPU_ADDR = 0x68

# Registres
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B

# Réveil du MPU6500
i2c.writeto_mem(MPU_ADDR, PWR_MGMT_1, b'\x00')

def read_word(reg):
    data = i2c.readfrom_mem(MPU_ADDR, reg, 2)
    val = (data[0] << 8) | data[1]
    if val >= 0x8000:
        val = -((65535 - val) + 1)
    return val

while True:
    accel_x = read_word(ACCEL_XOUT_H)
    accel_y = read_word(ACCEL_XOUT_H + 2)
    accel_z = read_word(ACCEL_XOUT_H + 4)
    print(f"X: {accel_x}, Y: {accel_y}, Z: {accel_z}")
    time.sleep(0.1)