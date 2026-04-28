import time
import re
import os
import sys

# Force output to appear in logs immediately
sys.stdout.reconfigure(line_buffering=True)
print("HEARTBEAT: Script has started and is initializing...")

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120 
DATA_PATH = os.getenv("PERSISTENT_STORAGE", ".") 
SEEN_FILE = os.path.join(DATA_PATH, "seen_jobs.txt")

# FULL LIST OF URLS
URLS = [
    "https://www.healthjobsuk.com/job_list?JobSearch_Submit=Search&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=534&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=64082&_srt=startdate&_sd=d",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=737&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=81534&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=594&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=88730&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=572&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=97667&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=558&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=110250&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=581&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=44291&_srt=startdate&_sd=a",
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search/results?searchFormType=sortBy&sort=publicationDateDesc&searchByLocationOnly=true&language=en#",
    "https://jobs.hscni.net/Search?SearchCatID=0",
    "https://apply.jobs.scot.nhs.uk/Home/Search"
]

MEDICAL_SPECIALTIES = ["medicine", "acute", "internal", "general medicine", "surgery", "general surgery", "trauma", "orthopaedic", "plastic", "emergency", "cardiology", "respiratory", "gastro", "neurology", "paediatric", "haematology", "intensive care", "critical care", "icu", "vascular", "urology"]
GRADE_KEYWORDS = ["fy1", "fy2", "foundation", "ct1", "ct2", "ct3", "st1", "st2", "st3", "registrar", "trust doctor", "trust grade", "clinical fellow", "junior fellow", "junior clinical fellow", "specialty doctor", "junior", "locum doctor"]
EXCLUDE_KEYWORDS = ["consultant", "st4", "st5", "st6", "st7", "nurse", "midwife", "assistant", "manager", "director", "admin", "physiotherapist", "radiographer", "lead", "scientist", "receptionist", "housekeeper", "cook", "clerk", "practitioner", "nutritionist", "nutrition", "coordinator", "therapist", "secretary", "pharmacist", "matron", "worker"]

def relevant_job(title):
    t = title.lower()
    return not any(ex in t for ex in EXCLUDE_KEYWORDS) and any(sp in t for sp in MEDICAL_SPECIALTIES) and any(gr in t for gr in GRADE_KEYWORDS)

def send_telegram(message):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def load_seen():
    if not os.path.exists(SEEN_FILE): return set()
    with open(SEEN_FILE, "r") as f: return set(f.read().splitlines())

def check_site(url, seen_jobs):
    print(f"DEBUG: Checking: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            soup = BeautifulSoup(page.content(), "html.parser")
            links = soup.select('a[href*="/Job/"], a[href*="/job/"]')
            for a in links:
                title = a.get_text(strip=True)
                if not title or not relevant_job(title): continue
                link = a['href']
                if not link.startswith("http"): link = "/".join(url.split('/')[:3]) + link
                job_id = re.search(r"\d+", link)
                if job_id and job_id.group() not in seen_jobs:
                    job_id_str = job_id.group()
                    send_telegram(f"🚨 NEW NHS JOB\n\n🏥 {title}\n🔗 {link}")
                    seen_jobs.add(job_id_str)
                    with open(SEEN_FILE, "a") as f: f.write(job_id_str + "\n")
        except Exception as e:
            print(f"DEBUG Error: {e}")
        finally:
            browser.close()

def main():
    seen_jobs = load_seen()
    print("Bot started...")
    while True:
        for url in URLS:
            check_site(url, seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
