from machine import UART, Pin
import time

# UART1 : RX=GPIO13, TX=GPIO12 (TX non utilisé pour le GPS)
uart1 = UART(0, baudrate=9600, tx=Pin(12), rx=Pin(13))

# ---------- Fonctions utilitaires ----------
def nmea_to_deg(coord, direction):
    """
    Convertit NMEA format (ddmm.mmmm) en degrés décimaux
    direction = 'N', 'S', 'E', 'W'
    """
    if not coord:
        return None
    deg = int(float(coord)/100)
    minutes = float(coord) - deg*100
    dec = deg + minutes/60
    if direction in ['S', 'W']:
        dec = -dec
    return dec

def read_line():
    """Lit une ligne NMEA depuis le GPS"""
    line = b""
    while True:
        if uart1.any():
            c = uart1.read(1)
            if c:
                line += c
                if c == b'\n':
                    return line.decode('utf-8').strip()
        else:
            time.sleep_ms(1)

# ---------- Main ----------
print("Lecture GPS ...")
while True:
    nmea = read_line()
    
    # GPRMC = Date, Heure, Vitesse horizontale, cap
    if nmea.startswith("$GPRMC"):
        try:
            parts = nmea.split(',')
            time_utc = parts[1]          # hhmmss.sss
            status = parts[2]            # A=ok, V=invalid
            lat = nmea_to_deg(parts[3], parts[4])
            lon = nmea_to_deg(parts[5], parts[6])
            speed_knots = float(parts[7]) if parts[7] else 0.0
            speed_kmh = speed_knots * 1.852
            course = float(parts[8]) if parts[8] else 0.0
            date = parts[9]              # ddmmyy
            
            print(f"Time UTC: {time_utc}, Date: {date}")
            print(f"Lat: {lat:.6f}, Lon: {lon:.6f}")
            print(f"Speed: {speed_kmh:.2f} km/h, Course: {course:.2f}°")
        except Exception as e:
            pass
    
    # GPGGA = Altitude
    elif nmea.startswith("$GPGGA"):
        try:
            parts = nmea.split(',')
            altitude = float(parts[9]) if parts[9] else 0.0
            print(f"Altitude: {altitude:.1f} m")
        except Exception as e:
            pass