import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= CONFIG ================= #

CHECK_INTERVAL = 300  # 5 minutes

URLS = {
    "nhs_jobs": "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "healthjobsuk": "https://www.healthjobsuk.com/job_list",
    "hscni": "https://jobs.hscni.net/Search?SearchCatID=0",
    "nhs_scotland": "https://apply.jobs.scot.nhs.uk/Home/Search"
}

# ================= DRIVER SETUP ================= #

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service()
    return webdriver.Chrome(service=service, options=chrome_options)

# ================= SCRAPER ================= #

def scrape_nhs_jobs(driver):
    print("\n🔎 NHS Jobs...")
    driver.get(URLS["nhs_jobs"])

    # wait for any job link to load
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )

    links = driver.find_elements(By.TAG_NAME, "a")

    print(f"Found {len(links)} links on NHS Jobs page")
    for link in links:
        title = link.text.strip()
        href = link.get_attribute("href")
        if title and href:
            print(f"Title: {title}\nLink: {href}\n")

def scrape_healthjobsuk(driver):
    print("\n🔎 HealthJobsUK...")
    driver.get(URLS["healthjobsuk"])

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )

    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"Found {len(links)} links on HealthJobsUK page")
    for link in links:
        title = link.text.strip()
        href = link.get_attribute("href")
        if title and href:
            print(f"Title: {title}\nLink: {href}\n")

def scrape_hscni(driver):
    print("\n🔎 HSCNI (Northern Ireland)...")
    driver.get(URLS["hscni"])

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )

    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"Found {len(links)} links on HSCNI page")
    for link in links:
        title = link.text.strip()
        href = link.get_attribute("href")
        if title and href:
            print(f"Title: {title}\nLink: {href}\n")

def scrape_scotland(driver):
    print("\n🔎 NHS Scotland...")
    driver.get(URLS["nhs_scotland"])

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )

    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"Found {len(links)} links on NHS Scotland page")
    for link in links:
        title = link.text.strip()
        href = link.get_attribute("href")
        if title and href:
            print(f"Title: {title}\nLink: {href}\n")

# ================= MAIN LOOP ================= #

def main():
    driver = get_driver()
    try:
        scrape_nhs_jobs(driver)
        scrape_healthjobsuk(driver)
        scrape_hscni(driver)
        scrape_scotland(driver)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
