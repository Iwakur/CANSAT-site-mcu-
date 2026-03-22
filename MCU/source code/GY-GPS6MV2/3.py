from machine import UART, Pin
import time

uart1 = UART(0, baudrate=9600, tx=Pin(12), rx=Pin(13))

def nmea_to_deg(coord, direction):
    if not coord:
        return None
    deg = int(float(coord)/100)
    minutes = float(coord) - deg*100
    dec = deg + minutes/60
    if direction in ['S', 'W']:
        dec = -dec
    return dec

def read_line():
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

print("Lecture GPS enrichie ...")
last_alt = None
last_time = None

while True:
    nmea = read_line()

    # GPRMC: Date, Heure, Latitude, Longitude, vitesse, cap
    if nmea.startswith("$GPRMC"):
        parts = nmea.split(',')
        time_utc = parts[1]
        status = parts[2]
        lat = nmea_to_deg(parts[3], parts[4])
        lon = nmea_to_deg(parts[5], parts[6])
        speed_knots = float(parts[7]) if parts[7] else 0.0
        speed_kmh = speed_knots * 1.852
        course = float(parts[8]) if parts[8] else 0.0
        date = parts[9]

        print(f"Time UTC: {time_utc}, Date: {date}")
        print(f"Lat: {lat:.6f}, Lon: {lon:.6f}")
        print(f"Speed: {speed_kmh:.2f} km/h, Course: {course:.2f}°")

    # GPGGA: Altitude, Satellites, Fix quality
    elif nmea.startswith("$GPGGA"):
        parts = nmea.split(',')
        num_sats = int(parts[7]) if parts[7] else 0
        hdop = float(parts[8]) if parts[8] else 0.0
        altitude = float(parts[9]) if parts[9] else 0.0
        print(f"Altitude: {altitude:.1f} m, Satellites: {num_sats}, HDOP: {hdop}")

        # Calcul vitesse verticale approximative
        if last_alt is not None and last_time is not None:
            dt = time.time() - last_time
            vert_speed = (altitude - last_alt)/dt if dt>0 else 0
            print(f"Vitesse verticale approx: {vert_speed:.2f} m/s")
        last_alt = altitude
        last_time = time.time()

    # GPGSA: précision du fix
    elif nmea.startswith("$GPGSA"):
        parts = nmea.split(',')
        fix_mode = parts[2]   # 1=aucun,2=2D,3=3D
        pdop = float(parts[15]) if parts[15] else 0.0
        vdop = float(parts[16]) if parts[16] else 0.0
        print(f"Fix: {fix_mode}, PDOP: {pdop}, VDOP: {vdop}")
