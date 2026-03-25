import serial
import requests

interface_port = "COM3"
interface_baudrate = 57600
 
llm_port = "8033"
llm_url = "http://127.0.0.1:" + llm_port + "/v1/chat/completions"

llm_system_prompt1 = """
                    You are a DMX lighting controller.

                    Interpret the user's natural language request and convert it into RGBW values for 4 lighting fixtures.

                    Each fixture has 4 channels: Red, Green, Blue, White (0-255).

                    Only reply with JSON.
                    Do not reply with any explanation or extra text.

                    Output format:
                    [
                    {"r": 0, "g": 0, "b": 0, "w": 0},
                    {"r": 0, "g": 0, "b": 0, "w": 0},
                    {"r": 0, "g": 0, "b": 0, "w": 0},
                    {"r": 0, "g": 0, "b": 0, "w": 0}
                    ]

                    Rules:
                    - Output exactly 4 objects in the array
                    - Each object must contain r, g, b, w
                    - Each value must be an integer from 0 to 255
                    - No markdown
                    - No backticks
                    - No labels
                    - No explanation

                    Example:
                    [
                    {"r":255,"g":0,"b":0,"w":0},
                    {"r":0,"g":255,"b":0,"w":0},
                    {"r":0,"g":0,"b":255,"w":0},
                    {"r":0,"g":0,"b":0,"w":255}
                    ]
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


def parse_multi_output(reply):
    default_output = [(255, 160, 60, 255)] *4

    try:
        fixtures = reply.split(";")

        if len(fixtures) != 4:
            print ("LLM Error: 4 fixture values required, using default")
            return default_output
        
        result = []
        i = 1

        for f in fixtures:
            parts = f.split(",")

            if len(parts) != 4:
                print("Error with fixture no.", i, ": LLM output must contain exactly 4 values, using default")
                return default_output    

            r, g, b, w = map(int, parts)

            for value in (r, g, b, w):
                if value < 0 or value > 255:
                    print("Error with fixture no.", i, ": LLM output contains value out of range 0-255, using default")
                    return default_output
                
            result.append((r,g,b,w))
            i += 1   

        return result
  
    except ValueError:
        print("Error: incorrect format from llama.cpp, using default ")
        return default_output

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
            print ("Exiting program....")
            blackout()
            return

        reply = ask_llm(user_prompt)
        print(reply)
        if reply is None:
            continue

        # r, g, b, w = parse_output(reply)
        fixtures = parse_multi_output(reply)

        print(fixtures)

        dmx = [0] * 512
        start_channels = [1, 5, 9, 13]

        i = 0
        for r, g, b, w in fixtures:
            set_rgbw_fixture(dmx, start_channels[i], r, g, b, w)
            i += 1

        send_dmx_universe(dmx)
        ##send_dmx(r, g, b, w)

    
if __name__ == "__main__":
    print ("~~ neuraLumaDMX - type *exit* to exit ~~" ) 
    main()