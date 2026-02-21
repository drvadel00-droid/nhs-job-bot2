import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 180  # 3 minutes (to catch jobs quickly)
MAX_PAGES = 5  # Scan up to 5 pages deep

# ---------------- FILTERS ---------------- #
MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine", "paediatric", "pediatric",
    "surgery", "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic",
    "emergency medicine", "emergency department", "oncology", "cardiology",
    "respiratory", "gastroenterology", "neurology", "obstetrics", "gynaecology",
    "haematology", "anaesthetics", "intensive care", "critical care", "acute medicine"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2",
    "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3",
    "registrar", "specialty registrar",
    "sas doctor", "specialty doctor", "trust doctor",
    "clinical fellow", "junior fellow", "research fellow",
    "teaching fellow", "locum doctor", "senior clinical fellow"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7", "st8",
    "advanced trainee", "higher specialty",
    "nurse", "midwife", "psychologist", "assistant",
    "admin", "radiographer", "physiotherapist", "manager",
    "director", "healthcare assistant", "support worker"
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
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": escape_telegram(message), 
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print(f"  ✅ Telegram sent")
    except Exception as e:
        print(f"  ⚠️ Telegram error: {e}")

def extract_job_id(link):
    patterns = [
        r'/job/(\d+)',
        r'/vacancy/(\d+)',
        r'JobId=(\d+)',
        r'jobId=(\d+)',
        r'/(\d+)$',
        r'Vacancy\.ashx\?id=(\d+)',
        r'job-detail/(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
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
    
    has_specialty = any(sp in title_lower for sp in MEDICAL_SPECIALTIES)
    return has_specialty

# ---------------- DEEP SCANNING CHECKERS ---------------- #

def check_hscni_deep(seen_jobs):
    """Northern Ireland - Deep scan multiple pages"""
    print("\n🔍 Deep scanning Northern Ireland HSC...")
    
    base_url = "https://jobs.hscni.net/Search"
    found = 0
    
    for page in range(1, MAX_PAGES + 1):
        print(f"  📄 Scanning page {page}...")
        
        params = {
            "Keywords": "doctor",
            "CategoryID": "0",
            "page": page
        }
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find job links
            job_links = []
            for a in soup.find_all("a", href=True):
                href = a['href']
                if "JobDetail" in href or "Vacancy" in href:
                    job_links.append(a)
            
            if not job_links:
                print(f"  📄 No more jobs on page {page}")
                break
                
            for a in job_links:
                title = a.get_text(strip=True)
                href = a['href']
                
                if not title or len(title) < 10:
                    continue
                
                if not relevant_job(title):
                    continue
                
                full_url = urljoin("https://jobs.hscni.net", href)
                job_id = extract_job_id(full_url)
                
                if job_id in seen_jobs:
                    continue
                
                found += 1
                message = f"🚨 *NEW NI Health Job!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                print(f"  ✅ NEW: {title[:60]}...")
            
            time.sleep(1)  # Be nice to server
            
        except Exception as e:
            print(f"  ⚠️ Error on page {page}: {e}")
            break
    
    print(f"  📊 Found {found} NEW jobs across {page} pages")
    return found

def check_nhs_england_deep(seen_jobs):
    """NHS Jobs England - Deep scan multiple pages"""
    print("\n🔍 Deep scanning NHS Jobs England...")
    
    keywords = ["doctor", "foundation", "clinical+fellow", "junior+doctor"]
    found = 0
    
    for keyword in keywords:
        for page in range(1, MAX_PAGES + 1):
            print(f"  📄 Scanning '{keyword}' page {page}...")
            
            url = f"https://www.jobs.nhs.uk/candidate/jobs/results"
            params = {
                "keyword": keyword,
                "page": page,
                "sort": "closingdate"  # Newest first
            }
            
            headers = {"User-Agent": "Mozilla/5.0"}
            
            try:
                response = requests.get(url, params=params, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for job links
                job_links = soup.find_all("a", href=re.compile(r"/job/\d+"))
                
                if not job_links:
                    print(f"  📄 No more jobs for '{keyword}' on page {page}")
                    break
                
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
                    
                    found += 1
                    message = f"🚨 *NEW NHS England Job!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
                    send_telegram(message)
                    save_seen(job_id)
                    seen_jobs.add(job_id)
                    print(f"  ✅ NEW: {title[:60]}...")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
                break
    
    print(f"  📊 Found {found} NEW NHS England jobs")
    return found

def check_healthjobsuk_deep(seen_jobs):
    """HealthJobsUK - Deep scan"""
    print("\n🔍 Deep scanning HealthJobsUK...")
    
    url = "https://www.healthjobsuk.com/search/results"
    found = 0
    
    for page in range(1, MAX_PAGES + 1):
        print(f"  📄 Scanning page {page}...")
        
        params = {
            "SearchText": "doctor",
            "Page": page,
            "Sort": "Date"
        }
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for job links
            job_links = soup.find_all("a", href=re.compile(r"/job/|/vacancy/", re.I))
            
            if not job_links:
                print(f"  📄 No more jobs on page {page}")
                break
            
            for a in job_links:
                title = a.get_text(strip=True)
                href = a['href']
                
                if not title or len(title) < 10:
                    continue
                
                if not relevant_job(title):
                    continue
                
                full_url = urljoin("https://www.healthjobsuk.com", href)
                job_id = extract_job_id(full_url)
                
                if job_id in seen_jobs:
                    continue
                
                found += 1
                message = f"🚨 *NEW HealthJobsUK Job!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                print(f"  ✅ NEW: {title[:60]}...")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            break
    
    print(f"  📊 Found {found} NEW HealthJobsUK jobs")
    return found

def check_nhs_scotland_deep(seen_jobs):
    """NHS Scotland - Deep scan"""
    print("\n🔍 Deep scanning NHS Scotland...")
    
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    found = 0
    
    for page in range(1, MAX_PAGES + 1):
        print(f"  📄 Scanning page {page}...")
        
        params = {
            "page": page
        }
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find job links
            job_links = []
            for a in soup.find_all("a", href=True):
                href = a['href']
                if "JobDetail" in href or "vacancy" in href.lower():
                    job_links.append(a)
            
            if not job_links:
                print(f"  📄 No more jobs on page {page}")
                break
            
            for a in job_links:
                title = a.get_text(strip=True)
                href = a['href']
                
                if not title or len(title) < 10:
                    continue
                
                if not relevant_job(title):
                    continue
                
                full_url = urljoin("https://apply.jobs.scot.nhs.uk", href)
                job_id = extract_job_id(full_url)
                
                if job_id in seen_jobs:
                    continue
                
                found += 1
                message = f"🚨 *NEW NHS Scotland Job!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                print(f"  ✅ NEW: {title[:60]}...")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            break
    
    print(f"  📊 Found {found} NEW Scotland jobs")
    return found

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot - REAL-TIME DETECTION MODE")
    print(f"📚 Scanning up to {MAX_PAGES} pages deep every {CHECK_INTERVAL} seconds")
    print("="*60)
    
    seen_jobs = load_seen()
    print(f"📚 Loaded {len(seen_jobs)} previously seen jobs")
    
    while True:
        print(f"\n{'='*60}")
        print(f"🕐 Deep scan started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        total = 0
        
        # Deep scan all sources
        total += check_hscni_deep(seen_jobs)
        time.sleep(3)
        
        total += check_nhs_england_deep(seen_jobs)
        time.sleep(3)
        
        total += check_healthjobsuk_deep(seen_jobs)
        time.sleep(3)
        
        total += check_nhs_scotland_deep(seen_jobs)
        
        print(f"\n{'='*60}")
        print(f"✅ Deep scan complete! Total NEW jobs found: {total}")
        print(f"💤 Sleeping {CHECK_INTERVAL} seconds before next deep scan...")
        print(f"{'='*60}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
