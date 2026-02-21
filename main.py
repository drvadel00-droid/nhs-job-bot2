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
    "haematology", "anaesthetics", "intensive care", "critical care", "acute medicine"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2", "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3", "registrar", "specialty registrar", "sas doctor",
    "specialty doctor", "trust doctor", "clinical fellow", "junior fellow",
    "research fellow", "teaching fellow", "locum doctor", "senior clinical fellow"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7", "st8", "nurse", "midwife",
    "psychologist", "admin", "manager", "director", "healthcare assistant"
]

# ---------------- UTILS ---------------- #
def load_seen():
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
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
    except:
        pass

def extract_job_id(link):
    match = re.search(r'/(\d+)$|JobId=(\d+)|vacancy/(\d+)|job/(\d+)', link)
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
    if "doctor" in title_lower or "clinical" in title_lower:
        return True
    return any(sp in title_lower for sp in MEDICAL_SPECIALTIES)

# ---------------- WORKING JOB CHECKERS ---------------- #

def check_northern_ireland(seen_jobs):
    """Northern Ireland - Already Working (shows newest first by default)"""
    print("\n🔍 Northern Ireland HSC...")
    url = "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0"
    
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found = 0
        for a in soup.find_all("a", href=True):
            href = a['href']
            if "JobDetail" not in href:
                continue
            
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            
            if not relevant_job(title):
                continue
            
            full_url = urljoin("https://jobs.hscni.net", href)
            job_id = extract_job_id(full_url)
            
            if job_id in seen_jobs:
                continue
            
            found += 1
            message = f"🚨 *NI Health Job*\n\n📋 {title}\n🔗 {full_url}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            print(f"  ✅ {title[:50]}...")
        
        print(f"  Found {found} new jobs")
        return found
    except Exception as e:
        print(f"  Error: {e}")
        return 0

def check_nhs_england(seen_jobs):
    """NHS England - Sorted by Posted Date (Newest First)"""
    print("\n🔍 NHS England (Newest First)...")
    
    # CORRECT: sort by posted date (newest first)
    urls = [
        "https://www.jobs.nhs.uk/candidate/jobs/search?keyword=doctor&sort=posteddate",
        "https://www.jobs.nhs.uk/candidate/jobs/search?keyword=foundation&sort=posteddate",
        "https://www.jobs.nhs.uk/candidate/jobs/search?keyword=junior+doctor&sort=posteddate",
        "https://www.jobs.nhs.uk/candidate/jobs/search?keyword=clinical+fellow&sort=posteddate",
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    total_found = 0
    
    for url in urls:
        try:
            print(f"  📍 Searching: {url.split('?')[1]}")
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find job links
            job_links = soup.find_all("a", href=re.compile(r"/job/\d+"))
            
            if not job_links:
                print(f"  ⚠️ No jobs found for this search")
                continue
            
            for a in job_links:
                title = a.get_text(strip=True)
                href = a['href']
                
                if not title or len(title) < 10:
                    continue
                
                if not relevant_job(title):
                    continue
                
                full_url = urljoin("https://www.jobs.nhs.uk", href)
                job_id = extract_job_id(full_url)
                
                if job_id in seen_jobs:
                    continue
                
                total_found += 1
                message = f"🚨 *NHS England Job*\n\n📋 {title}\n🔗 {full_url}"
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                print(f"  ✅ {title[:50]}...")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"  Found {total_found} new jobs")
    return total_found

def check_healthjobsuk(seen_jobs):
    """HealthJobsUK - Sorted by Date (Newest First)"""
    print("\n🔍 HealthJobsUK (Newest First)...")
    
    # CORRECT: sort by DateDesc for newest first
    url = "https://www.healthjobsuk.com/jobs/doctor?sort=DateDesc"
    
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found = 0
        # Look for job cards/links
        job_elements = soup.find_all("div", class_=re.compile(r"job|vacancy", re.I))
        
        if not job_elements:
            # Fallback to links
            job_elements = soup.find_all("a", href=re.compile(r"/job/|/vacancy/", re.I))
        
        for element in job_elements:
            if element.name == 'a':
                title = element.get_text(strip=True)
                href = element['href']
            else:
                # Try to find link inside div
                link = element.find("a", href=True)
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link['href']
            
            if not title or len(title) < 10:
                continue
            
            if not relevant_job(title):
                continue
            
            full_url = urljoin("https://www.healthjobsuk.com", href)
            job_id = extract_job_id(full_url)
            
            if job_id in seen_jobs:
                continue
            
            found += 1
            message = f"🚨 *HealthJobsUK*\n\n📋 {title}\n🔗 {full_url}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            print(f"  ✅ {title[:50]}...")
        
        print(f"  Found {found} new jobs")
        return found
    except Exception as e:
        print(f"  Error: {e}")
        return 0

def check_scotland(seen_jobs):
    """NHS Scotland - Newest appear first by default"""
    print("\n🔍 NHS Scotland...")
    
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found = 0
        for a in soup.find_all("a", href=True):
            href = a['href']
            if "JobDetail" not in href:
                continue
            
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            
            if not relevant_job(title):
                continue
            
            full_url = urljoin("https://apply.jobs.scot.nhs.uk", href)
            job_id = extract_job_id(full_url)
            
            if job_id in seen_jobs:
                continue
            
            found += 1
            message = f"🚨 *NHS Scotland Job*\n\n📋 {title}\n🔗 {full_url}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            print(f"  ✅ {title[:50]}...")
        
        print(f"  Found {found} new jobs")
        return found
    except Exception as e:
        print(f"  Error: {e}")
        return 0

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot - NEWEST JOBS FIRST")
    print("="*60)
    print("✅ Northern Ireland: Newest first by default")
    print("✅ NHS England: Sorted by posted date")
    print("✅ HealthJobsUK: Sorted by date descending")
    print("✅ NHS Scotland: Newest first by default")
    print("="*60)
    
    seen_jobs = load_seen()
    print(f"📚 Loaded {len(seen_jobs)} previously seen jobs")
    
    while True:
        print(f"\n{'='*60}")
        print(f"🕐 Check at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        total = 0
        total += check_northern_ireland(seen_jobs)
        time.sleep(2)
        total += check_nhs_england(seen_jobs)
        time.sleep(2)
        total += check_healthjobsuk(seen_jobs)
        time.sleep(2)
        total += check_scotland(seen_jobs)
        
        print(f"\n{'='*60}")
        print(f"✅ Total new jobs: {total}")
        print(f"💤 Sleeping {CHECK_INTERVAL} seconds...")
        print(f"{'='*60}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
