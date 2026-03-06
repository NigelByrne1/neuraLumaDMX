import requests

url = "http://127.0.0.1:8033/v1/chat/completions"
user_prompt = input("Enter colour command: ") 

data = {
    "messages": [
        {  
            "role": "system", 
            "content": " YOU ARE A DMX CONTROLLER ONLY REPLY WITH THE CORRECT COLOUR RGBW VALUES FOR THE REQUESTED COLOUR and have each value comma seperated, E.G. USER ASKS FOR RED YOUR RESPONSE IS 255,0,0,0 OR USER ASKS FOR BLUE YOUR RESPONSE IS 0,255,0,0"
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