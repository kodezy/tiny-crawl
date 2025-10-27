import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.models import CrawlResult

MIN_CONTENT_LENGTH: int = 100


async def crawl_urls(
    urls: list[str],
    use_cache: bool = False,
    recursive: bool = False,
    max_depth: int = 2,
    output_dir: str = "output",
    max_session_permit: int = 10,
    memory_threshold_percent: float = 80.0,
) -> None:
    """Crawl URLs and save results to markdown files or a single JSON file."""
    output_path = Path(output_dir)
    is_json_output = output_path.suffix == ".json"

    if is_json_output:
        json_data: list[dict[str, str]] = []
    else:
        output_path.mkdir(exist_ok=True)

    if not urls:
        return

    normalized_urls = [_normalize_url(url) for url in urls]
    config = _create_config(recursive, max_depth, use_cache)

    try:
        if recursive:
            async with AsyncWebCrawler() as crawler:
                for url in normalized_urls:
                    try:
                        result = await crawler.arun(url, config=config)
                        
                        if isinstance(result, list):
                            for item in result:
                                _process_result(item, output_path, json_data if is_json_output else None)
                        else:
                            _process_result(result, output_path, json_data if is_json_output else None)

                    except KeyboardInterrupt:
                        print(f"\n⚠️  Crawling interrupted by user while processing {url}")
                        break

                    except Exception as exception:
                        print(f"⚠️  Error crawling {url}: {exception}")
                        continue

        else:
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=memory_threshold_percent,
                max_session_permit=max_session_permit,
            )

            async with AsyncWebCrawler() as crawler:
                results = await crawler.arun_many(normalized_urls, config=config, dispatcher=dispatcher)
                for result in results:
                    _process_result(result, output_path, json_data if is_json_output else None)

        if is_json_output and json_data:
            _save_json(output_path, json_data)

    except KeyboardInterrupt:
        if is_json_output and json_data:
            _save_json(output_path, json_data)

        print("\n⚠️  Crawling interrupted by user")

    except Exception as exception:
        if is_json_output and json_data:
            _save_json(output_path, json_data)

        print(f"⚠️  Error while crawling {urls}: {exception}")


def main() -> None:
    """Parse command line arguments and start the crawling process."""
    parser = argparse.ArgumentParser(description="Web crawler using crawl4ai")

    parser.add_argument("url", nargs="?", help="URL to crawl")
    parser.add_argument("-f", "--file", help="File with URLs")
    parser.add_argument("-c", "--cache", action="store_true", help="Enable HTTP cache")
    parser.add_argument("-r", "--recursive", action="store_true", help="Follow links recursively")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Max depth")
    parser.add_argument("-o", "--output", default="output", help="Output directory or JSON file")

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("Either provide a URL or use -f")

    urls = _load_urls(args.file) if args.file else [args.url]

    try:
        asyncio.run(
            crawl_urls(
                urls,
                use_cache=args.cache,
                recursive=args.recursive,
                max_depth=args.depth,
                output_dir=args.output,
            )
        )

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user. Exiting gracefully.")

    except Exception as exception:
        print(f"\n❌ Fatal error: {exception}")


def _create_config(recursive: bool = False, max_depth: int = 2, use_cache: bool = False) -> CrawlerRunConfig:
    """Create a CrawlerRunConfig with the specified options."""
    cache_mode = CacheMode.ENABLED if use_cache else CacheMode.DISABLED

    if recursive:
        return CrawlerRunConfig(
            deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=max_depth, include_external=False),
            scraping_strategy=LXMLWebScrapingStrategy(),
            cache_mode=cache_mode,
            stream=False,
            verbose=True,
        )

    return CrawlerRunConfig(
        cache_mode=cache_mode,
        stream=False,
        verbose=True,
    )


def _process_result(result: CrawlResult, output_path: Path, json_data: list | None = None) -> None:
    """Process and save a crawl result if valid."""
    if result.success:
        markdown = _get_markdown_content(result)

        if markdown and _has_minimal_content(markdown):
            if json_data is not None:
                _add_to_json(json_data, result.url, markdown)
            else:
                _save_page(output_path, result.url, markdown)


def _add_to_json(json_data: list, url: str, content: str) -> None:
    """Add a result to the JSON data."""
    json_data.append(
        {
            "url": url,
            "content": content,
        }
    )


def _save_json(output_path: Path, json_data: list) -> None:
    """Save the JSON data to a file."""
    output_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_urls(filepath: str) -> list[str]:
    """Load the URLs from a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return [line.strip() for line in file if line.strip() and not line.strip().startswith("#")]

    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        raise

    except Exception as exception:
        print(f"Error reading file '{filepath}': {exception}")
        raise


def _normalize_url(url: str) -> str:
    """Add https:// if URL doesn't have a protocol."""
    url = url.strip()
    return url if url.startswith(("http://", "https://", "file://", "raw:")) else f"https://{url}"


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


if __name__ == "__main__":
    main()
