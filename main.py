import requests
from bs4 import BeautifulSoup
import time
import datetime
import re

# ---------------- CONFIG ---------------- #

CHECK_INTERVAL = 120  # 2 minutes

URLS = [
    # Broad HealthJobsUK
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",

    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0"
]

SPECIALTY_KEYWORDS = [
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
    "emergency department"
]

GRADE_KEYWORDS = [
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

EXCLUDE_KEYWORDS = [
    "consultant",
    "nurse",
    "midwife",
    "pharmacist",
    "physiotherapist",
    "radiographer",
    "healthcare assistant",
    "admin",
    "manager",
    "director"
]

# ---------------------------------------- #

def load_seen():
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except:
        return set()

def save_seen(job_id):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

def is_recent(text):
    text = text.lower()
    return "today" in text or "yesterday" in text or "hour" in text

def relevant_job(title):
    title_lower = title.lower()

    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False

    specialty_match = any(sp in title_lower for sp in SPECIALTY_KEYWORDS)
    grade_match = any(gr in title_lower for gr in GRADE_KEYWORDS)

    return specialty_match and grade_match

def extract_job_id(link):
    match = re.search(r'\d+', link)
    return match.group() if match else link

def check_site(url, seen_jobs):
    print(f"Checking {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            link = a["href"]

            if not title or len(title) < 5:
                continue

            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)

            if job_id in seen_jobs:
                continue

            print("NEW JOB FOUND:")
            print(title)
            print(link)
            print("------")

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

def main():
    print("Bot started...")
    seen_jobs = load_seen()

    while True:
        for url in URLS:
            check_site(url, seen_jobs)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
