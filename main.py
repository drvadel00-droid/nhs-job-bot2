import hashlib

def scrape_healthjobsuk(driver, seen_jobs):
    print("🔎 Scanning HealthJobsUK (Medical/Dental)...")
    
    # We use the specific Medical/Dental path to filter out non-doctor roles at the source
    url = "https://www.healthjobsuk.com/job_list/s2/Medical_Dental"
    
    try:
        driver.get(url)
        
        # 1. Wait for the page container to exist
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # 2. DISMISS COOKIES (Crucial: The overlay can block Selenium from "seeing" links)
        try:
            cookie_button = driver.find_element(By.ID, "ccc-notify-accept")
            cookie_button.click()
            time.sleep(1)
        except:
            pass 

        # 3. HUMAN SCROLL (Triggers the JavaScript to load the actual job items)
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1.5)

        # 4. CAPTURE TITLES AND LINKS
        # Updated 2026 Selectors: They use 'job-result-item' wrappers
        items = driver.find_elements(By.CSS_SELECTOR, ".job-result-item, .job-item")
        
        new_found = 0
        for item in items:
            try:
                # Find the link inside the item
                link_el = item.find_element(By.CSS_SELECTOR, "h3 a, a.jobTitle")
                title = link_el.text.strip()
                href = link_el.get_attribute("href")

                if not title or not href:
                    continue

                if relevant_job(title):
                    # Use a hash of the URL as a unique ID
                    job_id = hashlib.md5(href.encode()).hexdigest()
                    
                    if job_id not in seen_jobs:
                        msg = f"🚨 *HealthJobsUK: New Vacancy*\n\n🏥 {title}\n🔗 {href}"
                        print(f"✨ Found: {title}")
                        send_telegram(msg)
                        save_seen(job_id)
                        seen_jobs.add(job_id)
                        new_found += 1
            except:
                continue
                
        print(f"✅ HealthJobsUK Scan Complete. New jobs: {new_found}")

    except Exception as e:
        print(f"❌ HealthJobsUK Error: {e}")
