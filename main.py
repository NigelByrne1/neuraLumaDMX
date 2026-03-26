import json
import serial
import time
import requests

interface_port = "COM3"
interface_baudrate = 57600
 
llm_port = "8033"
llm_url = "http://127.0.0.1:" + llm_port + "/v1/chat/completions"

llm_system_prompt1 = """
You are a lighting designer.

The user will describe a mood, theme, event, flag, holiday, scene, or visual idea.
Your job is to choose the best 4 colours for 4 lighting fixtures.

Interpret the user's request creatively and output exactly 4 colour names in order, separated by commas.

The 4 colours should form a sensible lighting palette across 4 fixtures.
You may repeat colours if that makes sense for the theme.
The 4 fixtures are lined up in a straight line so it might make sense to pattern the colours rather than have 4 unique colours, example colour 1, colour 2, colour 1, colour 2. this is not always the case though please decide what the best approach is depending on the users request. 
If using a pattern like just mentioned make sure to pattern the 2 most significant colours that match the users request

Rules:
- Output exactly 4 colour names
- Separate them with commas
- Do not explain anything
- Do not output RGB or JSON
- Only output the 4 colour names

Guidance:
- For moods like calm, peaceful, cold, or ocean, choose soft cool colours such as blue, cyan, teal, aqua, or soft green
- For holidays or themes like christmas, choose an appropriate repeated palette such as red, green, red, green
- For flags or national colours, choose colours that best represent the flag or theme across 4 fixtures
- For requests like St Patrick's Day or Irish colours, prefer green, white, orange, green
- For requests like Thailand flag, prefer red, white, blue, red
- For police lights, alternate red and blue
- For sunset or warm moods, choose warm colours such as amber, orange, pink, and warm white
- Sometimes the user will just say one colour eg blue, output would be blue,blue,blue,blue it does not always have to be a pallete but it should always be accurate
- If the request is unclear, choose a sensible palette that best matches the theme

Examples:

blue:
blue, blue, blue, blue

calm colours
blue, cyan, teal, soft green

irish flag
green, white, orange, green

St Patrick's Day
green, white, orange, green

thailand flag
red, white, blue, red

christmas colours
red, green, red, green

american police
red, blue, red, blue

sunset
orange, amber, pink, warm white
""".strip()


llm_system_prompt2 = """
You are a DMX lighting controller.

Convert colour names into RGBW values.

Output JSON only.

Format:
[
  {"r":0,"g":0,"b":0,"w":0},
  {"r":0,"g":0,"b":0,"w":0},
  {"r":0,"g":0,"b":0,"w":0},
  {"r":0,"g":0,"b":0,"w":0}
]

Each value must be 0-255.

Do not include explanation.

Example input:
red, green, blue, white

Example output:
[
  {"r":255,"g":0,"b":0,"w":0},
  {"r":0,"g":255,"b":0,"w":0},
  {"r":0,"g":0,"b":255,"w":0},
  {"r":0,"g":0,"b":0,"w":255}
]
""".strip()

def ask_llm_1(user_prompt):
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

def ask_llm_2(user_prompt):
    data = {
        "messages": [
            {  
                "role": "system", 
                "content": llm_system_prompt2
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

def parse_json_output(reply):
    default_output = [(255, 160, 60, 255)] *4

    try:
        data = json.loads(reply)

        if len(data) != 4:
            print ("LLM Error: 4 fixture values required, using default")
            return default_output
        
        result = []
        i = 1

        for f in data:
            try:
                r = int(f["r"])
                g = int(f["g"])
                b = int(f["b"])
                w = int(f["w"])  
            except:
                print("Error with fixture no.", i, ": missing or invalid keys, using default")
                return default_output

            for value in (r, g, b, w):
                if value < 0 or value > 255:
                    print("Error with fixture no.", i, ": LLM output contains value out of range 0-255, using default")
                    return default_output
                
            result.append((r,g,b,w))
            i += 1   

        return result
  
    except ValueError:
        print("Error: incorrect JSON format from llama.cpp, using default ")
        return default_output


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

        colour_reply = ask_llm_1(user_prompt)
        print("Colour reply:", colour_reply)

        if colour_reply is None:
            continue

        json_reply = ask_llm_2(colour_reply)
        print("JSON reply:", json_reply)

        if json_reply is None:
            continue

        fixtures = parse_json_output(json_reply)

        print(fixtures)

        dmx = [0] * 512
        start_channels = [1, 5, 9, 13]

        i = 0
        for r, g, b, w in fixtures:
            set_rgbw_fixture(dmx, start_channels[i], r, g, b, w)
            i += 1

        send_dmx_universe(dmx)

    
if __name__ == "__main__":
    print ("~~ neuraLumaDMX - type *exit* to exit ~~" ) 
    main()