import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300  # 5 minutes (be nice to servers)

# Updated URLs with actual job listing pages
URLS = [
    # NHS Jobs England - Updated format
    "https://www.jobs.nhs.uk/candidate/search?keyword=doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=junior+doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=foundation&sort=publicationDateDesc",
    
    # HealthJobsUK - Will handle POST separately
    "HEALTHJOBS_POST",  # Special marker
    
    # Northern Ireland - Actual search URL
    "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0",
    
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",
]

# Trust-specific job listing pages (actual job boards)
TRUST_JOB_PAGES = [
    "https://www.newcastle-hospitals.nhs.uk/jobs/",  # Corrected
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

# [Keep your existing filters and utils - MEDICAL_SPECIALTIES, GRADE_KEYWORDS, etc.]

def check_site(url, seen_jobs):
    print(f"Checking {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        
        # Special handling for POST requests
        if url == "HEALTHJOBS_POST":
            return check_healthjobsuk_post(seen_jobs)
        
        # Special handling for different sites
        if "jobs.hscni.net" in url:
            return check_hscni(url, seen_jobs)
        elif "apply.jobs.scot.nhs.uk" in url:
            return check_scotland(seen_jobs)
        elif "jobs.nhs.uk" in url:
            return check_nhs_england(url, seen_jobs)
        else:
            return check_trust_site(url, seen_jobs)
            
    except Exception as e:
        print(f"Error checking {url}: {e}")

def check_nhs_england(url, seen_jobs):
    """Special handler for NHS Jobs England"""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # NHS Jobs uses specific job card classes
        job_cards = soup.find_all("div", class_=re.compile("job-card|vacancy|result"))
        
        for card in job_cards:
            # Try different selectors for job links
            link_tag = card.find("a", href=re.compile(r"/job/|/vacancy/|/detail/"))
            if not link_tag:
                continue
                
            title = link_tag.get_text(strip=True)
            if not title:
                continue
                
            link = urljoin("https://www.jobs.nhs.uk", link_tag["href"])
            
            if not relevant_job(title):
                continue
                
            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *NHS Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {link}"
            print(message + "\n")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error in NHS England check: {e}")

def check_trust_site(url, seen_jobs):
    """Generic handler for trust websites"""
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Common job link patterns
        job_patterns = [
            r"/job/", r"/vacancy/", r"/careers/", r"/opportunity/",
            r"/position/", r"/role/", r"/detail/", r"/job-detail"
        ]
        
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
            print(message + "\n")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error checking trust site {url}: {e}")

def check_hscni(url, seen_jobs):
    """Northern Ireland specific handler"""
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for job items (adjust selectors based on actual HTML)
        job_items = soup.find_all("div", class_=re.compile("job|vacancy|result"))
        
        for item in job_items:
            link_tag = item.find("a", href=True)
            if not link_tag:
                continue
                
            title = link_tag.get_text(strip=True)
            if not title:
                continue
                
            link = urljoin("https://jobs.hscni.net", link_tag["href"])
            
            if not relevant_job(title):
                continue
                
            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *NI Health Job Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {link}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error checking HSCNI: {e}")

def check_healthjobsuk_post(seen_jobs):
    """Handle POST request for HealthJobsUK"""
    url = "https://www.healthjobsuk.com/job_list"
    
    # Form data (adjust based on actual form)
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
        
        # Parse results (adjust selectors based on actual HTML)
        job_rows = soup.find_all("tr", class_=re.compile("job|vacancy|result"))
        
        for row in job_rows:
            link_tag = row.find("a", href=True)
            if not link_tag:
                continue
                
            title = link_tag.get_text(strip=True)
            link = urljoin("https://www.healthjobsuk.com", link_tag["href"])
            
            if not relevant_job(title):
                continue
                
            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue
                
            message = f"🚨 *HealthJobsUK Found!*\n\n🏥 *Title:* {title}\n🔗 *Apply here:* {link}"
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
            
    except Exception as e:
        print(f"Error checking HealthJobsUK: {e}")

# Update the main loop to use the new check_site
def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            check_site(url, seen_jobs)
            time.sleep(2)  # Be nice to servers between checks
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
