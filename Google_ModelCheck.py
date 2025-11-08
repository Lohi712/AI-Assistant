import os
import requests

API_KEY = os.getenv("GOOGLE_AI_API_KEY")
if not API_KEY:
    raise ValueError("Please set your GOOGLE_AI_API_KEY environment variable.")

url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": API_KEY,
}

data = {
    "contents": [
        {"parts": [{"text": "Hello Gemini 2.5! Tell me something interesting about AI."}]}
    ]
}

response = requests.post(url, headers=headers, json=data)

if response.status_code != 200:
    print("Error:", response.text)
else:
    result = response.json()
    print(result["candidates"][0]["content"]["parts"][0]["text"])
