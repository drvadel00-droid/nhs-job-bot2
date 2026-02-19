#!/bin/bash
# Install Playwright browsers
python -m playwright install chromium

# Start the bot
python main.py
