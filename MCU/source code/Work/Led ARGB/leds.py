from machine import Pin
import neopixel
import time

# Configuration
PIN_LED = 16      # GPIO utilisé
NB_LED = 1       # Nombre de LEDs

# Initialisation
np = neopixel.NeoPixel(Pin(PIN_LED), NB_LED)

while True :
    # Couleur BLEUE (R, G, B)
    np[0] = (0, 0, 20)

    # Envoi des données à la LED
    np.write()
    
    time.sleep(1)

    # Couleur BLEUE (R, G, B)
    np[0] = (0, 20, 0)

    # Envoi des données à la LED
    np.write()
    
    time.sleep(1)
