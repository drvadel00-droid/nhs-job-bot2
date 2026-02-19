import requests
from bs4 import BeautifulSoup
import time
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

URLS = [
    # England (NHS Jobs / TRAC publishing)
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0"
]

KEYWORDS = [
    # Specialties
    "general surgery",
    "trauma",
    "orthopaedic",
    "orthopedic",
    "plastic surgery",
    "paediatric surgery",
    "pediatric surgery",
    "internal medicine",
    "general medicine",
    "emergency medicine",
    "emergency department",

    # Grades
    "junior",
    "specialty doctor",
    "trust doctor",
    "st1",
    "st2",
    "st3",
    "clinical fellow",
    "junior fellow",
    "research fellow",
    "core",
    "ct1",
    "ct2"
]

seen_jobs = set()


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)


def process_page(base_url, soup):
    links = soup.find_all("a")

    for link in links:
        title = link.get_text(strip=True)
        href = link.get("href")

        if not title or not href:
            continue

        title_lower = title.lower()

        # Ignore consultant jobs
        if "consultant" in title_lower:
            continue

        # Must match at least one keyword
        if any(k in title_lower for k in KEYWORDS):

            if href.startswith("http"):
                full_link = href
            else:
                domain = base_url.split("/")[0] + "//" + base_url.split("/")[2]
                full_link = domain + href

            if full_link not in seen_jobs:
                seen_jobs.add(full_link)

                message = f"🚨 New Doctor Job Found:\n\n{title}\n\n{full_link}"
                send_telegram(message)

                print("Sent:", title)


def check_all_sites():
    for url in URLS:
        try:
            print("Checking:", url)
            resp = requests.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            process_page(url, soup)

        except Exception as e:
            print("Error checking", url, ":", e)


if __name__ == "__main__":
    print("🚀 Bot started. Monitoring UK jobs every 2 minutes...")

    while True:
        check_all_sites()
        time.sleep(120)  # 2 minutes
