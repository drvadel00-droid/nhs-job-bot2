import os
import requests

print("Bot started successfully.")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

print("BOT_TOKEN:", BOT_TOKEN)
print("CHAT_ID:", CHAT_ID)

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Environment variables missing!")

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
data = {
    "chat_id": CHAT_ID,
    "text": "🚀 Railway is successfully connected to Telegram!"
}

response = requests.post(url, data=data)
print(response.text)
