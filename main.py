import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300  # 5 minutes

# ---------------- RELIABLE SOURCES ONLY ---------------- #
URLS = [
    # NHS Jobs England (main source)
    {
        'name': 'NHS Jobs England',
        'url': 'https://www.jobs.nhs.uk/candidate/search?keyword=doctor&sort=publicationDateDesc',
        'type': 'nhs_england'
    },
    {
        'name': 'NHS Junior Doctor Jobs',
        'url': 'https://www.jobs.nhs.uk/candidate/search?keyword=junior+doctor&sort=publicationDateDesc',
        'type': 'nhs_england'
    },
    {
        'name': 'NHS Foundation Jobs',
        'url': 'https://www.jobs.nhs.uk/candidate/search?keyword=foundation&sort=publicationDateDesc',
        'type': 'nhs_england'
    },
    
    # Scotland
    {
        'name': 'NHS Scotland',
        'url': 'https://apply.jobs.scot.nhs.uk/Home/Search',
        'type': 'scotland'
    },
    
    # Northern Ireland
    {
        'name': 'HSC Northern Ireland',
        'url': 'https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0',
        'type': 'hscni'
    },
]

# ---------------- FILTERS ---------------- #
MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine", "paediatric", "pediatric",
    "surgery", "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic",
    "emergency medicine", "emergency department", "oncology", "cardiology",
    "respiratory", "gastroenterology", "neurology", "obstetrics", "gynaecology",
    "haematology", "anaesthetics", "anaesthesia", "intensive care", "critical care"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2",
    "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3",
    "registrar",
    "sas doctor", "specialty doctor", "trust doctor",
    "clinical fellow", "junior fellow", "research fellow",
    "teaching fellow", "locum doctor", "specialty trainee"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7", "st8",
    "advanced trainee", "higher specialty",
    "nurse", "midwife", "psychologist", "assistant",
    "admin", "radiographer", "physiotherapist", "manager",
    "director", "healthcare assistant", "support worker",
    "technician", "pharmacist", "therapist"
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
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def extract_job_id(link):
    match = re.search(r'/(\d+)$|JobId=(\d+)|vacancy/(\d+)', link)
    if match:
        return next(g for g in match.groups() if g is not None)
    return link

def relevant_job(title):
    title_lower = title.lower()
    
    # Exclude unwanted jobs
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    
    # Must include medical specialty
    has_specialty = any(sp in title_lower for sp in MEDICAL_SPECIALTIES)
    
    # Must include grade keyword
    has_grade = any(gr in title_lower for gr in GRADE_KEYWORDS)
    
    return has_specialty and has_grade

# ---------------- SITE CHECKERS ---------------- #
def check_nhs_england(site, seen_jobs):
    """Check NHS Jobs England"""
    print(f"Checking {site['name']}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        response = requests.get(site['url'], headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job cards/links
        job_elements = soup.find_all(['a', 'div', 'article'], 
                                     class_=re.compile(r'job|vacancy|result|card', re.I))
        
        if not job_elements:
            # Try finding all links as fallback
            job_elements = soup.find_all('a', href=re.compile(r'/job/|/vacancy/|/detail/'))
        
        found_count = 0
        for element in job_elements:
            # Get the link and title
            if element.name == 'a':
                link_tag = element
                title = element.get_text(strip=True)
            else:
                link_tag = element.find('a', href=True)
                title = element.get_text(strip=True) if not link_tag else link_tag.get_text(strip=True)
            
            if not link_tag or not title:
                continue
                
            href = link_tag.get('href', '')
            full_link = urljoin("https://www.jobs.nhs.uk", href)
            
            if not relevant_job(title):
                continue
                
            job_id = extract_job_id(full_link)
            if job_id in seen_jobs:
                continue
            
            found_count += 1
            message = f"🚨 *NHS Job Found!*\n\n🏥 *{site['name']}*\n📋 *Title:* {title}\n🔗 *Apply:* {full_link}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
        
        print(f"  Found {found_count} new jobs")
        
    except Exception as e:
        print(f"  Error: {e}")

def check_scotland(site, seen_jobs):
    """Check NHS Scotland"""
    print(f"Checking {site['name']}...")
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(site['url'], headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found_count = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'JobDetail' not in href and 'vacancy' not in href.lower():
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
                
            found_count += 1
            message = f"🚨 *Scotland NHS Job!*\n\n🏥 *Title:* {title}\n🔗 *Apply:* {full_link}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
        
        print(f"  Found {found_count} new jobs")
        
    except Exception as e:
        print(f"  Error: {e}")

def check_hscni(site, seen_jobs):
    """Check Northern Ireland"""
    print(f"Checking {site['name']}...")
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(site['url'], headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found_count = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            title = a.get_text(strip=True)
            
            if 'JobDetail' not in href and 'vacancy' not in href.lower():
                continue
                
            if not title or len(title) < 10:
                continue
                
            if not relevant_job(title):
                continue
                
            full_link = urljoin("https://jobs.hscni.net", href)
            job_id = extract_job_id(full_link)
            
            if job_id in seen_jobs:
                continue
                
            found_count += 1
            message = f"🚨 *Northern Ireland Health Job!*\n\n🏥 *Title:* {title}\n🔗 *Apply:* {full_link}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
        
        print(f"  Found {found_count} new jobs")
        
    except Exception as e:
        print(f"  Error: {e}")

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot Started - Focusing on reliable sources")
    print(f"Checking {len(URLS)} job sources every {CHECK_INTERVAL} seconds")
    
    seen_jobs = load_seen()
    print(f"Loaded {len(seen_jobs)} previously seen jobs")
    
    while True:
        print(f"\n{'='*50}")
        print(f"Check started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        for site in URLS:
            if site['type'] == 'nhs_england':
                check_nhs_england(site, seen_jobs)
            elif site['type'] == 'scotland':
                check_scotland(site, seen_jobs)
            elif site['type'] == 'hscni':
                check_hscni(site, seen_jobs)
            
            time.sleep(2)  # Be nice to servers
        
        print(f"\n✅ Check complete. Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
