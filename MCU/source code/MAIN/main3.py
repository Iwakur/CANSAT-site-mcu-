### Starships ###

# IMPORT
from machine import Pin, I2C, ADC
import neopixel
from micropython_bmpxxx import BMP581
from azbme680 import *
import time
import struct
import math

sea_lvl_pressure = 1016.0

mpu_status = False
mpu_cal = False
mpu_a_g = "              │              "
mpu_g = "              │               │              "
mpu_pr = "              │               │              "

bmp_status = False
bmp_alt = "        "
bmp_temp = "         "
bmp_pres = "        "

bme_status = False
bme_alt = "        "
bme_temp = "         "
bme_pres = "        "
bme_hum = "          "

#Led ARG
# Configuration
PIN_LED = 16      # GPIO utilisé
NB_LED = 1       # Nombre de LEDs

# Initialisation
np = neopixel.NeoPixel(Pin(PIN_LED), NB_LED)
ns = neopixel.NeoPixel(Pin(8), 8)
np[0] = (10, 0, 0)	# Couleur BLEUE (R, G, B)
np.write()			# Envoi des données à la LED

ns[0] = (0, 0, 0)
ns.write()
time.sleep(1)

print("Starting MCU...")
print("Scan I²C devices...\n")

#I2C Scan
i2c = I2C(0, 
          scl=Pin(1),  # Broche SCL
          sda=Pin(0),  # Broche SDA
          freq=400000)  # Fréquence 400 kHz (optionnelle)

devices = i2c.scan()
if devices:
    if 71 in devices :
        print("\tBMP580 Detected :", hex(71))
        bmp_status = True
        np[0] = (10, 0, 0)
        np.write()
        time.sleep(1)
        np[0] = (20,5, 0)
        np.write()
        ns[0] = (0, 10, 0)
        time.sleep(1)
    else :
        print("\tBME580 not detected ! @", hex(104))
        bmp_status = False
        ns[0] = (10, 0, 0)
    ns.write()
    
    if 119 in devices :
        bme_status = True
        print("\tBME688 Detected :", hex(119))
        np[0] = (10, 0, 0)
        np.write()
        time.sleep(1)
        np[0] = (20,5, 0)
        np.write()
        ns[1] = (0, 10, 0)
        time.sleep(1)
    else :
        bme_status = False
        print("\tBME688 not detected ! @", hex(119))
        ns[1] = (10, 0, 0)
    ns.write()
    
    
    if 104 in devices :
        mpu_status = True
        print("\tMPU6500 Detected :", hex(104))
        np[0] = (10, 0, 0)
        np.write()
        time.sleep(1)
        np[0] = (20,5, 0)
        np.write()
        ns[2] = (0, 10, 0)
        time.sleep(1)
    else :
        mpu_status = False
        print("\tMPU6500 not detected ! @", hex(104))
        ns[2] = (10, 0, 0)
    ns.write()
    
    if len(devices) == 3 :
        np[0] = (0, 10, 0)
    elif len(devices) < 3 :
        np[0] = (10, 10, 0)
    else :
        np[0] = (10, 0, 0)          
    #print("Périphériques I2C trouvés :", [hex(d) for d in devices])
else:
    print("Aucun périphérique I2C trouvé")
    np[0] = (10, 0, 0)
np.write()
time.sleep(1)

if bmp_status :
    bmp = BMP581(i2c=i2c, address=0x47)
    bmp.pressure_oversample_rate = bmp.OSR128
    bmp.temperature_oversample_rate = bmp.OSR8
    sea_level_pressure = bmp.sea_level_pressure
    bmp.sea_level_pressure = sea_lvl_pressure
    bmp.altitude = 111.0
    bmp.config
    bmp.iir_coefficient = bmp.COEF_0
    sea_level_pressure = bmp.sea_level_pressure

    print("\n\nCheck value :\n")
    print("\tBMP580 :")
    pressure = bmp.pressure
    print(f"\t\tSensor pressure = {pressure:.2f} hPa")
    temp = bmp.temperature
    print(f"\t\ttemp = {temp:.2f} C")

    # Pressure in hPA measured at sensor
    meters = bmp.altitude
    print(f"\t\tAltitude = {meters:.3f} meters")
    feet = meters * 3.28084
    feet_only = int(feet)
    inches = (feet - feet_only) * 12


#BME688
if bme_status :
    bme = BME680(i2c)
    bme.sealevel_pressure = sea_lvl_pressure

# === FONCTION POUR MESURER LE GAZ STABLE AVEC MOYENNE ===
def measure_gas_average(samples=10):
    gas_values = []
    for _ in range(samples):
        bme.measure(gas=True)
        gas_dict = bme.gas()
        # Vérifie si le chauffage est stable
        if gas_dict.get('heat_stable', False):
            # Cherche la première valeur numérique dans le dict
            gas_val = None
            for v in gas_dict.values():
                if isinstance(v, (int, float)):
                    gas_val = v
                    break
            if gas_val is not None:
                gas_values.append(gas_val)
        time.sleep(0.2)
    return sum(gas_values)/len(gas_values) if gas_values else 0

#MPU-6500
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

def altitude(pressure, sea_level_p, c=44300):
    return c * (1 - (pressure / sea_level_p) ** 0.190284)

def cellText(longeur, text) :
    text = str((longeur-len(str(text)))*" ")+str(text)
    return text

def boolToStr(value) :
    if value :
        return "   OK  "
    return "  ERROR"

if mpu_status :
    imu = MPU6500(i2c)
    pitch = 0.0
    roll = 0.0
    alpha = 0.98
    dt = 0.01  # 100 Hz
    dt=0.1

    imu = MPU6500(i2c)
    imu.calibrate()
    mpu_cal = True


#adc
adc = ADC(26)  # GPIO26 = ADC0

VREF = 3.3
ADC_MAX = 65535

def read_temp():
    raw = adc.read_u16()
    voltage = raw * VREF / ADC_MAX
    temperature = (voltage - 0.5) * 100
    return temperature



while True :
    
    ns[0] = (10, 10, 0)
    ns.write()
    time.sleep(0.1)
    
    try:
        data = i2c.readfrom_mem(0x47, 0x75, 1)
        if not bmp_status :
            bmp = BMP581(i2c=i2c, address=0x47)
            bmp.pressure_oversample_rate = bmp.OSR128
            bmp.temperature_oversample_rate = bmp.OSR8
            sea_level_pressure = bmp.sea_level_pressure
            bmp.sea_level_pressure = sea_lvl_pressure
            bmp.altitude = 111.0
            bmp.config
            bmp.iir_coefficient = bmp.COEF_0
            sea_level_pressure = bmp.sea_level_pressure
        bmp_status = True
    except OSError:
        bmp_status = False
    
    if bmp_status :
        bmp_pres = cellText(8,round(bmp.pressure,2))
        bmp_temp = cellText(9,round(bmp.temperature,2))
        bmp_alt = cellText(8,round(bmp.altitude,2))
        ns[0] = (0, 10, 0)
    else :
        ns[0] = (10, 0, 0)
    ns.write()
    time.sleep(0.1)


# Mesure principale incluant le gaz
    ns[1] = (10, 10, 0)
    ns.write()
    time.sleep(0.1)
    try:
        data = i2c.readfrom_mem(0x77, 0x75, 1)
        if not bme_status :           
            bme = BME680(i2c)
            bme.sealevel_pressure = bmp.sea_level_pressure
        bme_status = True
        ns[1] = (0, 10, 0)
    except OSError:
        bme_status = False
        ns[1] = (10, 0, 0)
    
    if bme_status :
        bme.measure(gas=False)
        #avg_gas = measure_gas_average(1)
        #alt2 = bme.altitude(bme.pressure())
        #print(alt2)
        bme_alt = cellText(8,round(altitude(bme.pressure(), sea_lvl_pressure),2))
        bme_pres = cellText(8,round(bme.pressure(),2))
        bme_temp = cellText(9,round(bme.temperature(),2))
        bme_hum = cellText(10,round(bme.humidity(),2))
    ns.write()
    time.sleep(0.1)
    #print("\t\tGaz : ", avg_gas,"Ohms")
    
    
    #MPU-6500
    ns[2] = (10, 10, 0)
    ns.write()
    time.sleep(0.1)
    try:
        data = i2c.readfrom_mem(0x68, 0x75, 1)
        if not mpu_cal :
            imu = MPU6500(i2c)
            pitch = 0.0
            roll = 0.0
            alpha = 0.98
            dt = 0.01  # 100 Hz
            dt=0.1

            imu = MPU6500(i2c)
            imu.calibrate()
            mpu_cal = True
        mpu_status = True
    except OSError:
        mpu_status = False
    
    if mpu_status :
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
        
        
        mpu_a_g = cellText(29,str(round(ax_g,6))+","+str(round(ay_g,6))+","+str(round(az_g,6)))
        mpu_g = cellText(45,str(round(gx,6))+","+str(round(gy,6))+","+str(round(gz,6)))
        
        mpu_pr = cellText(45,str(round(pitch,12))+" / "+str(round(roll,12)))
        ns[2] = (0, 10, 0)
    else :
        ns[2] = (10, 0, 0)
    ns.write()
    time.sleep(0.1)
    
    if bmp_status and bme_status and mpu_status :
        np[0] = (0, 10, 0)
    elif not bmp_status and not bme_status and not mpu_status :
        np[0] = (10, 0, 0)
    else :
        np[0] = (10, 10, 0)
    np.write()
    
    #tmp36
    tmp36 = read_temp()
    tmp36 = cellText(6,round(tmp36, 2));
    #RECAP
    
    print("╔═════════════╤════════════════╤═══════════════╤═══════════════╤═══════════════╤═══════════════╤════════════════╗")
    print("║             │      RTC       │    BMP580     │    BME688     │      TMP36    │    MPU-6500   │   GY-NEO6MV2   ║")
    print("╟─────────────┼────────────────┼───────────────┼───────────────┼───────────────┼───────────────┼────────────────╢")
    print("║ Datetime    │ 00/00 00:00:00 │               │               │               │               │ 00/00 00:00:00 ║")
    print("║ Temperature │                │ ",bmp_temp,"°C │ ",bme_temp,"°C │    ",tmp36,"°C │               │                ║")
    print("║ Press. atm. │                │ ",bmp_pres,"hPa │ ",bme_pres,"hPa │               │               │                ║")
    print("║ Press. alt. │                │  ",bmp_alt,"m. │  ",bme_alt,"m. │               │               │                ║")
    print("║ Humidité    │                │               │ ",bme_hum,"% │               │               │                ║")
    print("║ Force-G     │                │               │               │",mpu_a_g,"│                ║")
    print("║ Gyroscope   │                │               │",mpu_g,"│                ║")
    print("║ Pitch  Roll │                │               │",mpu_pr,"│                ║")
    print("║ Latitude    │                │               │               │               │               │             ?° ║")
    print("║ Longitude   │                │               │               │               │               │             ?° ║")
    print("║ Boussole    │                │               │               │               │               │             ?° ║")
    print("║ Vitesse     │                │               │               │               │               │         ? km/h ║")
    print("║ Satellites  │                │               │               │               │               │      ? nb sat. ║")
    print("║ Status      │        ?       │  ",boolToStr(bmp_status),"    │  ",boolToStr(bme_status),"    │       ?       │  ",boolToStr(mpu_status),"    │        ?       ║")
    print("╚═════════════╧════════════════╧═══════════════╧═══════════════╧═══════════════╧═══════════════╧════════════════╝")
    
    time.sleep(0.1)