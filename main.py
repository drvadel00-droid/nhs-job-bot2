import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"

# ---------------- URLS ---------------- #
URLS = [
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search?keyword=doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=junior+doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search?keyword=foundation&sort=publicationDateDesc",
    
    # HealthJobsUK - We'll handle separately
    "HEALTHJOBS_POST",
    
    # Northern Ireland
    "https://jobs.hscni.net/Search?Keywords=doctor&CategoryID=0",
    
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",
    
    # Trust sites
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

# ---------------- DEBUG FUNCTION ---------------- #
def debug_check_site(url, index):
    """Debug version that shows what we're actually getting"""
    print(f"\n{'='*60}")
    print(f"🔍 DEBUG [{index+1}/{len(URLS)}] - Checking: {url}")
    print(f"{'='*60}")
    
    try:
        # Special handling for HealthJobsUK
        if url == "HEALTHJOBS_POST":
            print("📝 Special case: HealthJobsUK requires POST request")
            print("Skipping GET request for this URL")
            return
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        print(f"📊 Status code: {response.status_code}")
        print(f"📦 Response size: {len(response.text)} characters")
        print(f"🔄 Final URL after redirects: {response.url}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Print page title
        title_tag = soup.find("title")
        print(f"📌 Page title: {title_tag.get_text() if title_tag else 'No title found'}")
        
        # Check for common error messages
        page_text = soup.get_text().lower()
        if "no results" in page_text or "no jobs" in page_text:
            print("⚠️  Page contains 'no results' or 'no jobs' message")
        if "cookie" in page_text and "consent" in page_text:
            print("🍪 Cookie consent page detected")
        
        # Find ALL links on the page
        all_links = soup.find_all("a", href=True)
        print(f"🔗 Total links found: {len(all_links)}")
        
        # Show first 15 links to see structure
        print("\n📋 First 15 links on page:")
        print("-" * 80)
        for i, a in enumerate(all_links[:15]):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not text:
                text = "[NO TEXT]"
            print(f"  {i+1:2d}. Text: '{text[:50]:50}' -> URL: {href[:60]}")
        
        # Look specifically for job-related links
        print("\n🎯 Searching for job-related links...")
        job_keywords = ["doctor", "medical", "clinical", "fy1", "fy2", "ct1", "st1", 
                       "foundation", "registrar", "specialty", "vacancy", "job", "career"]
        
        potential_jobs = []
        for a in all_links:
            href = a.get("href", "")
            text = a.get_text(strip=True)
            link_text = text.lower()
            
            # Check if link text contains job keywords
            if any(keyword in link_text for keyword in job_keywords):
                potential_jobs.append((text, href))
        
        print(f"📊 Links with job-related text: {len(potential_jobs)}")
        for text, href in potential_jobs[:10]:  # Show first 10
            print(f"  📍 '{text[:70]}'")
            print(f"     -> {href[:80]}")
            print()
        
        # Look for common job listing patterns in URLs
        print("\n🔍 Checking URL patterns...")
        url_patterns = ["/job/", "/vacancy/", "/detail/", "/position/", "JobId=", "jobdetail"]
        pattern_matches = []
        
        for a in all_links:
            href = a.get("href", "").lower()
            text = a.get_text(strip=True)
            if any(pattern in href for pattern in url_patterns) and len(text) > 10:
                pattern_matches.append((text, href))
        
        print(f"📊 Links matching job URL patterns: {len(pattern_matches)}")
        for text, href in pattern_matches[:10]:
            print(f"  🔗 '{text[:50]}'")
            print(f"     -> {href[:80]}")
            print()
        
        # Check for pagination
        pagination = soup.find_all("a", href=True, string=re.compile(r"\d+|next|prev|»|«"))
        if pagination:
            print(f"📑 Pagination links found: {len(pagination)}")
        
        # Check for JavaScript content
        scripts = soup.find_all("script")
        has_json_data = False
        for script in scripts:
            if script.string and ("jobs" in script.string.lower() or "vacancies" in script.string.lower()):
                if "JSON" in script.string or "data" in script.string:
                    has_json_data = True
                    print("💡 Found JavaScript data that might contain jobs")
                    break
        
        print(f"\n{'='*60}")
        print(f"✅ Debug complete for {url}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error checking {url}: {e}")
        import traceback
        traceback.print_exc()

# ---------------- MAIN DEBUG FUNCTION ---------------- #
def main():
    print("🚀 NHS JOB BOT - COMPREHENSIVE DEBUG MODE")
    print(f"Total URLs to check: {len(URLS)}")
    print("="*60)
    
    for i, url in enumerate(URLS):
        debug_check_site(url, i)
        time.sleep(2)  # Be nice to servers
    
    print("\n✨ DEBUG COMPLETE!")
    print("\nPlease copy ALL of the output above and share it with me.")
    print("This will help me identify:")
    print("1. Which sites are blocking/redirecting")
    print("2. The actual HTML structure of each site")
    print("3. Where the job listings are hiding")
    print("4. If we need different approaches for different sites")

if __name__ == "__main__":
    main()
