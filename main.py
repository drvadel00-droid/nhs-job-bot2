import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.jobs.nhs.uk/candidate/search/results?staffGroup=MEDICAL_AND_DENTAL&language=en"

def get_jobs(url):
    page = 1
    all_jobs = []

    while True:
        print(f"Fetching page {page}...")
        response = requests.get(f"{url}&page={page}", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        
        job_cards = soup.find_all("div", class_="vacancy-card")
        if not job_cards:
            print("No more jobs found.")
            break

        for job in job_cards:
            title_tag = job.find("a", href=True)
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = "https://www.jobs.nhs.uk" + title_tag["href"]
                all_jobs.append((title, link))
                print(f"🏥 {title}\n🔗 {link}\n")

        page += 1

    print(f"Total jobs found: {len(all_jobs)}")
    return all_jobs

get_jobs(BASE_URL)
