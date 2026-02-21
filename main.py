import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"  # Your bot token
CHAT_ID = "-1003888963521"  # Your private channel numeric ID
CHECK_INTERVAL = 300  # seconds (5 minutes)

# Updated URLs with actual job listing pages
URLS = [
    # NHS Jobs England - Updated format
    "https://www.jobs.nhs.uk/candidate/search?keyword=doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=junior+doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=foundation&sort=publicationDateDesc",
    
    # HealthJobsUK - Special handling
    "HEALTHJOBS_POST",
    
    # Northern Ireland
    "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0",
    
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",
]

# Trust-specific job listing pages
TRUST_JOB_PAGES = [
    "https://www.newcastle-hospitals.nhs.uk/jobs/",
    "https://www.leedsth.nhs.uk/working-for-us/current-vacancies/",
    "https://mft.nhs.uk/careers/search-vacancies/",
    "https://www.bartshealth.nhs.uk/current-vacancies",
    "https://www.imperial.nhs.uk/careers/search-vacancies",
    "https://www.guysandstthomas.nhs.uk/careers/search-all-vacancies",
    "https://www.uclh.nhs.uk/work-with-us/current-vacancies",
    "https://www.porthosp.nhs.uk/careers/current-vacancies.htm",
    "https://www.ruh.nhs.uk/careers/current_vacancies/"
]

# Add trust pages to main list
URLS.extend(TRUST_JOB_PAGES)

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

# ---------------- UTILS (These were missing!) ---------------- #
def load_seen():
    """Load previously seen job IDs from file"""
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"Error loading seen jobs: {e}")
        return set()

def save_seen(job_id):
    """Save a new job ID to file"""
    try:
        with open("seen_jobs.txt", "a") as f:
            f.write(job_id + "\n")
    except Exception as e:
        print(f"Error saving job ID: {e}")

def escape_telegram(text):
    """Escape characters for Telegram MarkdownV2"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text

def send_telegram(message):
    """Send message to Telegram channel"""
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": escape_telegram(message), 
        "parse_mode": "MarkdownV2"
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print("Telegram send error:", e)

def extract_job_id(link):
    """Extract numeric ID from job link"""
    match = re.search(r'\d+', link)
    return match.group() if match else link

def relevant_job(title):
    """Check if job title matches our filters"""
    title_lower = title.lower()
    
    # Exclude unwanted jobs
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    
    # Must include medical specialty
    if not any(sp in title_lower for sp in MEDICAL_SPECIALTIES):
        return False
    
    # Must include grade keyword
    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False
    
    return True

# ---------------- SITE CHECKERS ---------------- #
def check_nhs_england(url, seen_jobs):
    """Check NHS Jobs England"""
    print(f"Checking NHS England: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job links - adjust selectors based on actual HTML
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            
            # Check if it's a job link
            if not ("/job/" in href or "/vacancy/" in href or "job-detail" in href):
                continue
                
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
                
            full_link = urljoin("https://www.jobs.nhs.uk", href)
            job_id = extract_job_id(full_link)
            
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *NHS Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"Found: {title}")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error in NHS England check: {e}")

def check_healthjobsuk_post(seen_jobs):
    """Handle POST request for HealthJobsUK"""
    print("Checking HealthJobsUK...")
    url = "https://www.healthjobsuk.com/job_list"
    
    form_data = {
        "JobSearch_q": "doctor",
        "JobSearch_d": "",
        "JobSearch_g": "",
        "JobSearch_re": "_POST",
        "JobSearch_re_0": "1",
        "JobSearch_re_1": "1-_-_-",
        "JobSearch_re_2": "1-_-_--_-_-",
        "JobSearch_Submit": "Search",
        "_tr": "JobSearch",
        "_ts": str(int(time.time()))
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(url, data=form_data, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            
            if "jobdetail" not in href.lower():
                continue
                
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
                
            full_link = urljoin("https://www.healthjobsuk.com", href)
            job_id = extract_job_id(full_link)
            
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *HealthJobsUK Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"Found: {title}")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error checking HealthJobsUK: {e}")

def check_hscni(url, seen_jobs):
    """Northern Ireland specific handler"""
    print(f"Checking Northern Ireland: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            
            if "JobDetail" not in href and "vacancy" not in href.lower():
                continue
                
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
                
            full_link = urljoin("https://jobs.hscni.net", href)
            job_id = extract_job_id(full_link)
            
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *NI Health Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"Found: {title}")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error checking HSCNI: {e}")

def check_scotland(seen_jobs):
    """Scotland NHS jobs"""
    print("Checking Scotland jobs...")
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "JobDetail?JobId=" not in href:
                continue
                
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
                
            full_link = urljoin("https://apply.jobs.scot.nhs.uk", href)
            job_id = extract_job_id(full_link)
            
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *Scotland Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"Found: {title}")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print("Error checking Scotland:", e)

def check_trust_site(url, seen_jobs):
    """Generic handler for trust websites"""
    print(f"Checking trust site: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Common job link patterns
        job_patterns = ["/job/", "/vacancy/", "/careers/", "/opportunity/",
                       "/position/", "/role/", "/detail/", "job-detail"]
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            
            # Check if it looks like a job link
            is_job_link = any(pattern in href for pattern in job_patterns)
            is_job_title = len(title) > 10 and any(k in title.lower() for k in ["doctor", "medical", "clinical", "fy", "ct", "st"])
            
            if not (is_job_link or is_job_title):
                continue
                
            if not relevant_job(title):
                continue
                
            full_link = urljoin(url, href)
            job_id = extract_job_id(full_link)
            
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *NHS Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"Found: {title}")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error checking trust site {url}: {e}")

def check_site(url, seen_jobs):
    """Main dispatcher for different site types"""
    try:
        if url == "HEALTHJOBS_POST":
            check_healthjobsuk_post(seen_jobs)
        elif "jobs.hscni.net" in url:
            check_hscni(url, seen_jobs)
        elif "apply.jobs.scot.nhs.uk" in url:
            check_scotland(seen_jobs)
        elif "jobs.nhs.uk" in url:
            check_nhs_england(url, seen_jobs)
        else:
            check_trust_site(url, seen_jobs)
            
    except Exception as e:
        print(f"Error in check_site for {url}: {e}")

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()
    print(f"Loaded {len(seen_jobs)} previously seen jobs")
    
    while True:
        for url in URLS:
            print(f"\n--- Checking: {url} ---")
            check_site(url, seen_jobs)
            time.sleep(2)  # Be nice to servers between checks
        
        print(f"\n✅ Check complete. Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
