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
    "https://jobs.hscni.net/Search?SearchCatID=0"
]

# ---------------- HELPER FUNCTIONS ---------------- #

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

# ---------------- FILTER LOGIC ---------------- #

def relevant_job(title):
    title_lower = title.lower()

    EXCLUDE_KEYWORDS = [
        "consultant", "st4", "st5", "st6", "st7",
        "advanced trainee", "higher specialty",
        "nurse", "midwife", "pharmacist", "physiotherapist",
        "radiographer", "healthcare assistant", "admin",
        "manager", "director"
    ]

    GRADE_KEYWORDS = [
        "foundation", "fy1", "fy2", "f1", "f2",
        "ct1", "ct2", "ct3", "core trainee",
        "st1", "st2", "st3",
        "sho", "senior house officer",
        "registrar",
        "sas doctor", "specialty doctor", "trust doctor",
        "clinical fellow", "junior fellow", "research fellow",
        "teaching fellow", "locum doctor"
    ]

    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False

    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False

    return True

# ---------------- DATE FILTER ---------------- #

def is_recent(posted_date_str):
    """
    Only accept jobs posted from yesterday onwards
    Supports ISO format or day/month/year
    """
    try:
        posted_date = datetime.datetime.fromisoformat(posted_date_str.replace("Z",""))
    except:
        try:
            posted_date = datetime.datetime.strptime(posted_date_str, "%d/%m/%Y")
        except:
            return True  # Unknown format, include anyway

    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    return posted_date >= yesterday

# ---------------- SITE SCRAPER ---------------- #

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

        for a in job_links:
            title = a.get_text(strip=True)
            link = a["href"]

            if not title or len(title) < 10:
                continue
            if "/job/" not in link.lower() and "vacancy" not in link.lower():
                continue
            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            # Fetch posting date
            posted_date_str = get_job_date_healthjobs(link)
            if posted_date_str and not is_recent(posted_date_str):
                continue

            print("\n=== NEW JOB FOUND ===")
            print("Title:", title)
            print("Link:", link)
            print("=====================\n")

            send_telegram(f"🚨 New Job Found:\n{title}\n{link}")
            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# ---------------- SCOTLAND API ---------------- #

def check_scotland_api(seen_jobs):
    print("Checking Scotland API...")
    try:
        url = "https://apply.jobs.scot.nhs.uk/Account/Search"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        payload = {
            "Keyword": "",
            "Location": "",
            "Radius": 0,
            "SortBy": "Date",
            "SortDescending": True,
            "Page": 1
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            print("Scotland API failed:", response.status_code)
            return

        data = response.json()
        for job in data.get("Results", []):
            title = job.get("JobTitle", "")
            job_id = str(job.get("VacancyId", ""))
            link = f"https://apply.jobs.scot.nhs.uk/Home/Job/{job_id}"

            posted_date_str = job.get("DatePosted", "")
            if posted_date_str and not is_recent(posted_date_str):
                continue
            if not relevant_job(title):
                continue
            if job_id in seen_jobs:
                continue

            print("\n=== NEW SCOTLAND JOB ===")
            print("Title:", title)
            print("Link:", link)
            print("========================\n")

            send_telegram(f"🚨 Scotland Job:\n{title}\n{link}")
            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print("Error checking Scotland API:", e)

# ---------------- MAIN LOOP ---------------- #

def main():
    print("🚀 Ultimate NHS Job Bot started...")
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            check_site(url, seen_jobs)
        check_scotland_api(seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
