from machine import I2C, Pin
import time
import bme680

i2c = I2C(0, scl=Pin(1), sda=Pin(0))
bme = bme680.BME680_I2C(i2c, address=0x77)

while True:
    # Lecture des données
    
    # Affichage
    print("Température : {:.2f} °C".format(bme.temperature))
    print("Humidité    : {:.2f} %".format(bme.humidity))
    print("Pression    : {:.2f} hPa".format(bme.pressure))
    print("Gaz         : {} ohms".format(bme.gas_resistance))
    print("-----------------------")
    
    time.sleep(2)
