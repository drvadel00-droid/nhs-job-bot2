import requests
from bs4 import BeautifulSoup
import time
import re
import os
import datetime

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
CHECK_INTERVAL = 120  # seconds

URLS = [
    # HealthJobsUK
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",

    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0",

    # Scotland NHS jobs (public page)
    "https://apply.jobs.scot.nhs.uk/Home/Search"
]

# ---------------- FILTER LOGIC ---------------- #

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

def load_seen():
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except:
        return set()

def save_seen(job_id):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def extract_job_id(link):
    match = re.search(r'\d+', link)
    return match.group() if match else link

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in title_lower for sp in MEDICAL_SPECIALTIES):
        return False
    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False
    return True

def is_recent(posted_date_str):
    try:
        posted_date = datetime.datetime.fromisoformat(posted_date_str.replace("Z",""))
    except:
        try:
            posted_date = datetime.datetime.strptime(posted_date_str, "%d/%m/%Y")
        except:
            return True  # If no date, consider it recent
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    return posted_date >= yesterday

def normalize_link(link, base):
    if link.startswith("/"):
        return base + link
    return link

# ---------------- SITE CHECK ---------------- #

def get_job_date_healthjobs(link):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(link, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        date_tag = soup.find("time")
        if date_tag:
            return date_tag.get("datetime", "")
    except:
        return ""
    return ""

def check_site(url, seen_jobs):
    print(f"Checking {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        job_links = soup.find_all("a", href=True)

        base_url = re.match(r"(https?://[^/]+)", url).group(1)

        for a in job_links:
            title = a.get_text(strip=True)
            link = normalize_link(a["href"], base_url)

            if not title or len(title) < 10:
                continue
            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            posted_date_str = get_job_date_healthjobs(link)
            if posted_date_str and not is_recent(posted_date_str):
                continue

            # Telegram notification
            message = f"🚨 New Job Found!\n\n🏥 {title}\n🔗 Apply: {link}"
            print(message + "\n")
            send_telegram(message)

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# ---------------- SCOTLAND CHECK ---------------- #

def check_scotland(seen_jobs):
    print("Checking Scotland jobs...")
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        a_tags = soup.find_all("a", href=True)

        for a in a_tags:
            href = a['href']
            if "JobDetail?JobId=" not in href:
                continue
            link = normalize_link(href, "https://apply.jobs.scot.nhs.uk")
            title = a.get_text(strip=True)
            if not relevant_job(title):
                continue
            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            # Scotland does not expose date in HTML easily, assume recent
            message = f"🚨 Scotland Job Found!\n\n🏥 {title}\n🔗 Apply: {link}"
            print(message + "\n")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print("Error checking Scotland:", e)

# ---------------- MAIN LOOP ---------------- #

def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            if "apply.jobs.scot.nhs.uk" in url:
                check_scotland(seen_jobs)
            else:
                check_site(url, seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
