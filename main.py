import serial
import requests

interface_port = "COM3"
interface_baudrate = 57600
 
llm_port = "8033"
llm_url = "http://127.0.0.1:" + llm_port + "/v1/chat/completions"

llm_system_prompt1 = """
                    You are a DMX controller. Use the users prompt to interpret natural language and out put it to dmx commands
                    Only reply with four comma-separated integers in order of channels:
                    Each integer representing a RGBW dmx value from 0-255 and in order
                    e.g. desired output values for dmx channel red 1 = 0, channel 2 green = 123, channel 3 blue = 222, channel 4 white = 12
                    then you would only reply with 0,123,222,12
                    some examples of colours red = 255,0,0,0 white = 0,0,0,255 warm white 255,160,60,255
                    """.strip()


def ask_llm(user_prompt):
    data = {
        "messages": [
            {  
                "role": "system", 
                "content": llm_system_prompt1
            },
            {
                "role": "user", 
                "content": user_prompt
            }
        ]
    }
    try:
        response = requests.post(llm_url, json=data, timeout=5)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]
        return reply
    except requests.exceptions.HTTPError as e:
        print("HTTP error occurred trying to reach llama.cpp:", e)
        return None
    except requests.exceptions.RequestException as e:
        print("A request error occurred trying to reach llama.cpp:", e)
        return None

def parse_output(reply):
    default_output = (255, 160, 60, 255)

    try:
        parts = reply.split(",")

        if len(parts) != 4:
            print("Error: LLM output must contain exactly 4 values, using default")
            return default_output    

        r, g, b, w = map(int, parts)

        for value in (r, g, b, w):
            if value < 0 or value > 255:
                print("Error: LLM output contains value out of range 0-255, using default")
                return default_output

        return r, g, b, w

    except ValueError:
        print("Error: incorrect format from llama.cpp, using default ")
        return default_output

def build_packet(levels):
    payload = bytes([0]) + bytes(levels)
    length = len(payload)
    return bytes([0x7E,0x06,length & 0xFF,(length >> 8) & 0xFF]) + payload + bytes([0xE7])

def send_dmx(r, g, b, w):
    dmx = [0] * 512

    dmx[0] = r  
    dmx[1] = g 
    dmx[2] = b  
    dmx[3] = w  

    try:
        with serial.Serial(interface_port, interface_baudrate) as ser:
            packet = build_packet(dmx)
            ser.write(packet)
    except serial.SerialException as e:
        print ("Error: could not reach DMX interface: ", e)
    except serial.SerialTimeoutException as e:
        print ("Error: DMX write timeout: ", e)

def send_dmx_universe (dmx):
    try:
        with serial.Serial(interface_port, interface_baudrate) as ser:
            packet = build_packet(dmx)
            ser.write(packet)
    except serial.SerialException as e:
        print ("Error: could not reach DMX interface: ", e)
    except serial.SerialTimeoutException as e:
        print ("Error: DMX write timeout: ", e)

def set_rgbw_fixture(dmx, start_channel, r, g, b, w):
    dmx[start_channel - 1] = r
    dmx[start_channel] = g
    dmx[start_channel + 1] = b
    dmx[start_channel + 2] = w

def blackout():
    dmx = [0] * 512

    try:
        with serial.Serial(interface_port, interface_baudrate) as ser:
            packet = build_packet(dmx)
            ser.write(packet)
    except serial.SerialException as e:
        print ("Error: could not send blackout:", e)
    except serial.SerialTimeoutException as e:
        print ("Error: could not send blackout:", e)

def main():
    while True:
        user_prompt = input("Enter colour command: ")

        if user_prompt.lower() == "exit":
            print ("Exiting program..")
            blackout()
            return

        reply = ask_llm(user_prompt)

        if reply is None:
            continue

        r, g, b, w = parse_output(reply)
        
        print("LLM REPLY:", f"{r},{g},{b},{w}")

        dmx = [0] * 512
        set_rgbw_fixture(dmx, 1, r, g, b, w)
        set_rgbw_fixture(dmx, 5, r, g, b, w)
        set_rgbw_fixture(dmx, 9, r, g, b, w)
        set_rgbw_fixture(dmx, 13, r, g, b, w)
        
        send_dmx_universe(dmx)
        ##send_dmx(r, g, b, w)

    
if __name__ == "__main__":
    print ("~~ neuraLumaDMX - type *exit* to exit ~~" ) 
    main()