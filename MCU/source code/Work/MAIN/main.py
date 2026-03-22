### Starships ###

# IMPORT
from machine import Pin, I2C
import neopixel
from micropython_bmpxxx import BMP581
from azbme680 import *
import time

#Led ARG
# Configuration
PIN_LED = 16      # GPIO utilisé
NB_LED = 1       # Nombre de LEDs

# Initialisation
np = neopixel.NeoPixel(Pin(PIN_LED), NB_LED)
np[0] = (20, 0, 0)	# Couleur BLEUE (R, G, B)
np.write()			# Envoi des données à la LED
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
        np[0] = (20, 0, 0)
        np.write()
        time.sleep(1)
        np[0] = (20,5, 0)
        np.write()
        time.sleep(1)
    else :
        print("\tBME580 not detected ! @", hex(104))
    if 104 in devices :
        print("\tMPU6500 Detected :", hex(104))
        np[0] = (20, 0, 0)
        np.write()
        time.sleep(1)
        np[0] = (20,5, 0)
        np.write()
        time.sleep(1)
    else :
        print("MPU6500 not detected ! @", hex(104))
    if 119 in devices :
        print("\tBME688 Detected :", hex(119))
        np[0] = (20, 0, 0)
        np.write()
        time.sleep(1)
        np[0] = (20,5, 0)
        np.write()
        time.sleep(1)
    else :
        print("\tBME688 not detected ! @", hex(119))
            
    if len(devices) == 3 :
        np[0] = (0, 20, 0)
    elif len(devices) < 3 :
        np[0] = (20, 5, 0)
    else :
        np[0] = (20, 0, 0)          
    #print("Périphériques I2C trouvés :", [hex(d) for d in devices])
else:
    print("Aucun périphérique I2C trouvé")
    np[0] = (20, 0, 0)
np.write()
time.sleep(1)

bmp = BMP581(i2c=i2c, address=0x47)
bmp.pressure_oversample_rate = bmp.OSR128
bmp.temperature_oversample_rate = bmp.OSR8
sea_level_pressure = bmp.sea_level_pressure
bmp.sea_level_pressure = 1016.0
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
# === CONFIGURATION I2C ===
bme = BME680(i2c)

# === PRESSURE DE REFERENCE ===
bme.sealevel_pressure = bmp.sea_level_pressure  # Ajuster selon ta localisation

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

def altitude(pressure, sea_level_p, c=44300):
    return c * (1 - (pressure / sea_level_p) ** 0.190284)

def cellText(longeur, text) :
    text = str((longeur-len(text))*" ")+text
    return text

while True :
    print("\n\tBMP580 :")
    pressure = bmp.pressure
    print(f"\t\tPression atm. = {pressure:.2f} hPa")
    temp = bmp.temperature
    print(f"\t\ttemperature = {temp:.2f} °C")

    # Pressure in hPA measured at sensor
    meters = bmp.altitude
    print(f"\t\tAltitude = {meters:.3f} mètres")
    feet = meters * 3.28084
    feet_only = int(feet)
    inches = (feet - feet_only) * 12




# Mesure principale incluant le gaz
    bme.measure(gas=False)
    #avg_gas = measure_gas_average(1)
    #alt = bme.altitude(bme.pressure())
    alt = altitude(bme.pressure(), sea_level_pressure)
    
    print("\n\tBME688 :")
    print("\t\tPression atm. : ", bme.pressure(),"hPa")
    print("\t\tTemperature : ", bme.temperature(),"°C")
    print("\t\tHumidité : ", bme.humidity(),"%")
    print("\t\tAltitude : ", alt,"mètres")
    #print("\t\tGaz : ", avg_gas,"Ohms")   


    #RECAP
    print("╔════════════╤════════════════════╤═════════════╤════════════╤══════════╤══════════╤═══════════╤════════════╤═══╗")
    print("║            │       Datetime     │ Température │ Pres. Atm. │ Humidité │ Altitude │ Lat, Long │ gY, gX, gZ │   ║")
    print("╟────────────┼────────────────────┼─────────────┼────────────┼──────────┼──────────┼───────────┼────────────┼───╢")
    print("║ RTC        │          -         │          °C │        hPa │        % │       m. │     -     │      -     │   ║")
    print("║ BMP580     │          -         │ ",round(temp,2)," °C │        hPa │        % │       m. │     -     │      -     │   ║")
    print("║ BME688     │          -         │          °C │        hPa │        % │       m. │     -     │      -     │   ║")
    print("║ TMP36      │          -         │          °C │     -      │    -     │    -     │     -     │      -     │   ║")
    print("║ MPU6500    │          -         │      -      │     -      │    -     │    -     │     -     │            │   ║")
    print("║ GY-NEO6MV2 │          -         │      -      │     -      │    -     │       m. │     -     │      -     │   ║")
    print("╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════════╝")
    time.sleep(1)
