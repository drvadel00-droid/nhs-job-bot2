import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120  # seconds

# ---------------- UPDATED URLS (FIXED) ---------------- #
URLS = [
    # HealthJobsUK - Keep as is
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",
    
    # NHS Jobs England - UPDATED URL FORMAT
    "https://www.jobs.nhs.uk/candidate/search?keyword=doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=foundation&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=junior+doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=clinical+fellow&sort=publicationDateDesc",
    
    # Northern Ireland
    "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0",
    
    # Scotland NHS jobs
    "https://apply.jobs.scot.nhs.uk/Home/Search",
    
    # Remove problematic trust sites or keep but we'll handle them differently
]

# ---------------- FILTER LOGIC ---------------- #
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
        print("Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": escape_telegram(message), "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print("Telegram send error:", e)

def extract_job_id(link):
    match = re.search(r'/(\d+)$|JobId=(\d+)|vacancy/(\d+)|job/(\d+)', link)
    if match:
        return next(g for g in match.groups() if g is not None)
    return link

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in title_lower for sp in MEDICAL_SPECIALTIES):
        # Allow if it has "doctor" in title
        if "doctor" in title_lower:
            return any(gr in title_lower for gr in GRADE_KEYWORDS)
        return False
    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False
    return True

def normalize_link(link, base):
    if link.startswith("/"):
        return base + link
    if link.startswith("http"):
        return link
    return base + "/" + link

# ---------------- SITE CHECK ---------------- #
def check_site(url, seen_jobs):
    print(f"\n🔍 Checking {url}")
    
    # Special handling for HealthJobsUK (POST request)
    if "healthjobsuk.com" in url and "job_list" in url:
        return check_healthjobsuk(seen_jobs)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Get base URL for joining relative links
        base_url = re.match(r"(https?://[^/]+)", url).group(1)
        
        # Look for job links - different patterns for different sites
        job_links = []
        
        if "jobs.nhs.uk" in url:
            # NHS Jobs specific selectors
            job_links = soup.find_all("a", href=re.compile(r"/job/|/vacancy/|/candidate/job/"))
        elif "hscni.net" in url:
            # Northern Ireland specific
            job_links = soup.find_all("a", href=re.compile(r"JobDetail|Vacancy"))
        elif "scot.nhs.uk" in url:
            # Scotland specific
            job_links = soup.find_all("a", href=re.compile(r"JobDetail|Vacancy"))
        else:
            # Generic job link patterns
            job_links = soup.find_all("a", href=re.compile(r"job|vacancy|career|position|detail", re.I))
        
        # If no job links found with patterns, try all links with filtering
        if not job_links:
            all_links = soup.find_all("a", href=True)
            for a in all_links:
                text = a.get_text(strip=True)
                href = a["href"]
                # Check if link text looks like a job title
                if len(text) > 15 and any(k in text.lower() for k in ["doctor", "medical", "clinical", "fy", "ct", "st"]):
                    job_links.append(a)
        
        found_count = 0
        for a in job_links:
            title = a.get_text(strip=True)
            link = a["href"]
            
            if not title or len(title) < 10:
                continue
            
            # Skip navigation links
            if any(skip in title.lower() for skip in ["home", "contact", "about", "search", "login", "register"]):
                continue
            
            if not relevant_job(title):
                continue
            
            # Normalize the link
            if link.startswith("http"):
                full_link = link
            else:
                full_link = urljoin(url, link)
            
            job_id = extract_job_id(full_link)
            if job_id in seen_jobs:
                continue
            
            found_count += 1
            message = f"🚨 *NHS Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"  ✅ Found: {title[:50]}...")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
        
        print(f"  📊 Found {found_count} new jobs on this site")
        
    except Exception as e:
        print(f"  ❌ Error checking {url}: {e}")

def check_healthjobsuk(seen_jobs):
    """Special handler for HealthJobsUK POST requests"""
    print("  📝 Using POST request for HealthJobsUK")
    
    url = "https://www.healthjobsuk.com/job_list"
    
    # Form data
    data = {
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        found_count = 0
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
            
            found_count += 1
            message = f"🚨 *HealthJobsUK Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {full_link}"
            print(f"  ✅ Found: {title[:50]}...")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
        
        print(f"  📊 Found {found_count} new jobs on HealthJobsUK")
        
    except Exception as e:
        print(f"  ❌ Error checking HealthJobsUK: {e}")

# ---------------- MAIN LOOP ---------------- #
def main():
    print("🚀 NHS Job Bot - Restored Version")
    print(f"Checking {len(URLS)} sources every {CHECK_INTERVAL} seconds")
    
    seen_jobs = load_seen()
    print(f"📚 Loaded {len(seen_jobs)} previously seen jobs")
    
    while True:
        print(f"\n{'='*60}")
        print(f"🕐 Check started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        for url in URLS:
            check_site(url, seen_jobs)
            time.sleep(2)  # Be nice to servers
        
        print(f"\n✅ Check complete. Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
