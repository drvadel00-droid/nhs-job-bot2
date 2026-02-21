import requests
from bs4 import BeautifulSoup
import time
import re

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"

# ---------------- DEBUG FUNCTION ---------------- #
def debug_nhs_england():
    """Debug NHS England to see what's really on the page"""
    print("\n🔍 DEBUG - NHS England Page Structure")
    print("="*60)
    
    url = "https://www.jobs.nhs.uk/candidate/jobs/search?keyword=doctor&sort=posteddate"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"📊 Status Code: {response.status_code}")
        print(f"📦 Response Size: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Print page title
        title = soup.find("title")
        print(f"📌 Page Title: {title.text if title else 'No title'}")
        
        # Look for any job-related content
        print("\n🔎 Searching for job-related elements...")
        
        # Check for common job containers
        containers = soup.find_all(["div", "article", "section"], 
                                  class_=re.compile(r"job|vacancy|result|card|listing", re.I))
        print(f"📦 Found {len(containers)} potential job containers")
        
        # Check for links with job in href
        job_links = soup.find_all("a", href=re.compile(r"job|vacancy|position", re.I))
        print(f"🔗 Found {len(job_links)} links with 'job' in href")
        
        # Check for text containing medical keywords
        page_text = soup.get_text()
        medical_terms = ["doctor", "clinical", "medical", "nurse", "consultant"]
        for term in medical_terms:
            count = page_text.lower().count(term)
            print(f"  '{term}' appears {count} times")
        
        # Print first 500 chars of HTML to see structure
        print("\n📄 First 1000 characters of HTML:")
        print("-"*40)
        print(response.text[:1000])
        print("-"*40)
        
        # Look specifically for the job listing area
        print("\n🎯 Looking for main content area...")
        
        # Try common selectors
        selectors = [
            "main", "article", ".search-results", "#results",
            ".job-results", ".vacancy-list", ".job-list"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"  Found {len(elements)} elements with selector '{selector}'")
        
        # Try to find any links with numbers in them (often job IDs)
        numbered_links = soup.find_all("a", href=re.compile(r"/\d+"))
        print(f"\n🔢 Found {len(numbered_links)} links with numbers in href")
        
        for i, link in enumerate(numbered_links[:5]):
            print(f"  {i+1}. {link.get('href')} - Text: {link.get_text(strip=True)[:50]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def debug_healthjobsuk():
    """Debug HealthJobsUK"""
    print("\n🔍 DEBUG - HealthJobsUK Page Structure")
    print("="*60)
    
    url = "https://www.healthjobsuk.com/jobs/doctor?sort=DateDesc"
    
    try:
        response = requests.get(url, timeout=15)
        print(f"📊 Status Code: {response.status_code}")
        print(f"📦 Response Size: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("title")
        print(f"📌 Page Title: {title.text if title else 'No title'}")
        
        # Look for job cards
        job_cards = soup.find_all(["div", "li"], class_=re.compile(r"job|vacancy|result", re.I))
        print(f"\n📦 Found {len(job_cards)} potential job cards")
        
        # Look for job links
        job_links = soup.find_all("a", href=re.compile(r"/job/|/vacancy/", re.I))
        print(f"🔗 Found {len(job_links)} job links")
        
        # Print first few job links if any
        for i, link in enumerate(job_links[:5]):
            print(f"  {i+1}. {link.get_text(strip=True)[:50]} -> {link.get('href')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def debug_scotland():
    """Debug NHS Scotland"""
    print("\n🔍 DEBUG - NHS Scotland Page Structure")
    print("="*60)
    
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    
    try:
        response = requests.get(url, timeout=15)
        print(f"📊 Status Code: {response.status_code}")
        print(f"📦 Response Size: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("title")
        print(f"📌 Page Title: {title.text if title else 'No title'}")
        
        # Look for job links
        job_links = soup.find_all("a", href=re.compile(r"JobDetail|Vacancy", re.I))
        print(f"🔗 Found {len(job_links)} job links")
        
        for i, link in enumerate(job_links[:5]):
            print(f"  {i+1}. {link.get_text(strip=True)[:50]} -> {link.get('href')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def debug_hscni():
    """Debug Northern Ireland"""
    print("\n🔍 DEBUG - Northern Ireland Page Structure")
    print("="*60)
    
    url = "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0"
    
    try:
        response = requests.get(url, timeout=15)
        print(f"📊 Status Code: {response.status_code}")
        print(f"📦 Response Size: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("title")
        print(f"📌 Page Title: {title.text if title else 'No title'}")
        
        # Look for job links
        job_links = soup.find_all("a", href=re.compile(r"JobDetail|Vacancy", re.I))
        print(f"🔗 Found {len(job_links)} job links")
        
        for i, link in enumerate(job_links[:5]):
            print(f"  {i+1}. {link.get_text(strip=True)[:50]} -> {link.get('href')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

# ---------------- MAIN DEBUG ---------------- #
def main():
    print("🚀 NHS JOB BOT - DEEP DEBUG MODE")
    print("This will show us exactly what each site returns")
    print("="*60)
    
    debug_hscni()          # Test Northern Ireland (was working)
    print("\n" + "="*60)
    time.sleep(2)
    
    debug_nhs_england()    # Test NHS England (showing 0)
    print("\n" + "="*60)
    time.sleep(2)
    
    debug_healthjobsuk()   # Test HealthJobsUK
    print("\n" + "="*60)
    time.sleep(2)
    
    debug_scotland()       # Test Scotland
    
    print("\n" + "="*60)
    print("✅ DEBUG COMPLETE")
    print("Please share this output so I can see the actual page structures")

if __name__ == "__main__":
    main()
