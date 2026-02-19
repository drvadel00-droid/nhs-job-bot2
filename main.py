import requests
from bs4 import BeautifulSoup
import time
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")

URLS = [
    "https://www.healthjobsuk.com/job_list?JobSearch_d=534",
    "https://jobs.hscni.net/Search?SearchCatID=63",
    "https://apply.jobs.scot.nhs.uk/Home/Job"
]

KEYWORDS = [
    "general surgery", "trauma", "orthopedics", "plastic surgery",
    "pediatric surgery", "internal medicine", "general medicine",
    "emergency medicine", "emergency department",
    "junior", "specialty doctor", "st1", "st2", "st3",
    "clinical fellow", "junior fellow", "research fellow",
    "core", "ct1", "ct2"
]

sent_jobs = set()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

def check_sites():
    for url in URLS:
        try:
            resp = requests.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a")
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href")
                if not title or not href:
                    continue
                title_lower = title.lower()
                if "consultant" in title_lower:
                    continue
                if any(k.lower() in title_lower for k in KEYWORDS):
                    full_link = href if href.startswith("http") else url.split("/")[0] + "//" + url.split("/")[2] + href
                    if full_link not in sent_jobs:
                        sent_jobs.add(full_link)
                        send_telegram(f"New Job Found:\n{title}\n{full_link}")
                        print("Sent:", title)
        except Exception as e:
            print("Error fetching:", url, e)

def check_google():
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return
    for keyword in KEYWORDS:
        query = f"{keyword} site:jobs.nhs.uk OR site:healthjobsuk.com OR site:apply.jobs.scot.nhs.uk"
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&cx={GOOGLE_CX}&key={GOOGLE_API_KEY}"
        try:
            resp = requests.get(url).json()
            for item in resp.get("items", []):
                title = item["title"]
                link = item["link"]
                title_lower = title.lower()
                if any(k.lower() in title_lower for k in KEYWORDS):
                    if link not in sent_jobs:
                        sent_jobs.add(link)
                        send_telegram(f"Google Job Found:\n{title}\n{link}")
                        print("Sent via Google:", title)
        except Exception as e:
            print("Google search error:", e)

if __name__ == "__main__":
    print("Bot started. Monitoring jobs every 2 minutes...")
    while True:
        check_sites()
        check_google()
        time.sleep(120)  # 2 minutes
