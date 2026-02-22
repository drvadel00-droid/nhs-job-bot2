#!/bin/bash
# Install Playwright browsers
python -m playwright install chromium
pip install selenium webdriver-manager requests
# Start the bot
python main.py
