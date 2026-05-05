FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        curl \
        fonts-noto-cjk \
        fonts-liberation \
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libxrender1 \
        libxkbcommon0 \
        libxshmfence1 \
        libxss1 \
        libxtst6 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libcairo2 \
        libcairo-gobject2 \
        libfontconfig1 \
        libgdk-pixbuf-2.0-0 \
        libgtk-3-0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libasound2 \
        xvfb \
        xdotool \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pydantic \
    cloakbrowser \
    playwright \
    selenium \
    undetected-chromedriver

ENV CLOAKBROWSER_CACHE_DIR=/opt/cloakbrowser
ENV CLOAKBROWSER_AUTO_UPDATE=false
RUN python -m cloakbrowser install

COPY src /app/src
ENV PYTHONPATH=/app/src
ENV BROWSER_SEARCH_CHROME_BINARY=/usr/bin/chromium
ENV BROWSER_SEARCH_PROVIDER_ORDER=cloak,naver
ENV BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC=45
ENV BROWSER_SEARCH_GOOGLE_JITTER_SEC=15
ENV BROWSER_SEARCH_BLOCK_COOLDOWN_SEC=7200

EXPOSE 8765
CMD ["python", "-m", "llm_batch.browser_search.server"]
