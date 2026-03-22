from azbme680 import *
from machine import SoftI2C, Pin
import time

# === CONFIGURATION I2C ===
i2c = SoftI2C(scl=Pin(1), sda=Pin(0))
bme = BME680(i2c)

# === PRESSURE DE REFERENCE ===
bme.sealevel_pressure = 1010.0  # Ajuster selon ta localisation

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

# === BOUCLE PRINCIPALE ===
while True:
    # Mesure principale incluant le gaz
    bme.measure(gas=True)
    avg_gas = measure_gas_average(10)
    alt = bme.altitude(bme.pressure())
    print("* T,H,P,ALT,Gas moy:", 
          "{:.2f}°C".format(bme.temperature()), 
          "{:.2f}%".format(bme.humidity()), 
          "{:.2f} hPa".format(bme.pressure()), 
          "{:.1f} m".format(alt), 
          "{:.0f} ohms".format(avg_gas))
    
    # Mesures rapides sans gaz pour suivi
    for _ in range(10):
        bme.measure(gas=False)
        alt = bme.altitude(bme.pressure())
        print("- T,H,P,ALT:", 
              "{:.2f}°C".format(bme.temperature()), 
              "{:.2f}%".format(bme.humidity()), 
              "{:.2f} hPa".format(bme.pressure()), 
              "{:.1f} m".format(alt))
        time.sleep(1)
