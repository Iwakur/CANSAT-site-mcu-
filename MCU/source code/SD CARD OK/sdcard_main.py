from machine import Pin, SPI
import os
import sdcard



# Initialisation SPI
#spi = SPI(0,
#          baudrate=1_000_000,
#          polarity=0,
#          phase=0,
#          sck=Pin(18),
#          mosi=Pin(19),
#          miso=Pin(16))

# Initialisation SPI
#spi = SPI(1,
#          baudrate=1_000_000,
#          polarity=0,
#          phase=0,
#          sck=Pin(10),
#          mosi=Pin(11),
#          miso=Pin(12))
#cs = Pin(13, Pin.OUT)

#Initialisation SPI
spi = SPI(0,
          baudrate=1_000_000,
          polarity=0,
          phase=0,
          sck=Pin(2),
          mosi=Pin(3),
          miso=Pin(4))
cs = Pin(5, Pin.OUT)

# Initialisation carte SD
sd = sdcard.SDCard(spi, cs)

# Monter la carte SD
os.mount(sd, "/sd")


# LIRE LA CARTE SD

# Lister les fichiers
print("Contenu de la carte SD :")
print(os.listdir("/sd"))

#ECRASER SD
with open("/sd/starships.txt", "w") as f:
    f.write("Bonjour depuis le Raspberry Pi Pico !\n")


#AJOUTER SD
with open("/sd/starships.txt", "a") as f:
    f.write("Starships is the best")

#LIRE FICHIER
with open("/sd/starships.txt", "r") as f:
    print(f.read())