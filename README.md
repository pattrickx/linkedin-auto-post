# Web News Extractor

A FastAPI service for extracting content from web pages and returning structured results in JSON or Markdown. It is designed for automation, ingestion pipelines, site monitoring.

This API has two primary use cases:
- extract frontpages/listings and identify related articles
- extract a single page and return the full content in Markdown

It is a good fit for content automation, scraping pipelines, publishing workflows, monitoring jobs.

## What the API does

- Receives one or more URLs via POST
- Extracts articles and metadata from frontpages/listings
- Extracts a single page and returns the content in Markdown
- Optionally crawls article content in Markdown
- Returns consistent JSON responses for integration

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


## Usage examples

### Extract multiple URLs with curl

```bash
curl -X POST "<your-endpoint>/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com", "https://example.org"],
    "max_articles": 10
  }'
```

### Extract a single page as Markdown with curl

```bash
curl -X POST "<your-endpoint>/extract/url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/article"
  }'
```

### Streaming response with curl

```bash
curl -N -X POST "<your-endpoint>/extract/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com"]
  }'
```

### Extract multiple URLs with Python

```python
import requests

payload = {
    "urls": ["https://example.com", "https://example.org"],
    "max_articles": 10,
}

response = requests.post("<your-endpoint>/extract", json=payload, timeout=120)
response.raise_for_status()
print(response.json())
```

### Extract a single page as Markdown with Python

```python
import requests

payload = {
    "url": "https://example.com/article"
}

response = requests.post("<your-endpoint>/extract/url", json=payload, timeout=120)
response.raise_for_status()
print(response.json())
```

## Swagger / OpenAPI

Interactive documentation:

- `<your-endpoint>/docs`
- `<your-endpoint>/redoc`

The application is configured so Swagger works correctly with FastAPI:
- title
- description
- version
- docs_url
- redoc_url
- openapi_url

