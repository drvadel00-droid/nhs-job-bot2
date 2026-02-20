import requests

BOT_TOKEN = "your_bot_token_here"
CHAT_ID = "-1003888963521"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {"chat_id": CHAT_ID, "text": "✅ Test message from NHS Job Bot"}
r = requests.post(url, data=payload)
print(r.status_code, r.text)
