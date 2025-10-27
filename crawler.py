import argparse
import asyncio
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.models import CrawlResult

MAX_SESSION_PERMIT: int = 10
MEMORY_THRESHOLD_PERCENT: float = 80.0
MIN_CONTENT_LENGTH: int = 100


async def crawl_single(url: str, output_dir: str, use_cache: bool = False) -> None:
    """Crawl a single URL and save the result to a markdown file."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    normalized_url = _normalize_url(url)

    cache_mode = CacheMode.ENABLED if use_cache else CacheMode.DISABLED
    config = CrawlerRunConfig(cache_mode=cache_mode, verbose=True)

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(normalized_url, config=config)

        if result.success:
            markdown = _get_markdown_content(result)

            if markdown and _has_minimal_content(markdown):
                _save_page(output_path, result.url, markdown)


async def crawl_site(urls: list[str], output_dir: str, max_depth: int = 2, use_cache: bool = False) -> None:
    """Crawl a list of URLs and save the results to markdown files."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    if not urls:
        return

    cache_mode = CacheMode.ENABLED if use_cache else CacheMode.DISABLED

    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=max_depth, include_external=False),
        scraping_strategy=LXMLWebScrapingStrategy(),
        cache_mode=cache_mode,
        stream=True,
        verbose=True,
    )

    async with AsyncWebCrawler() as crawler:
        for url in urls:
            normalized_url = _normalize_url(url)

            async for result in await crawler.arun(normalized_url, config=config):
                if result.success:
                    markdown = _get_markdown_content(result)

                    if markdown and _has_minimal_content(markdown):
                        _save_page(output_path, result.url, markdown)


async def crawl_multi(urls: list[str], output_dir: str, use_cache: bool = False) -> None:
    """Crawl a list of URLs and save the results to markdown files."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    normalized_urls = [_normalize_url(url) for url in urls]

    if not urls:
        return

    cache_mode = CacheMode.ENABLED if use_cache else CacheMode.DISABLED

    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=MEMORY_THRESHOLD_PERCENT,
        max_session_permit=MAX_SESSION_PERMIT,
    )

    config = CrawlerRunConfig(
        cache_mode=cache_mode,
        stream=False,
        verbose=True,
    )

    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(normalized_urls, config=config, dispatcher=dispatcher)
        for result in results:
            if result.success:
                markdown = _get_markdown_content(result)
                if markdown and _has_minimal_content(markdown):
                    _save_page(output_path, result.url, markdown)


def _load_urls(filepath: str) -> list[str]:
    """Load the URLs from a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        raise

    except Exception as exception:
        print(f"Error reading file '{filepath}': {exception}")
        raise


def _normalize_url(url: str) -> str:
    """Add https:// if URL doesn't have a protocol."""
    url = url.strip()
    if not url.startswith(("http://", "https://", "file://", "raw:")):
        return f"https://{url}"
    return url


def _get_filename(url: str) -> str:
    """Get the filename for the markdown file."""
    path = urlparse(url).path.replace("/", "_").strip("_") or "index"
    return f"{path}.md" if not path.endswith(".md") else path


def _get_markdown_content(result: CrawlResult) -> str | None:
    """Get the markdown content from the result."""
    if not result.markdown:
        return None

    if isinstance(result.markdown, str):
        return result.markdown

    return result.markdown.raw_markdown


def _save_page(output_path: Path, url: str, content: str) -> None:
    """Save the markdown content to a file."""
    filepath = output_path / _get_filename(url)
    filepath.write_text(f"# {url}\n\n{content}", encoding="utf-8")


def _has_minimal_content(markdown: str) -> bool:
    """Check if the markdown content has a minimal length."""
    return len(markdown.strip()) > MIN_CONTENT_LENGTH


def main() -> None:
    """Main function to parse arguments and crawl the URLs."""
    parser = argparse.ArgumentParser(description="Web crawler using crawl4ai")
    parser.add_argument("url", nargs="?", help="URL to crawl")
    parser.add_argument("-f", "--file", help="File with URLs")
    parser.add_argument("-o", "--output", default="docs", help="Output directory")
    parser.add_argument("-r", "--recursive", action="store_true", help="Follow links recursively")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Max depth")
    parser.add_argument("-c", "--cache", action="store_true", help="Enable HTTP cache")

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("Either provide a URL or use -f")

    urls = _load_urls(args.file) if args.file else [args.url]

    if args.recursive:
        asyncio.run(crawl_site(urls, args.output, args.depth, args.cache))
    else:
        asyncio.run(crawl_multi(urls, args.output, args.cache))


if __name__ == "__main__":
    main()
