"""
extractor.py — Extrai artigos de frontpages usando OpenAI via LangChain.
Lê OPENAI_API_KEY automaticamente do .env.
"""

import asyncio
import httpx
import json
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, asdict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

load_dotenv()  # carrega .env automaticamente


# ──────────────────────────────────────────────
# MODELOS
# ──────────────────────────────────────────────

class ArticleItem(BaseModel):
    title: str
    url: str
    date: Optional[str] = Field(None, description="YYYY-MM-DD ou null")

class ArticleList(BaseModel):
    articles: list[ArticleItem]

@dataclass
class Article:
    title: str
    url: str
    date: Optional[str]        # ISO 8601: "2025-05-20"
    source: str                # domínio de origem
    content_md: Optional[str] = None


# ──────────────────────────────────────────────
# 1. FETCH HTML DA FRONTPAGE
# ──────────────────────────────────────────────

async def fetch_html(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.text


# ──────────────────────────────────────────────
# 2. OPENAI VIA LANGCHAIN — EXTRAÇÃO DE ARTIGOS
# ──────────────────────────────────────────────

EXTRACTION_SYSTEM = """
Você é um extrator de dados estruturados de HTML de sites de notícias.
Dado o HTML de uma frontpage, extraia TODOS os artigos listados.

Retorne APENAS um JSON válido com esta estrutura (sem markdown, sem explicação):
{
  "articles": [
    {
      "title": "Título do artigo",
      "url": "https://url-completa.com/artigo",
      "date": "YYYY-MM-DD"
    }
  ]
}

Regras:
- Se a URL for relativa (ex: /artigo/123), complete com o domínio base fornecido.
- Se a data não estiver explícita, use null.
- Datas em português (ex: "20 mai 2025", "há 2 horas") devem ser convertidas para YYYY-MM-DD.
- Ignore anúncios, links de navegação e rodapé — foque em artigos/notícias.
- Retorne no máximo 50 artigos por frontpage.
"""

def build_llm(model: str = "gpt-4o-mini") -> ChatOpenAI:
    """Instancia o LLM — OPENAI_API_KEY vem do .env via load_dotenv()."""
    return ChatOpenAI(
        model=model,
        temperature=0,
        max_tokens=4096,
    )

async def extract_articles(
    html: str,
    base_url: str,
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """Envia HTML para o OpenAI via LangChain e recebe lista de artigos."""

    html_truncated = html[:80_000]  # cabe no contexto de 128k

    llm = build_llm(model)
    parser = JsonOutputParser(pydantic_object=ArticleList)

    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM),
        HumanMessage(content=(
            f"Base URL: {base_url}\n\n"
            f"HTML da frontpage:\n\n{html_truncated}"
        )),
    ]

    # with_structured_output garante JSON válido mesmo com modelos mais velhos
    structured_llm = llm.with_structured_output(ArticleList)
    result: ArticleList = await structured_llm.ainvoke(messages)
    return [a.model_dump() for a in result.articles]


# ──────────────────────────────────────────────
# 3. FILTRO POR DATA
# ──────────────────────────────────────────────

def parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return None

def filter_by_date(
    articles: list[dict],
    date_from: date,
    date_to: date,
) -> list[dict]:
    result = []
    for a in articles:
        d = parse_date(a.get("date"))
        if d and date_from <= d <= date_to:
            result.append(a)
    return result


# ──────────────────────────────────────────────
# 4. CRAWL4AI — EXTRAÇÃO DE CONTEÚDO EM MARKDOWN
# ──────────────────────────────────────────────

async def crawl_article_content(url: str) -> str:
    """
    Usa crawl4ai para extrair o conteúdo do artigo em Markdown.
    Requer: pip install crawl4ai && crawl4ai-setup
    """
    try:
        from crawl4ai import AsyncWebCrawler
        from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        browser_config = BrowserConfig(verbose=False)

        run_config = CrawlerRunConfig(
            # Filtragem de conteúdo — remove blocos com poucas palavras (nav, rodapé, etc.)
            word_count_threshold=10,
            excluded_tags=["form", "header", "footer", "nav"],
            exclude_external_links=True,
            remove_overlay_elements=True,  # remove popups/modais
            process_iframes=True,
            # Markdown: PruningContentFilter mantém só o conteúdo mais relevante
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(threshold=0.6),
                options={"ignore_links": True},
            ),
            cache_mode=CacheMode.ENABLED,  # evita re-crawl desnecessário
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                return f"[Erro ao extrair (HTTP {result.status_code}): {result.error_message}]"

            # fit_markdown = conteúdo podado pelo PruningContentFilter (mais limpo)
            # raw_markdown = fallback se o filtro remover demais
            return result.markdown.fit_markdown or result.markdown.raw_markdown

    except ImportError:
        return "[crawl4ai não instalado — rode: pip install crawl4ai && crawl4ai-setup]"
    except Exception as e:
        return f"[Erro: {e}]"


# ──────────────────────────────────────────────
# 5. PIPELINE PRINCIPAL
# ──────────────────────────────────────────────

async def process_frontpages(
    frontpage_urls: list[str],
    date_from: date,
    date_to: date,
    model: str = "gpt-4o-mini",
    crawl_content: bool = True,
    max_articles: int = 20,
    progress_callback=None,
) -> list[Article]:
    """
    Pipeline completo:
    1. Fetch HTML de cada frontpage
    2. OpenAI extrai artigos (title, url, date)
    3. Filtra por intervalo de datas
    4. crawl4ai extrai conteúdo em Markdown
    """
    all_articles: list[Article] = []

    for fp_url in frontpage_urls:
        source = fp_url.split("/")[2]
        if progress_callback:
            progress_callback(f"📥 Buscando frontpage: {source}")

        try:
            html = await fetch_html(fp_url)
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Erro ao buscar {fp_url}: {e}")
            continue

        if progress_callback:
            progress_callback(f"🤖 Extraindo artigos com OpenAI ({model}): {source}")

        try:
            raw_articles = await extract_articles(html, fp_url, model)
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Erro OpenAI ({source}): {e}")
            continue

        filtered = filter_by_date(raw_articles, date_from, date_to)

        if progress_callback:
            progress_callback(
                f"✅ {source}: {len(raw_articles)} artigos encontrados, "
                f"{len(filtered)} no intervalo de datas"
            )

        for a in filtered[:max_articles]:
            all_articles.append(Article(
                title=a["title"],
                url=a["url"],
                date=a.get("date"),
                source=source,
            ))

    # Crawl de conteúdo (paralelo, máx 5 simultâneos)
    if crawl_content and all_articles:
        if progress_callback:
            progress_callback(f"\n🕷️ Extraindo conteúdo de {len(all_articles)} artigos...")

        semaphore = asyncio.Semaphore(5)

        async def crawl_with_limit(article: Article):
            async with semaphore:
                if progress_callback:
                    progress_callback(f"  ↳ {article.title[:60]}...")
                article.content_md = await crawl_article_content(article.url)

        await asyncio.gather(*[crawl_with_limit(a) for a in all_articles])

    return all_articles


# ──────────────────────────────────────────────
# 6. UTILS — SALVAR RESULTADOS
# ──────────────────────────────────────────────

def save_articles_json(articles: list[Article], path: str = "articles.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in articles], f, ensure_ascii=False, indent=2)
    print(f"💾 Salvo em {path}")

def save_articles_markdown(articles: list[Article], path: str = "articles.md"):
    lines = [f"# Artigos Extraídos\n\nTotal: {len(articles)}\n"]
    for a in articles:
        lines.append(f"---\n## {a.title}")
        lines.append(f"- **Fonte**: {a.source}")
        lines.append(f"- **Data**: {a.date}")
        lines.append(f"- **URL**: {a.url}\n")
        if a.content_md:
            lines.append("### Conteúdo\n")
            lines.append(a.content_md)
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"💾 Salvo em {path}")
    
if __name__ == "__main__":
    # Exemplo de uso
    frontpages = [
        "https://huggingface.co/blog",
        # Adicione mais URLs de frontpages aqui
    ]
    date_from = date(2024, 1, 1)
    date_to = date(2027, 12, 31)

    articles = asyncio.run(process_frontpages(frontpages, date_from, date_to))
    save_articles_json(articles)
    save_articles_markdown(articles)