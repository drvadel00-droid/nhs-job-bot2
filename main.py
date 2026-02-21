import requests
from bs4 import BeautifulSoup
import time
import re

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "PUT_YOUR_NEW_TOKEN_HERE"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120  # seconds

URLS = [
    # HealthJobsUK
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",

    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0",

    # Scotland NHS jobs
    "https://apply.jobs.scot.nhs.uk/Home/Search",

    # Newcastle Hospitals
    "https://www.newcastle-hospitals.nhs.uk/careers/",

    # Leeds Teaching Hospitals
    "https://www.leedsth.nhs.uk/careers/",

    # Manchester University NHS FT
    "https://mft.nhs.uk/careers/",

    # Barts Health
    "https://www.bartshealth.nhs.uk/jobs",

    # Imperial College Healthcare
    "https://www.imperial.nhs.uk/careers",

    # Guy’s & St Thomas’
    "https://www.guysandstthomas.nhs.uk/work-us",

    # UCLH
    "https://www.uclh.nhs.uk/work-with-us",

    # Portsmouth Hospitals University NHS Trust
    "https://www.porthosp.nhs.uk/careers.htm",

    # Royal United Hospitals Bath NHS Foundation Trust
    "https://www.ruh.nhs.uk/careers/"
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

def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        print("Telegram response:", r.status_code, r.text)
    except Exception as e:
        print("Telegram send error:", e)

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

def normalize_link(link, base):
    if link.startswith("/"):
        return base + link
    return link

# ---------------- SITE CHECK ---------------- #

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

            if not title or len(title) < 5:
                continue
            if not re.search(r"\d+", link):
                continue
            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            safe_title = escape_markdown(title)
            safe_link = escape_markdown(link)

            message = (
                f"🚨 *New Job Found!*\n\n"
                f"🏥 *Title:* {safe_title}\n"
                f"🔗 *Apply here:* {safe_link}"
            )

            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# ---------------- MAIN LOOP ---------------- #

def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            check_site(url, seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
