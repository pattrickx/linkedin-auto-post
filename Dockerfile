FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
       ca-certificates \
       git \
       libglib2.0-0 \
       libnss3 \
       libgconf-2-4 \
       libatk1.0-0 \
       libatk-bridge2.0-0 \
       libcups2 \
       libdbus-1-3 \
       libdrm2 \
       libexpat1 \
       libgbm1 \
       libgtk-3-0 \
       libnspr4 \
       libx11-6 \
       libx11-xcb1 \
       libxcb1 \
       libxcomposite1 \
       libxdamage1 \
       libxext6 \
       libxfixes3 \
       libxkbcommon0 \
       libxrandr2 \
       xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
