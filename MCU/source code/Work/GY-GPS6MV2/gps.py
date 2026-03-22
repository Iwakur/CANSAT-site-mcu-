from machine import Pin
import rp2
import time

BAUD = 4800
BIT_CYCLES = 8
FREQ = BAUD * BIT_CYCLES

# ---------- TX ----------
@rp2.asm_pio(
    out_init=rp2.PIO.OUT_HIGH,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT
)
def uart_tx():
    pull()
    set(pins, 0)      [7]   # start bit
    label("bitloop")
    out(pins, 1)      [7]
    jmp(not_osre, "bitloop")
    set(pins, 1)      [7]   # stop bit

# ---------- RX ----------
@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_RIGHT
)
def uart_rx():
    wait(0, pin, 0)        # wait start bit
    set(x, 7)         [10]
    label("rxloop")
    in_(pins, 1)
    jmp(x_dec, "rxloop")
    push()

# ---------- State machines ----------
tx_sm = rp2.StateMachine(
    0, uart_tx,
    freq=FREQ,
    out_base=Pin(7)
)

rx_sm = rp2.StateMachine(
    1, uart_rx,
    freq=FREQ,
    in_base=Pin(6)
)

tx_sm.active(1)
rx_sm.active(1)

# ---------- Fonctions haut niveau ----------
def softserial_write(data):
    for c in data:
        tx_sm.put(c)

def softserial_read():
    if rx_sm.rx_fifo():
        return rx_sm.get() & 0xFF
    return None

# ---------- Test ----------
softserial_write(b"UART PIO OK\r\n")

while True:
    b = softserial_read()
    if b is not None:
        print("Reçu:", chr(b))
        softserial_write(bytes([b]))  # echo
    time.sleep(1)
