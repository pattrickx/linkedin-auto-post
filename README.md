# linkedin-auto-post API

A FastAPI service for extracting content from web pages and returning structured results in JSON or Markdown. It is designed for automation, ingestion pipelines, site monitoring, and RapidAPI-style marketplace integrations.

This API has two primary use cases:
- extract frontpages/listings and identify related articles
- extract a single page and return the full content in Markdown

It is a good fit for content automation, scraping pipelines, publishing workflows, monitoring jobs, and integrations with RapidAPI, Portainer, or similar orchestration tools.

## What the API does

- Receives one or more URLs via POST
- Extracts articles and metadata from frontpages/listings
- Extracts a single page and returns the content in Markdown
- Optionally crawls article content in Markdown
- Returns consistent JSON responses for integration
- Exposes a healthcheck endpoint for monitoring and orchestration
- Includes basic URL validation and simple local SSRF protection

## Endpoints

- GET /
  - Basic service information
- GET /health
  - Simple healthcheck
- POST /extract
  - Processes a list of URLs and returns extracted articles
- POST /extract/url
  - Processes a single URL and returns the page content in Markdown
- POST /extract/stream
  - Returns progressive events in NDJSON
- GET /docs
  - Swagger UI
- GET /redoc
  - ReDoc
- GET /openapi.json
  - OpenAPI specification

## Endpoint behavior summary

### /extract
Use this when you want to send one or more frontpage/listing URLs and receive the articles found, with optional Markdown content for each article.

### /extract/url
Use this when you want to send a specific page URL and receive only that page content in Markdown, without article discovery logic.

## Project structure

```text
.
├── app.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── src/
    └── extraction/
        ├── __init__.py
        └── service.py
```

## Requirements

- Python 3.11+
- OpenAI API key for the LLM extraction step
- Browser dependencies for `crawl4ai` when using content crawling

## Local installation

1. Create and activate a virtual environment.
2. Install dependencies.
3. Configure the `.env` file.
4. Start the application with Uvicorn.

Example:

```bash
python -m venv .venv
source .venv/Scripts/activate
uv pip install -r requirements.txt
```

Minimal `.env` file:

```env
OPENAI_API_KEY=your_key_here
APP_NAME=linkedin-auto-post-api
APP_VERSION=2.2.0
```

Run locally:

```bash
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Docker

Build and run:

```bash
docker compose up -d --build
```

Or use Portainer with the repository’s `docker-compose.yml` file.

## Usage examples

### Extract multiple URLs with curl

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com", "https://example.org"],
    "crawl_content": true,
    "max_articles": 10
  }'
```

### Extract a single page as Markdown with curl

```bash
curl -X POST "http://localhost:8000/extract/url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/article",
    "model": "gpt-5.4-mini"
  }'
```

### Streaming response with curl

```bash
curl -N -X POST "http://localhost:8000/extract/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com"],
    "crawl_content": true
  }'
```

### Extract multiple URLs with Python

```python
import requests

payload = {
    "urls": ["https://example.com", "https://example.org"],
    "crawl_content": True,
    "max_articles": 10,
}

response = requests.post("http://localhost:8000/extract", json=payload, timeout=120)
response.raise_for_status()
print(response.json())
```

### Extract a single page as Markdown with Python

```python
import requests

payload = {
    "url": "https://example.com/article",
    "model": "gpt-5.4-mini",
}

response = requests.post("http://localhost:8000/extract/url", json=payload, timeout=120)
response.raise_for_status()
print(response.json())
```

## Swagger / OpenAPI

Interactive documentation:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

The application is configured so Swagger works correctly with FastAPI:
- title
- description
- version
- docs_url
- redoc_url
- openapi_url

## Security

The API includes basic validation:

- only accepts `http` and `https`
- blocks `localhost`, `127.0.0.1`, `0.0.0.0`, and `::1`
- supports allowlisting through `ALLOWED_HOSTS`

Example:

```env
ALLOWED_HOSTS=example.com,example.org
```

If `ALLOWED_HOSTS` is empty, the API accepts public hosts while still blocking local addresses.

## Useful configuration

```env
APP_NAME=linkedin-auto-post-api
APP_VERSION=2.2.0
DEFAULT_MODEL=gpt-4o-mini
DEFAULT_CRAWL_CONTENT=true
DEFAULT_MAX_ARTICLES=20
MAX_URLS=25
CORS_ORIGINS=*
ALLOWED_HOSTS=
```
