import serial
import requests

url = "http://127.0.0.1:8033/v1/chat/completions"
PORT = "COM3" 

user_prompt = input("Enter colour command: ") 

data = {
    "messages": [
        {  
            "role": "system", 
            "content": "You are a DMX controller. Only reply with four comma-separated integers in RGBW order: R,G,B,W. Example: red=255,0,0,0 blue=0,0,255,0 green=0,255,0,0 white=0,0,0,255"
        },
        {
            "role": "user", 
            "content": user_prompt
        }
    ]
}

response = requests.post(url, json=data)

reply = response.json()["choices"][0]["message"]["content"]

print(reply)

r, g, b, w = map(int, reply.split(","))


def build_packet(levels):
    payload = bytes([0]) + bytes(levels)
    length = len(payload)
    return bytes([0x7E,0x06,length & 0xFF,(length >> 8) & 0xFF]) + payload + bytes([0xE7])

dmx = [0] * 512
dmx[0] = r  
dmx[1] = g 
dmx[2] = b  
dmx[3] = w  

with serial.Serial(PORT, 57600) as ser:
    while True:
        packet = build_packet(dmx)
        ser.write(packet)