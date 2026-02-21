import requests
from bs4 import BeautifulSoup
import re

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"

URL = "https://www.jobs.nhs.uk/candidate/search/results?language=en"

# Filters for relevant jobs
MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine", "paediatric", "pediatric",
    "surgery", "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic",
    "emergency medicine", "emergency department", "oncology", "cardiology",
    "respiratory", "gastroenterology", "neurology", "obstetrics", "gynaecology",
    "haematology"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2",
    "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3",
    "registrar",
    "sas doctor", "specialty doctor", "trust doctor",
    "clinical fellow", "junior fellow", "research fellow",
    "teaching fellow", "locum doctor"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "advanced trainee", "higher specialty",
    "nurse", "midwife", "psychologist", "assistant",
    "admin", "radiographer", "physiotherapist", "manager",
    "director", "healthcare assistant"
]

# ---------------- UTILS ---------------- #
def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in title_lower for sp in MEDICAL_SPECIALTIES):
        return False
    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False
    return True

def escape_telegram(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": escape_telegram(message), "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print("Telegram send error:", e)

# ---------------- FETCH JOBS ---------------- #
def fetch_jobs(url):
    page = 1
    while True:
        full_url = f"{url}&page={page}"
        print(f"Fetching page {page}...")
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(full_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        job_items = soup.select("div.job-info")
        if not job_items:
            print("No more jobs found, ending.")
            break

        for job in job_items:
            title_tag = job.select_one("h3 a")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = "https://www.jobs.nhs.uk" + title_tag.get("href", "")

            if relevant_job(title):
                message = f"🚨 *New NHS Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {link}"
                print(message)
                send_telegram(message)

        page += 1

if __name__ == "__main__":
    fetch_jobs(URL)
