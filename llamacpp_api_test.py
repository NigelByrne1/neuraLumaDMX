import requests

url = "http://127.0.0.1:8033/v1/chat/completions"

data = {
    "messages": [
        {
            "role": "user", 
            "content": "What is the capital of Ireland? just respond with the name"
        }
    ]
}

response = requests.post(url, json=data)

reply = response.json()["choices"][0]["message"]["content"]

print(reply)