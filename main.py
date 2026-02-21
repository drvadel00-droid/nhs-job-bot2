import requests
import time

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"  # Your bot token
CHAT_ID = "-1003888963521"  # Your private channel numeric ID
CHECK_INTERVAL = 120  # seconds

# ---------------- FILTERS ---------------- #
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
        print("Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print("Telegram send error:", e)

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in title_lower for sp in MEDICAL_SPECIALTIES):
        return False
    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False
    return True

# ---------------- NHS JOBS API ---------------- #
API_URL = "https://www.jobs.nhs.uk/api/JobSearch"

def fetch_jobs(page=1):
    params = {
        "staffGroup": "MEDICAL_AND_DENTAL",
        "language": "en",
        "page": page,
        "resultsPerPage": 50  # max per page
    }
    try:
        response = requests.get(API_URL, params=params, timeout=15)
        if response.status_code != 200:
            print(f"Error fetching API: {response.status_code}")
            return []
        data = response.json()
        return data.get("results", [])
    except Exception as e:
        print("Error fetching API:", e)
        return []

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()
    page = 1

    while True:
        new_jobs_found = False
        jobs = fetch_jobs(page)
        if not jobs:
            print("No jobs fetched, retrying in next interval...")
            time.sleep(CHECK_INTERVAL)
            continue

        for job in jobs:
            job_id = str(job.get("vacancyId", ""))
            title = job.get("title", "")
            link = job.get("url", "")

            if not relevant_job(title):
                continue
            if job_id in seen_jobs:
                continue

            message = f"🚨 *New NHS Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {link}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            new_jobs_found = True

        if not new_jobs_found:
            print("No new jobs found on page", page)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
