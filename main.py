# ---------------- DEBUG VERSION ---------------- #
def debug_check_site(url, seen_jobs):
    """Debug version that shows what we're actually getting"""
    print(f"\n🔍 DEBUG - Checking: {url}")
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=15)
        
        print(f"Status code: {response.status_code}")
        print(f"Response size: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Print page title
        title_tag = soup.find("title")
        print(f"Page title: {title_tag.get_text() if title_tag else 'No title'}")
        
        # Find ALL links on the page
        all_links = soup.find_all("a", href=True)
        print(f"Total links found: {len(all_links)}")
        
        # Show first 10 links to see structure
        print("\nFirst 10 links on page:")
        for i, a in enumerate(all_links[:10]):
            href = a.get("href", "")
            text = a.get_text(strip=True)[:50]
            print(f"  {i+1}. Text: '{text}' -> URL: {href[:100]}")
        
        # Look for potential job links
        potential_jobs = []
        for a in all_links:
            href = a.get("href", "")
            text = a.get_text(strip=True)
            
            # Check if it might be a job
            if len(text) > 15 and any(k in text.lower() for k in ["doctor", "medical", "clinical", "fy", "ct", "st", "registrar"]):
                potential_jobs.append((text, href))
        
        print(f"\nPotential job links found: {len(potential_jobs)}")
        for text, href in potential_jobs[:5]:  # Show first 5
            print(f"  📋 Job: {text[:100]}... -> {href[:50]}...")
        
        return len(potential_jobs)
        
    except Exception as e:
        print(f"Error: {e}")
        return 0

# ---------------- TEMPORARY MAIN LOOP FOR DEBUGGING ---------------- #
def main():
    print("🚀 NHS Job Bot - DEBUG MODE")
    print("Checking each URL once to see what's being received...\n")
    
    seen_jobs = set()  # Empty set for debugging
    
    for url in URLS:
        job_count = debug_check_site(url, seen_jobs)
        print(f"\n✅ Found {job_count} potential jobs on {url}")
        print("-" * 50)
        time.sleep(1)
    
    print("\n🔧 Debug complete! Now we need to update the selectors based on what we saw.")
    print("Copy the output above and share it with me so I can help fix the selectors.")

if __name__ == "__main__":
    main()
