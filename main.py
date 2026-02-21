import requests
from bs4 import BeautifulSoup
import time
import re
import json
from urllib.parse import urljoin, quote

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300  # 5 minutes

# ---------------- FILTERS ---------------- #
MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine", "paediatric", "pediatric",
    "surgery", "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic",
    "emergency medicine", "emergency department", "oncology", "cardiology",
    "respiratory", "gastroenterology", "neurology", "obstetrics", "gynaecology",
    "haematology", "anaesthetics", "anaesthesia", "intensive care", "critical care",
    "acute medicine", "stroke", "diabetes", "endocrinology", "renal", "nephrology"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2",
    "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3",
    "registrar", "specialty registrar",
    "sas doctor", "specialty doctor", "trust doctor", "clinical fellow",
    "junior fellow", "research fellow", "teaching fellow", "locum doctor",
    "specialty trainee", "junior clinical", "foundation doctor"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7", "st8",
    "advanced trainee", "higher specialty", "specialist",
    "nurse", "midwife", "psychologist", "assistant",
    "admin", "radiographer", "physiotherapist", "manager",
    "director", "healthcare assistant", "support worker",
    "technician", "pharmacist", "therapist", "porter",
    "catering", "housekeeper", "secretary", "receptionist"
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
        "parse_mode": "MarkdownV2"
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Telegram sent: {r.status_code}")
    except Exception as e:
        print("Telegram send error:", e)

def extract_job_id(link):
    # Try different patterns
    patterns = [
        r'/job/(\d+)',
        r'vacancy/(\d+)',
        r'JobId=(\d+)',
        r'jobId=(\d+)',
        r'/(\d+)$'
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    # Fallback: use last part of URL
    return link.split('/')[-1].split('?')[0]

def relevant_job(title):
    title_lower = title.lower()
    
    # Quick exclude check
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    
    # Must have a grade keyword
    has_grade = any(gr in title_lower for gr in GRADE_KEYWORDS)
    if not has_grade:
        return False
    
    # Should have a medical specialty (but be more lenient)
    has_specialty = any(sp in title_lower for sp in MEDICAL_SPECIALTIES)
    
    # If it has "doctor" and grade, count it even without specialty
    if "doctor" in title_lower and has_grade:
        return True
        
    return has_specialty

# ---------------- ACTUAL WORKING CHECKERS ---------------- #

def check_nhs_jobs_direct(seen_jobs):
    """Direct API approach for NHS Jobs"""
    print("\n🔍 Checking NHS Jobs via API...")
    
    # This is the actual API endpoint NHS Jobs uses
    api_url = "https://www.jobs.nhs.uk/api/jobs/search"
    
    # Search terms to try
    search_terms = ["doctor", "junior doctor", "foundation", "clinical fellow", "core trainee"]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    found_count = 0
    
    for term in search_terms:
        try:
            # Try POST request first
            payload = {
                "keyword": term,
                "sort": "closingDate",
                "page": 1,
                "perPage": 50
            }
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    jobs = data.get('data', [])
                    
                    for job in jobs:
                        title = job.get('title', '')
                        if not title:
                            continue
                            
                        job_id = str(job.get('id', ''))
                        if not job_id:
                            continue
                            
                        if not relevant_job(title):
                            continue
                            
                        if job_id in seen_jobs:
                            continue
                        
                        # Construct job URL
                        job_url = f"https://www.jobs.nhs.uk/candidate/job/{job_id}"
                        
                        found_count += 1
                        message = f"🚨 *NHS Job Found!*\n\n📋 *{title}*\n🔗 [Apply Here]({job_url})"
                        send_telegram(message)
                        save_seen(job_id)
                        seen_jobs.add(job_id)
                        print(f"  ✅ Found: {title[:50]}...")
                        
                except json.JSONDecodeError:
                    print(f"  ⚠️  Could not parse JSON for term '{term}'")
            
            # Be nice to API
            time.sleep(1)
            
        except Exception as e:
            print(f"  ⚠️  Error with term '{term}': {e}")
    
    print(f"  📊 Total new NHS Jobs found: {found_count}")
    return found_count

def check_healthjobsuk(seen_jobs):
    """Check HealthJobsUK"""
    print("\n🔍 Checking HealthJobsUK...")
    
    # HealthJobsUK search URL
    url = "https://www.healthjobsuk.com/search/results"
    
    params = {
        "SearchText": "doctor",
        "SearchType": "advanced",
        "Sort": "Date"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    found_count = 0
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job cards/links
        job_cards = soup.find_all("div", class_=re.compile(r"job|vacancy|result", re.I))
        
        if not job_cards:
            # Try alternative selectors
            job_links = soup.find_all("a", href=re.compile(r"/job/|/vacancy/|/detail/", re.I))
            
            for link in job_links:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                if not title or len(title) < 10:
                    continue
                    
                if not relevant_job(title):
                    continue
                
                full_url = urljoin("https://www.healthjobsuk.com", href)
                job_id = extract_job_id(full_url)
                
                if job_id in seen_jobs:
                    continue
                
                found_count += 1
                message = f"🚨 *HealthJobsUK Found!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                print(f"  ✅ Found: {title[:50]}...")
        
        print(f"  📊 Total HealthJobsUK found: {found_count}")
        
    except Exception as e:
        print(f"  ⚠️  Error checking HealthJobsUK: {e}")
    
    return found_count

def check_nhs_scotland(seen_jobs):
    """Check NHS Scotland"""
    print("\n🔍 Checking NHS Scotland...")
    
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    found_count = 0
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job links
        for link in soup.find_all("a", href=True):
            href = link['href']
            if "JobDetail" not in href and "vacancy" not in href.lower():
                continue
                
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
            
            full_url = urljoin("https://apply.jobs.scot.nhs.uk", href)
            job_id = extract_job_id(full_url)
            
            if job_id in seen_jobs:
                continue
            
            found_count += 1
            message = f"🚨 *NHS Scotland Job!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            print(f"  ✅ Found: {title[:50]}...")
        
        print(f"  📊 Total NHS Scotland found: {found_count}")
        
    except Exception as e:
        print(f"  ⚠️  Error checking NHS Scotland: {e}")
    
    return found_count

def check_hscni(seen_jobs):
    """Check Northern Ireland"""
    print("\n🔍 Checking Northern Ireland HSC...")
    
    url = "https://jobs.hscni.net/Search"
    params = {
        "Keywords": "doctor",
        "CategoryID": "0"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    found_count = 0
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job links
        for link in soup.find_all("a", href=True):
            href = link['href']
            if "JobDetail" not in href and "vacancy" not in href.lower():
                continue
                
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
            
            full_url = urljoin("https://jobs.hscni.net", href)
            job_id = extract_job_id(full_url)
            
            if job_id in seen_jobs:
                continue
            
            found_count += 1
            message = f"🚨 *Northern Ireland HSC Job!*\n\n📋 *{title}*\n🔗 [Apply Here]({full_url})"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            print(f"  ✅ Found: {title[:50]}...")
        
        print(f"  📊 Total Northern Ireland jobs found: {found_count}")
        
    except Exception as e:
        print(f"  ⚠️  Error checking HSCNI: {e}")
    
    return found_count

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot v2 - Using direct API approach")
    print("="*50)
    
    seen_jobs = load_seen()
    print(f"📚 Loaded {len(seen_jobs)} previously seen jobs")
    
    while True:
        print(f"\n{'='*50}")
        print(f"🕐 Check started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        total_found = 0
        
        # Check each source
        total_found += check_nhs_jobs_direct(seen_jobs)
        time.sleep(3)
        
        total_found += check_healthjobsuk(seen_jobs)
        time.sleep(3)
        
        total_found += check_nhs_scotland(seen_jobs)
        time.sleep(3)
        
        total_found += check_hscni(seen_jobs)
        
        print(f"\n{'='*50}")
        print(f"✅ Check complete! Total new jobs found: {total_found}")
        print(f"💤 Sleeping for {CHECK_INTERVAL} seconds...")
        print(f"{'='*50}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
