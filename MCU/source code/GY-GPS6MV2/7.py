from machine import UART, Pin
import time

# ---------- Config UART ----------
uart1 = UART(0, baudrate=9600, tx=Pin(12), rx=Pin(13))  # TX non utilisé

# ---------- Fonctions utilitaires ----------
def nmea_to_deg(coord, direction):
    """
    Convertit la coordonnée NMEA (ddmm.mmmm) en degrés décimaux
    direction = 'N', 'S', 'E', 'W'
    """
    if not coord or len(coord) < 3:
        return None
    deg = int(float(coord)/100)
    minutes = float(coord) - deg*100
    dec = deg + minutes/60
    if direction in ['S', 'W']:
        dec = -dec
    return dec

def read_line():
    """
    Lit une ligne NMEA depuis l'UART GPS
    """
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

# ---------- Variables pour vitesse verticale ----------
last_alt = None
last_time = None

# ---------- Lecture GPS ----------
print("Lecture GPS enrichie ...")
while True:
    nmea = read_line()
    if not nmea.startswith("$GP"):  # Ignore les lignes non GPS
        continue

    # ---------- GPRMC ----------
    if nmea.startswith("$GPRMC"):
        try:
            parts = nmea.split(',')
            if parts[2] != 'A':  # Statut A=ok, V=invalid
                continue
            time_utc = parts[1]
            date = parts[9]
            lat = nmea_to_deg(parts[3], parts[4])
            lon = nmea_to_deg(parts[5], parts[6])
            speed_knots = float(parts[7]) if parts[7] else 0.0
            speed_kmh = speed_knots * 1.852
            course = float(parts[8]) if parts[8] else 0.0

            print("------ GPRMC ------")
            print(f"Heure UTC: {time_utc}, Date: {date}")
            print(f"Latitude: {lat:.6f}, Longitude: {lon:.6f}")
            print(f"Vitesse horizontale: {speed_kmh:.2f} km/h, Cap: {course:.2f}°")
        except Exception:
            pass

    # ---------- GPGGA ----------
    elif nmea.startswith("$GPGGA"):
        try:
            parts = nmea.split(',')
            num_sats = int(parts[7]) if parts[7] else 0
            hdop = float(parts[8]) if parts[8] else 0.0
            altitude = float(parts[9]) if parts[9] else 0.0

            print("------ GPGGA ------")
            print(f"Altitude: {altitude:.1f} m, Satellites: {num_sats}, HDOP: {hdop}")

            # Calcul de la vitesse verticale approx
         
            if last_alt is not None and last_time is not None:
                dt = time.time() - last_time
                vert_speed = (altitude - last_alt)/dt if dt > 0 else 0
                print(f"Vitesse verticale approx: {vert_speed:.2f} m/s")
            last_alt = altitude
            last_time = time.time()
        except Exception:
            pass

    # ---------- GPGSA ----------
    elif nmea.startswith("$GPGSA"):
        try:
            parts = nmea.split(',')
            fix_mode = parts[2]   # 1=aucun, 2=2D, 3=3D
            pdop = float(parts[15]) if parts[15] else 0.0
            vdop = float(parts[16]) if parts[16] else 0.0
            print("------ GPGSA ------")
            print(f"Fix GPS: {fix_mode}, PDOP: {pdop}, VDOP: {vdop}")
        except Exception:
            pass

    # ---------- Optionnel : GPVTG pour vitesse cap true/magnetic ----------
    elif nmea.startswith("$GPVTG"):
        try:
            parts = nmea.split(',')
            true_course = float(parts[1]) if parts[1] else 0.0
            mag_course = float(parts[3]) if parts[3] else 0.0
            speed_kmh = float(parts[7]) if parts[7] else 0.0
            print("------ GPVTG ------")
            print(f"Cap vrai: {true_course}°, Cap magnétique: {mag_course}°, Vitesse: {speed_kmh} km/h")
        except Exception:
            pass
