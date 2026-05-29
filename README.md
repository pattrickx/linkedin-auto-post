# linkedin-auto-post API

FastAPI-based API to receive one or more URLs, extract articles and Markdown content, and return everything as JSON.

The project is organized into two main parts:

* HTTP API in `app.py`
* extraction engine in `src/extraction/`

## What the API does

* Receives one or more URLs via POST
* Extracts articles and structured data from the page
* Optionally crawls article content in Markdown format
* Returns JSON responses
* Exposes a healthcheck endpoint for orchestration and monitoring
* Includes basic SSRF protection and local host blocking

## Endpoints

* `GET /`

  * Basic service information
* `GET /health`

  * Simple healthcheck
* `POST /extract`

  * Processes a list of URLs
* `POST /extract/url`

  * Processes a single URL
* `POST /extract/stream`

  * Progressive response using NDJSON
* `GET /docs`

  * Swagger UI
* `GET /redoc`

  * ReDoc
* `GET /openapi.json`

  * OpenAPI specification

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

* Python 3.11+
* OpenAI API key for the LLM extraction step
* Browser dependencies for `crawl4ai` when using Markdown content crawling

## Local installation

1. Create and activate the virtual environment.
2. Install dependencies.
3. Configure the `.env` file.
4. Start the application with Uvicorn.

Example:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows Git Bash: source .venv/Scripts/activate
uv pip install -r requirements.txt
```

Minimal `.env` file:

```env
OPENAI_API_KEY=your_key_here
APP_NAME=linkedin-auto-post-api
APP_VERSION=2.0.0
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

Or use Portainer with the repository’s `docker-compose.yml`.

## API Usage

### Extract multiple URLs

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com", "https://example.org"],
    "crawl_content": true,
    "max_articles": 10
  }'
```

### Extract a single URL

```bash
curl -X POST "http://localhost:8000/extract/url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "crawl_content": true,
    "max_articles": 10
  }'
```

### Streaming response

```bash
curl -N -X POST "http://localhost:8000/extract/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com"],
    "crawl_content": true
  }'
```

## Swagger / OpenAPI

Interactive documentation is available at:

* `http://localhost:8000/docs`
* `http://localhost:8000/redoc`

The project already exposes:

* `title`
* `version`
* `description`
* `openapi.json`

This ensures Swagger works correctly with FastAPI.

## Security

The API includes basic validation:

* only accepts `http` and `https`
* blocks `localhost`, `127.0.0.1`, `0.0.0.0`, and `::1`
* supports allowlists via `ALLOWED_HOSTS`

Example:

```env
ALLOWED_HOSTS=example.com,example.org
```

If `ALLOWED_HOSTS` is empty, the API accepts public hosts while still blocking local addresses.

## Useful configuration

```env
APP_NAME=linkedin-auto-post-api
APP_VERSION=2.0.0
DEFAULT_MODEL=gpt-4o-mini
DEFAULT_CRAWL_CONTENT=true
DEFAULT_MAX_ARTICLES=20
MAX_URLS=25
CORS_ORIGINS=*
ALLOWED_HOSTS=
```

## Notes

Extraction depends on external calls to the LLM provider and, when `crawl_content=true`, on the browser/headless environment required by `crawl4ai`.

If you'd like, in the next step I can also add automated tests for the endpoints and SSRF validation rules.
