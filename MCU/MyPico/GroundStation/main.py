from rfm69 import RFM69
import utime

rfm = RFM69(
    sck_pin=3,
    mosi_pin=2,
    miso_pin=4,
    cs_pin=14,
    rst_pin=None,
    frequency_mhz=434.0,
    bitrate=4800,
    tx_power_dbm=13
)

print("Receiver ready")
print("OK:", rfm.ok)
print("Error:", rfm.last_error)
print("Debug:", rfm.debug_status())

while True:
    msg = rfm.receive_line(timeout_ms=500)
    if msg is not None:
        print("Received:", msg)
    utime.sleep_ms(100)