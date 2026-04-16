import network
import socket

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="CANSAT")

while not ap.active():
    pass

print("AP started:", ap.ifconfig())

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)

while True:
    cl, addr = s.accept()
    print("Client connected")

    request = cl.recv(1024)

    response = """\
HTTP/1.1 200 OK

Hello from Pico W 🚀
"""

    cl.send(response)
    cl.close()