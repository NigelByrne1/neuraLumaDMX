import serial
import requests

interface_port = "COM3"
interface_baudrate = 57600
 
llm_port = "8033"
llm_url = "http://127.0.0.1:" + llm_port + "/v1/chat/completions"

llm_system_prompt1 = """
                    You are a DMX controller. Use the users prompt to interpret natural language and out put it to dmx commands
                    Only reply with four comma-separated integers in order of channels:
                    Each integer representing a dmx value from 0-255 and in order
                    e.g. desired output values for dmx channel red 1 = 0, channel 2 green = 123, channel 3 blue = 222, channel 4 white = 12
                    then you would only reply with 0,123,222,12
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
    r, g, b, w = map(int, reply.split(","))
    return r, g, b, w

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

    with serial.Serial(interface_port, interface_baudrate) as ser:
        packet = build_packet(dmx)
        ser.write(packet)

def main(): 
    user_prompt = input("Enter colour command: ")
    reply = ask_llm(user_prompt)

    if reply is None:
        main()
        return

    print("LLM reply:", reply)

    r, g, b, w = parse_output(reply)
    send_dmx(r, g, b, w,)

    main()

main()