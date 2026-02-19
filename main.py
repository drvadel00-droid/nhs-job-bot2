import requests
from bs4 import BeautifulSoup
import time
import re
import os
from datetime import datetime, timedelta
from threading import Thread

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Telegram Bot Token
CHAT_ID = os.environ.get("CHAT_ID")      # Telegram Chat ID

CHECK_INTERVAL = 120  # seconds (2 minutes)

# Sites to monitor
URLS = {
    "HSCNI": "https://jobs.hscni.net/Search?SearchCatID=0",
    "NHS_England": "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "HealthJobsUK": "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",
    "Scotland_NHS": "https://apply.jobs.scot.nhs.uk/Home/Search"
}

SPECIALTY_KEYWORDS = [
    "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic surgery",
    "paediatric surgery", "pediatric surgery", "internal medicine", "general medicine",
    "emergency medicine", "emergency department"
]

GRADE_KEYWORDS = [
    "junior", "specialty doctor", "trust doctor", "st1", "st2", "st3",
    "clinical fellow", "junior fellow", "research fellow", "core", "ct1", "ct2"
]

EXCLUDE_KEYWORDS = [
    "consultant", "nurse", "midwife", "pharmacist", "physiotherapist",
    "radiographer", "healthcare assistant", "admin", "manager", "director"
]

SEEN_FILE = "seen_jobs.txt"

# ---------------------------------------- #

def load_seen():
    seen = {}
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "||" in line:
                    job_id, ts = line.split("||")
                    seen[job_id] = datetime.fromisoformat(ts)
    return seen

def save_seen(job_id):
    with open(SEEN_FILE, "a") as f:
        f.write(f"{job_id}||{datetime.now().isoformat()}\n")

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    specialty_match = any(sp in title_lower for sp in SPECIALTY_KEYWORDS)
    grade_match = any(gr in title_lower for gr in GRADE_KEYWORDS)
    return specialty_match and grade_match

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

# ---------------- SITE-SPECIFIC SCRAPERS ---------------- #

def scrape_hscni(seen_jobs):
    try:
        url = URLS["HSCNI"]
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=True)
        for a in links:
            title = a.get_text(strip=True)
            link = a["href"]
            if not title or len(title) < 10:
                continue
            if not relevant_job(title):
                continue
            job_id = re.search(r'\d+', link)
            job_id = job_id.group() if job_id else link
            if job_id in seen_jobs:
                continue
            send_telegram(f"🚨 HSCNI Job: {title}\n{link}")
            print(f"NEW HSCNI JOB: {title} | {link}")
            save_seen(job_id)
            seen_jobs[job_id] = datetime.now()
    except Exception as e:
        print(f"HSCNI Error: {e}")

def scrape_nhs_england(seen_jobs):
    try:
        url = URLS["NHS_England"]
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        vacancies = soup.select("a.vacancy-title")
        for a in vacancies:
            title = a.get_text(strip=True)
            link = a["href"]
            if not title or len(title) < 10:
                continue
            if not relevant_job(title):
                continue
            job_id = re.search(r'\d+', link)
            job_id = job_id.group() if job_id else link
            if job_id in seen_jobs:
                continue
            send_telegram(f"🚨 NHS England Job: {title}\nhttps://www.jobs.nhs.uk{link}")
            print(f"NEW NHS ENGLAND JOB: {title} | {link}")
            save_seen(job_id)
            seen_jobs[job_id] = datetime.now()
    except Exception as e:
        print(f"NHS England Error: {e}")

def scrape_healthjobsuk(seen_jobs):
    try:
        url = URLS["HealthJobsUK"]
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            link = a["href"]
            if not title or len(title) < 10:
                continue
            if not relevant_job(title):
                continue
            job_id = re.search(r'\d+', link)
            job_id = job_id.group() if job_id else link
            if job_id in seen_jobs:
                continue
            send_telegram(f"🚨 HealthJobsUK: {title}\n{link}")
            print(f"NEW HealthJobsUK JOB: {title} | {link}")
            save_seen(job_id)
            seen_jobs[job_id] = datetime.now()
    except Exception as e:
        print(f"HealthJobsUK Error: {e}")

def scrape_scotland(seen_jobs):
    try:
        url = URLS["Scotland_NHS"]
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            link = a["href"]
            if not title or len(title) < 10:
                continue
            if not relevant_job(title):
                continue
            job_id = re.search(r'\d+', link)
            job_id = job_id.group() if job_id else link
            if job_id in seen_jobs:
                continue
            send_telegram(f"🚨 Scotland NHS Job: {title}\nhttps://apply.jobs.scot.nhs.uk{link}")
            print(f"NEW Scotland JOB: {title} | {link}")
            save_seen(job_id)
            seen_jobs[job_id] = datetime.now()
    except Exception as e:
        print(f"Scotland NHS Error: {e}")

# ---------------- MAIN LOOP ---------------- #

def main():
    print("🚀 Ultimate NHS Job Bot started...")
    seen_jobs = {}
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "||" in line:
                    job_id, ts = line.split("||")
                    seen_jobs[job_id] = datetime.fromisoformat(ts)

    while True:
        threads = []
        for func in [scrape_hscni, scrape_nhs_england, scrape_healthjobsuk, scrape_scotland]:
            t = Thread(target=func, args=(seen_jobs,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # Clean seen jobs older than 60 days
        cutoff = datetime.now() - timedelta(days=60)
        seen_jobs = {jid: ts for jid, ts in seen_jobs.items() if ts >= cutoff}
        with open(SEEN_FILE, "w") as f:
            for jid, ts in seen_jobs.items():
                f.write(f"{jid}||{ts.isoformat()}\n")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
