from machine import I2C, Pin
import time

# Adresse I2C par défaut du BMP581
BMP581_I2C_ADDR = 0x47

# Initialisation de l'I2C sur le Pico (SDA=GP0, SCL=GP1)
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

# Fonction pour écrire un octet sur le BMP581
def write_reg(reg, data):
    i2c.writeto_mem(BMP581_I2C_ADDR, reg, bytes([data]))

# Fonction pour lire plusieurs octets
def read_regs(reg, n):
    return i2c.readfrom_mem(BMP581_I2C_ADDR, reg, n)

# Vérification de l'identité du capteur
chip_id = read_regs(0x00, 1)[0]
print("BMP581 Chip ID:", hex(chip_id))

# --- Initialisation du capteur ---
# Mode normal, température + pression
write_reg(0x1B, 0x01)  # Ex: configuration simple, mode normal
write_reg(0x1C, 0xF4)  # Oversampling max pour précision

time.sleep(0.1)

# Lecture de la pression et température (simplifié)
def read_temperature_pressure():
    # Lecture brute (3 octets pression + 3 octets température)
    data = read_regs(0x04, 6)
    
    # Conversion brute (simplifiée)
    press_raw = (data[0] << 16) | (data[1] << 8) | data[2]
    temp_raw = (data[3] << 16) | (data[4] << 8) | data[5]
    
    # Conversion approximative (pour un exemple rapide)
    temperature = temp_raw / 65536  # simplifié
    pressure = press_raw / 65536  # simplifié
    
    return temperature, pressure

# Boucle principale
while True:
    temp, pres = read_temperature_pressure()
    print("Température:", temp, "°C")
    print("Pression:", pres, "Pa")
    time.sleep(1)