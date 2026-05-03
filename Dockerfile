FROM python:3.11-slim

# Install system dependencies for Chromium
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 wget && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the browser during the build
RUN playwright install chromium
RUN pip uninstall playwright-stealth -y
RUN pip install playwright-stealth==1.0.6
RUN playwright install chromium && playwright install-deps chromium

COPY . .

# Force Python to not buffer the output so you see logs instantly
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
