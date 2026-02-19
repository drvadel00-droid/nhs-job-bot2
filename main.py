import requests
from bs4 import BeautifulSoup
import time
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

KEYWORDS = ["doctor", "surgery", "emergency", "clinical", "trust", "specialty"]

URLS = [
    "https://www.healthjobsuk.com/job_list?JobSearch_d=534",
    "https://jobs.hscni.net/Search?SearchCatID=63"
]

sent_jobs = set()


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)


def check_jobs():
    for url in URLS:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            links = soup.find_all("a")

            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href")

                if not title or not href:
                    continue

                title_lower = title.lower()

                # Ignore consultants
                if "consultant" in title_lower:
                    continue

                # Match keywords
                if any(word in title_lower for word in KEYWORDS):

                    full_link = href if href.startswith("http") else url.split("/")[0] + "//" + url.split("/")[2] + href

                    if full_link not in sent_jobs:
                        sent_jobs.add(full_link)

                        message = f"New Job Found:\n{title}\n{full_link}"
                        send_telegram(message)
                        print("Sent:", title)

        except Exception as e:
            print("Error fetching:", url, e)


if __name__ == "__main__":
    print("Bot started. Monitoring jobs...")

    while True:
        check_jobs()
        time.sleep(300)  # Check every 5 minutes
