import serial

PORT = "COM3" 

def build_packet(levels):
    payload = bytes([0]) + bytes(levels)
    length = len(payload)
    return bytes([0x7E,0x06,length & 0xFF,(length >> 8) & 0xFF]) + payload + bytes([0xE7])

dmx = [0] * 512
dmx[0] = 0  
dmx[1] = 0 
dmx[2] = 0  
dmx[3] = 0  

with serial.Serial(PORT, 57600) as ser:
    while True:
        packet = build_packet(dmx)
        ser.write(packet)