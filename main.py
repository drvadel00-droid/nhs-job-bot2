import time
import re
import os
import sys
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

# Force line buffering so Railway logs appear in real-time
sys.stdout.reconfigure(line_buffering=True)

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300 
DATA_PATH = os.getenv("PERSISTENT_STORAGE", ".") 
SEEN_FILE = os.path.join(DATA_PATH, "seen_jobs.txt")

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
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Print page info to logs
            content = page.content()
            print(f"DEBUG: Page HTML length: {len(content)}")
            print(f"DEBUG: Page Preview: {content[:500]}")
            
            soup = BeautifulSoup(content, "html.parser")
            
            # Find ANY link that has 'job' in it
            links = soup.find_all('a', href=re.compile(r'job', re.I))
            print(f"DEBUG: Found {len(links)} links containing 'job' in the URL")
            
            for a in links:
                print(f"DEBUG: Found Link: {a.get_text(strip=True)} -> {a.get('href', 'no-href')}")
                
        except Exception as e:
            print(f"DEBUG Error on {url}: {e}")
        finally:
            browser.close()


def main():
    print("HEARTBEAT: Script initialized...")
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            try:
                check_site(url, seen_jobs)
            except Exception as e:
                print(f"DEBUG: Skipping {url} due to error: {e}")
                continue 
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
