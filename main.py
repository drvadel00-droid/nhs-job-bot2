import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 180  # 3 minutes

# ---------------- FILTERS ---------------- #
MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine", "paediatric", "pediatric",
    "surgery", "general surgery", "emergency medicine", "oncology", "cardiology",
    "respiratory", "gastroenterology", "neurology", "obstetrics", "gynaecology",
    "haematology", "anaesthetics", "intensive care", "critical care"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2", "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3", "registrar", "specialty registrar", "sas doctor",
    "specialty doctor", "trust doctor", "clinical fellow", "junior fellow",
    "locum doctor", "senior clinical fellow"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7", "st8", "nurse", "midwife",
    "psychologist", "admin", "manager", "director", "healthcare assistant"
]

# ---------------- UTILS ---------------- #
def load_seen():
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_seen(job_id):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

def escape_telegram(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": escape_telegram(message), 
        "parse_mode": "MarkdownV2"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"  ⚠️ Telegram error: {e}")

def extract_job_id(link):
    match = re.search(r'/(\d+)$|JobId=(\d+)|vacancy/(\d+)|job/(\d+)|id=(\d+)', link)
    if match:
        return next(g for g in match.groups() if g is not None)
    return link

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    has_grade = any(gr in title_lower for gr in GRADE_KEYWORDS)
    if not has_grade:
        return False
    if "doctor" in title_lower or "clinical" in title_lower or "medical" in title_lower:
        return True
    return any(sp in title_lower for sp in MEDICAL_SPECIALTIES)

# ---------------- NORTHERN IRELAND (WORKING) ---------------- #
def check_northern_ireland(seen_jobs):
    """Northern Ireland - Fixed for current site structure"""
    print("\n🔍 Northern Ireland HSC...")
    
    # Try multiple search variations
    urls = [
        "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0",
        "https://jobs.hscni.net/Search?Keywords=clinical&CategoryID=0",
        "https://jobs.hscni.net/Search?Keywords=medical&CategoryID=0",
    ]
    
    total_found = 0
    
    for url in urls:
        try:
            print(f"  📍 Searching: {url.split('=')[1].split('&')[0]}")
            response = requests.get(url, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for job cards - HSCNI uses specific structure
            job_cards = soup.find_all("div", class_=re.compile(r"job|vacancy|result", re.I))
            
            if not job_cards:
                # Try finding links directly
                for a in soup.find_all("a", href=True):
                    href = a['href']
                    if "JobDetail" in href or "Vacancy" in href:
                        title = a.get_text(strip=True)
                        if title and len(title) > 10:
                            if relevant_job(title):
                                full_url = urljoin("https://jobs.hscni.net", href)
                                job_id = extract_job_id(full_url)
                                
                                if job_id not in seen_jobs:
                                    total_found += 1
                                    message = f"🚨 *NI Health Job*\n\n📋 {title}\n🔗 {full_url}"
                                    send_telegram(message)
                                    save_seen(job_id)
                                    seen_jobs.add(job_id)
                                    print(f"  ✅ {title[:50]}...")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
    
    print(f"  Found {total_found} new jobs")
    return total_found

# ---------------- NHS JOBS (VIA API) ---------------- #
def check_nhs_api(seen_jobs):
    """Alternative: Try NHS Jobs API endpoint"""
    print("\n🔍 NHS Jobs (API)...")
    
    api_url = "https://www.jobs.nhs.uk/api/jobs"
    
    params = {
        "keyword": "doctor",
        "sort": "postedDate",
        "limit": 50
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            jobs = data.get('data', [])
            
            found = 0
            for job in jobs:
                title = job.get('title', '')
                job_id = str(job.get('id', ''))
                
                if not title or not job_id:
                    continue
                
                if not relevant_job(title):
                    continue
                
                if job_id in seen_jobs:
                    continue
                
                job_url = f"https://www.jobs.nhs.uk/job/{job_id}"
                found += 1
                message = f"🚨 *NHS Job*\n\n📋 {title}\n🔗 {job_url}"
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                print(f"  ✅ {title[:50]}...")
            
            print(f"  Found {found} new jobs via API")
            return found
        else:
            print(f"  ⚠️ API returned {response.status_code}")
            return 0
            
    except Exception as e:
        print(f"  ⚠️ API error: {e}")
        return 0

# ---------------- ALTERNATIVE JOB BOARDS ---------------- #
def check_trac_jobs(seen_jobs):
    """Trac Jobs (used by many NHS trusts)"""
    print("\n🔍 Trac Jobs...")
    
    # Trac is used by many NHS organizations
    url = "https://trac.jobs/Search"
    params = {
        "Keywords": "doctor",
        "Sort": "Date"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found = 0
        for a in soup.find_all("a", href=re.compile(r"/jobs/\d+|/vacancy/", re.I)):
            title = a.get_text(strip=True)
            href = a['href']
            
            if not title or len(title) < 10:
                continue
            
            if not relevant_job(title):
                continue
            
            full_url = urljoin("https://trac.jobs", href)
            job_id = extract_job_id(full_url)
            
            if job_id in seen_jobs:
                continue
            
            found += 1
            message = f"🚨 *Trac Jobs*\n\n📋 {title}\n🔗 {full_url}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            print(f"  ✅ {title[:50]}...")
        
        print(f"  Found {found} new jobs")
        return found
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
        return 0

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot - WORKING SOURCES ONLY")
    print("="*60)
    print("✅ Northern Ireland: Working")
    print("🔄 NHS Jobs: Trying API")
    print("🔄 Trac Jobs: Alternative source")
    print("="*60)
    
    seen_jobs = load_seen()
    print(f"📚 Loaded {len(seen_jobs)} previously seen jobs")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        print(f"\n{'='*60}")
        print(f"🕐 Cycle #{cycle_count} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        total = 0
        
        # Northern Ireland (working)
        total += check_northern_ireland(seen_jobs)
        time.sleep(3)
        
        # Try NHS API (might work)
        total += check_nhs_api(seen_jobs)
        time.sleep(3)
        
        # Try Trac Jobs (alternative)
        total += check_trac_jobs(seen_jobs)
        
        print(f"\n{'='*60}")
        print(f"✅ Cycle #{cycle_count} complete. New jobs: {total}")
        print(f"📊 Total unique jobs seen: {len(seen_jobs)}")
        print(f"💤 Sleeping {CHECK_INTERVAL} seconds...")
        print(f"{'='*60}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
