from machine import Pin, I2C

# Exemple avec I2C0
i2c = I2C(0, 
          scl=Pin(1),  # Broche SCL
          sda=Pin(0),  # Broche SDA
          freq=400000)  # Fréquence 400 kHz (optionnelle)

devices = i2c.scan()
if devices:
    print("Périphériques I2C trouvés :", [hex(d) for d in devices])
else:
    print("Aucun périphérique I2C trouvé")

    
address = 0x68   # Adresse du périphérique
num_bytes = 6    # Nombre d'octets à lire

raw_data = i2c.readfrom(address, num_bytes)
print("Données brutes :", raw_data)


reg = 0x3B  # Adresse du registre à lire
num_bytes = 6

# Envoyer l'adresse du registre et lire les données
i2c.writeto(address, bytes([reg]))
raw_data = i2c.readfrom(address, num_bytes)
print("Données du registre :", raw_data)

value = int.from_bytes(raw_data[4:6], "big", True)
print("Valeur :", value)