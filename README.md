Here’s a clean technical documentation for your script, organized like a README / developer documentation.

---

# NHS Job Bot Scraper Documentation

## Overview

This script is an **asynchronous NHS job monitoring bot** that:

* Scrapes multiple UK medical job boards:

  * HealthJobsUK
  * NHS Jobs England
  * HSCNI (Northern Ireland)
  * NHS Scotland
* Filters jobs based on:

  * Medical specialties
  * Training grades
  * Excluded senior/non-medical roles
* Detects newly posted jobs
* Sends alerts to a Telegram channel/group
* Persists previously seen jobs to avoid duplicates

Built with:

* `asyncio`
* `playwright`
* `BeautifulSoup`
* `aiohttp`

---

# Architecture

```text
main()
 ├── telegram_consumer()
 ├── run_cycle()
 │    ├── _site_with_timeout()
 │    │    └── check_site()
 │    │         ├── create_context()
 │    │         ├── goto_with_retry()
 │    │         ├── parser()
 │    │         ├── filter logic
 │    │         └── enqueue_telegram()
 └── loop forever
```

---

# Configuration

## Telegram Settings

```python
BOT_TOKEN
CHAT_ID
```

Used for Telegram notifications.

---

## Timing Configuration

| Variable                 | Description                             |
| ------------------------ | --------------------------------------- |
| `CHECK_INTERVAL`         | Delay between scraping cycles (seconds) |
| `PAGE_TIMEOUT`           | Max page navigation timeout             |
| `DETAIL_TIMEOUT`         | Timeout for detail pages                |
| `SITE_HARD_LIMIT`        | Hard timeout per URL task               |
| `TELEGRAM_SEND_INTERVAL` | Telegram rate limiting                  |

Example:

```python
CHECK_INTERVAL = 120
```

Runs every 2 minutes.

---

## Browser Configuration

| Variable                   | Description                       |
| -------------------------- | --------------------------------- |
| `MAX_CONCURRENT_BROWSERS`  | Max parallel browser sessions     |
| `PLAYWRIGHT_RECYCLE_EVERY` | Restart Playwright after N cycles |

Purpose:

* Prevent memory leaks
* Avoid browser zombie processes

---

# Supported Sites

## 1. HealthJobsUK

URLs:

```python
https://www.healthjobsuk.com/job_list...
```

Parser:

```python
parse_healthjobsuk()
```

Extracts:

* title
* grade
* employer
* location
* speciality
* salary

---

## 2. NHS Jobs England

URL:

```python
https://www.jobs.nhs.uk/candidate/search/results...
```

Parser:

```python
parse_nhsjobs()
```

Extracts:

* title
* employer
* location
* salary
* closing date
* contract type

---

## 3. HSCNI

URL:

```python
https://jobs.hscni.net/Search
```

Parser:

```python
parse_hscni()
```

Extracts:

* title
* reference
* salary
* location
* contract
* closing date

---

## 4. Scotland NHS

URL:

```python
https://apply.jobs.scot.nhs.uk/Home/Job
```

Parser:

```python
parse_scotland()
```

Extracts:

* title
* salary
* employer
* department
* location
* hours
* closing date
* reference

---

# Filtering Logic

## Included Medical Specialties

```python
MEDICAL_SPECIALTIES
```

Examples:

* medicine
* surgery
* cardiology
* respiratory
* ICU
* neurology

A job must contain at least one specialty keyword.

---

## Allowed Grades

```python
GRADE_KEYWORDS
```

Examples:

* FY1
* FY2
* CT1–CT3
* ST1–ST3
* registrar
* trust grade
* clinical fellow

A job must contain at least one grade keyword.

---

## Excluded Roles

```python
EXCLUDE_KEYWORDS
```

Examples:

* consultant
* nurse
* admin
* pharmacist
* therapist
* director

If any excluded keyword exists → job rejected.

---

## Filter Function

```python
relevant_job(title)
```

Logic:

```python
return (
    no excluded keywords
    AND has specialty
    AND has allowed grade
)
```

---

# Seen Jobs Persistence

File:

```text
seen_jobs.txt
```

Functions:

## Load existing jobs

```python
load_seen()
```

Returns:

```python
set(job_ids)
```

---

## Save new job

```python
async_save_seen(job_id)
```

Appends to file.

Protected by:

```python
_seen_lock
```

to avoid race conditions.

---

# Telegram Notification System

Uses queue-based async sender.

Queue:

```python
_tg_queue
```

Producer:

```python
enqueue_telegram()
```

Consumer:

```python
telegram_consumer()
```

Features:

* Fully async
* Rate-limited
* Handles Telegram 429 retry_after
* Retries failed sends

---

## Telegram Message Format

Site-specific formatting:

* `format_nhsjobs()`
* `format_healthjobsuk()`
* `format_hscni()`
* `format_scotland()`

Example output:

```text
🚨 NEW NHS JOB — England

🏥 Clinical Fellow in Cardiology
🏢 NHS Trust
📍 London
💷 £43,923
📅 Closes: 25 May 2026
🔗 https://...
```

---

# Browser Stealth / Anti-Bot Protection

Uses:

```python
playwright_stealth
```

Additional stealth:

```python
navigator.webdriver = undefined
navigator.plugins spoofed
navigator.languages spoofed
window.chrome spoofed
```

Randomization:

* viewport
* user agent
* mouse movement
* scrolling
* startup delay

Functions:

```python
human_scroll()
random_mouse_move()
```

Purpose:

* Reduce bot detection

---

# Navigation Retry Strategy

Function:

```python
goto_with_retry()
```

Strategies:

1. `domcontentloaded`
2. `commit`

Reason:

* Some sites deliberately stall bots

Behavior:

* Retry 2 times
* 2-second pause between attempts

Handles:

* timeout
* 403
* HTTP failures

---

# Concurrency Model

Semaphore:

```python
_browser_sem
```

Limits concurrent browsers.

Example:

```python
MAX_CONCURRENT_BROWSERS = 3
```

Only 3 sites scraped simultaneously.

---

# Timeout Protection

Each site wrapped with:

```python
asyncio.wait_for()
```

Function:

```python
_site_with_timeout()
```

Hard limit:

```python
SITE_HARD_LIMIT = 300
```

If exceeded:

```text
Hard timeout hit — skipping
```

Prevents one site hanging the entire cycle.

---

# Main Execution Loop

## Startup

```python
main()
```

Steps:

1. Raise process thread limits
2. Load seen jobs
3. Start Telegram consumer
4. Initialize semaphore

---

## Continuous Loop

```python
while True:
```

Runs:

```python
async_playwright()
```

Inside:

```python
PLAYWRIGHT_RECYCLE_EVERY cycles
```

After N cycles:

* close Playwright
* garbage collect
* restart browser stack

Purpose:

* memory cleanup
* avoid browser leaks

---

# Error Handling

Levels:

## Entry-level

Inside each job:

```python
try/except
```

Bad entry won't kill site scraping.

---

## Site-level

Inside:

```python
check_site()
```

Bad site won't kill cycle.

---

## Cycle-level

Inside:

```python
run_cycle()
```

Bad cycle won't kill bot.

---

## Global loop

Bot runs forever.

---

# Output Logs

Example logs:

```text
[14:33:10] 🚀 NHS JOB BOT STARTED
[14:33:11] Loaded 421 jobs
[14:33:12] Checking: https://...
[14:33:20] NEW JOB: Clinical Fellow
[14:33:21] Telegram sent
```

---

# Dependencies

Install:

```bash
pip install playwright aiohttp beautifulsoup4 fake-useragent playwright-stealth
playwright install chromium
```

---

# Files

## Required

```text
seen_jobs.txt
```

Auto-created.

---

# How to Run

```bash
python bot.py
```

---

# Key Features Summary

✅ Async scraping
✅ Multi-site support
✅ Telegram alerts
✅ Duplicate prevention
✅ Human-like browser behavior
✅ Retry logic
✅ Timeout protection
✅ Browser recycling
✅ Persistent seen jobs

---

# Potential Improvements

Recommended upgrades:

## Security

Move secrets to environment variables:

```python
BOT_TOKEN = os.getenv("BOT_TOKEN")
```

instead of hardcoding token.

---

## Storage

Replace:

```text
seen_jobs.txt
```

with SQLite for scalability.

---

## Logging

Use Python logging module instead of print.

---

## Deployment

Good platforms:

* Docker
* Railway
* Render
* VPS

---

## Monitoring

Add heartbeat Telegram message:

```text
Bot alive
```

every few hours.

---

# Author Notes

This bot is optimized for:

* long-running scraping
* anti-bot resistance
* low duplicate notifications
* unattended deployment

Suitable for 24/7 NHS medical job monitoring.

---
