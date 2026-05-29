from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.extraction import Article, crawl_article_content, process_frontpages


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "linkedin-auto-post-api"
    app_version: str = "2.2.0"
    default_model: str = "gpt-4o-mini"
    default_crawl_content: bool = True
    default_max_articles: int = 20
    max_urls: int = 25
    cors_origins: str = "*"
    allowed_hosts: str = ""


settings = Settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API para extrair artigos/conteúdo de um ou mais sites e retornar JSON.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

allow_origins = ["*"] if settings.cors_origins == "*" else [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allow_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class ExtractRequest(BaseModel):
    urls: list[HttpUrl] = Field(..., min_length=1, description="Uma ou mais URLs para processar")
    date_from: date | None = None
    date_to: date | None = None
    model: str | None = Field(default=None, min_length=1)
    crawl_content: bool | None = None
    max_articles: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def validate_dates(self) -> "ExtractRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from deve ser menor ou igual a date_to")
        return self


class ExtractUrlRequest(BaseModel):
    url: HttpUrl
    model: str | None = Field(default=None, min_length=1)


class ExtractError(BaseModel):
    url: str
    message: str
    stage: str


class ArticleOut(BaseModel):
    title: str
    url: str
    date: str | None = None
    source: str
    content_md: str | None = None

    @classmethod
    def from_article(cls, article: Article) -> "ArticleOut":
        return cls.model_validate(article.__dict__)


class ExtractResponse(BaseModel):
    ok: bool
    count: int
    articles: list[ArticleOut]
    errors: list[ExtractError]
    model: str
    crawl_content: bool
    elapsed_ms: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    time: str


class RootResponse(BaseModel):
    service: str
    version: str
    docs: str
    health: str
    extract: str
    extract_url: str


class StreamItem(BaseModel):
    type: str
    message: str | None = None
    article: ArticleOut | None = None
    error: ExtractError | None = None


class UrlCheckResult(BaseModel):
    url: str
    allowed: bool
    reason: str | None = None


def validate_target_url(url: str) -> UrlCheckResult:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return UrlCheckResult(url=url, allowed=False, reason="apenas URLs http/https são aceitas")
    if not parsed.netloc:
        return UrlCheckResult(url=url, allowed=False, reason="URL inválida")
    host = parsed.hostname or ""
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    if host in blocked_hosts:
        return UrlCheckResult(url=url, allowed=False, reason="host local não permitido")
    allowed_hosts = {h.strip().lower() for h in settings.allowed_hosts.split(",") if h.strip()}
    if allowed_hosts and host.lower() not in allowed_hosts:
        return UrlCheckResult(url=url, allowed=False, reason="host fora da allowlist")
    return UrlCheckResult(url=url, allowed=True)


@app.get("/", response_model=RootResponse, tags=["system"])
async def root() -> RootResponse:
    return RootResponse(service=settings.app_name, version=settings.app_version, docs="/docs", health="/health", extract="/extract", extract_url="/extract/url")


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version, time=datetime.utcnow().isoformat() + "Z")


@app.get("/openapi.json", include_in_schema=False)
async def openapi_alias() -> Any:
    return app.openapi()


async def _run_extraction(urls: list[str], date_from: date | None, date_to: date | None, model: str, crawl_content: bool, max_articles: int) -> ExtractResponse:
    start = time.perf_counter()
    articles_out: list[ArticleOut] = []
    errors: list[ExtractError] = []
    for url in urls:
        check = validate_target_url(url)
        if not check.allowed:
            errors.append(ExtractError(url=url, message=check.reason or "url bloqueada", stage="validation"))
            continue
        try:
            extracted = await process_frontpages(
                frontpage_urls=[url],
                date_from=date_from or date(1970, 1, 1),
                date_to=date_to or date(2100, 1, 1),
                model=model,
                crawl_content=crawl_content,
                max_articles=max_articles,
            )
            articles_out.extend(ArticleOut.from_article(a) for a in extracted)
        except Exception as exc:
            errors.append(ExtractError(url=url, message=str(exc), stage="extract"))
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return ExtractResponse(ok=len(errors) == 0, count=len(articles_out), articles=articles_out, errors=errors, model=model, crawl_content=crawl_content, elapsed_ms=elapsed_ms)


@app.post("/extract", response_model=ExtractResponse, tags=["extract"])
async def extract(payload: ExtractRequest) -> ExtractResponse:
    if len(payload.urls) > settings.max_urls:
        raise HTTPException(status_code=400, detail=f"Máximo de {settings.max_urls} URLs por requisição")
    model = payload.model or settings.default_model
    crawl_content = settings.default_crawl_content if payload.crawl_content is None else payload.crawl_content
    max_articles = payload.max_articles or settings.default_max_articles
    return await _run_extraction([str(u) for u in payload.urls], payload.date_from, payload.date_to, model, crawl_content, max_articles)


@app.post("/extract/url", response_model=ArticleOut, tags=["extract"])
async def extract_url(payload: ExtractUrlRequest) -> ArticleOut:
    check = validate_target_url(str(payload.url))
    if not check.allowed:
        raise HTTPException(status_code=400, detail=check.reason)
    model = payload.model or settings.default_model
    markdown = await crawl_article_content(str(payload.url))
    title = urlparse(str(payload.url)).path.rstrip("/").split("/")[-1] or urlparse(str(payload.url)).netloc
    return ArticleOut(
        title=title,
        url=str(payload.url),
        date=None,
        source=urlparse(str(payload.url)).netloc,
        content_md=markdown,
    )


@app.post("/extract/stream", tags=["extract"])
async def extract_stream(payload: ExtractRequest):
    if len(payload.urls) > settings.max_urls:
        raise HTTPException(status_code=400, detail=f"Máximo de {settings.max_urls} URLs por requisição")
    model = payload.model or settings.default_model
    crawl_content = settings.default_crawl_content if payload.crawl_content is None else payload.crawl_content
    max_articles = payload.max_articles or settings.default_max_articles

    async def generator():
        yield StreamItem(type="start", message="processing").model_dump_json() + "\n"
        for raw_url in payload.urls:
            url = str(raw_url)
            check = validate_target_url(url)
            if not check.allowed:
                yield StreamItem(type="error", error=ExtractError(url=url, message=check.reason or "url bloqueada", stage="validation")).model_dump_json() + "\n"
                continue
            try:
                extracted = await process_frontpages(
                    frontpage_urls=[url],
                    date_from=payload.date_from or date(1970, 1, 1),
                    date_to=payload.date_to or date(2100, 1, 1),
                    model=model,
                    crawl_content=crawl_content,
                    max_articles=max_articles,
                )
                for item in extracted:
                    yield StreamItem(type="article", article=ArticleOut.from_article(item)).model_dump_json() + "\n"
            except Exception as exc:
                yield StreamItem(type="error", error=ExtractError(url=url, message=str(exc), stage="extract")).model_dump_json() + "\n"
        yield StreamItem(type="done", message="finished").model_dump_json() + "\n"

    return StreamingResponse(generator(), media_type="application/x-ndjson")
