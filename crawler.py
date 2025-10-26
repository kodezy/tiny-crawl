import argparse
import asyncio
from pathlib import Path
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig


def load_urls_from_file(filepath: str) -> list[str]:
    """Load URLs from a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def is_valid_link(url: str, base_url: str) -> bool:
    """Check if a link is valid."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    if not parsed.netloc or parsed.netloc != base_parsed.netloc:
        return False

    if not parsed.path or parsed.path == "/":
        return False

    if any(x in parsed.path for x in ["#", "?", "javascript:", "mailto:", ".pdf", ".zip", ".png", ".jpg"]):
        return False

    return True


def normalize_url(url: str, base_url: str) -> str | None:
    """Normalize and validate a URL, ensuring it has a proper protocol."""
    if not url:
        return None
    
    parsed = urlparse(url)
    if parsed.scheme:
        return url
    
    absolute_link = urljoin(base_url, url)
    if absolute_link and absolute_link.startswith(("http://", "https://")):
        return absolute_link
    
    return None


async def crawl_site(starting_urls: list[str], max_pages: int = 10, output_dir: str = "docs") -> None:
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    visited_urls = set()
    urls_to_crawl = starting_urls if isinstance(starting_urls, list) else [starting_urls]
    saved_count = 0

    async with AsyncWebCrawler() as crawler:
        while urls_to_crawl and saved_count < max_pages:
            current_url = urls_to_crawl.pop(0)

            if current_url in visited_urls:
                continue

            visited_urls.add(current_url)

            print(f"Crawling: {current_url} ({saved_count + 1}/{max_pages})")

            try:
                result = await crawler.arun(
                    url=current_url,
                    config=CrawlerRunConfig(process_iframes=True, cache_mode=CacheMode.BYPASS),
                )

                if result.markdown and len(result.markdown.strip()) > 100:
                    url_path = urlparse(current_url).path
                    safe_filename = url_path.replace("/", "_").strip("_") or "index"
                    if not safe_filename.endswith(".md"):
                        safe_filename += ".md"

                    filepath = output_path / safe_filename
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(f"# {current_url}\n\n")
                        f.write(result.markdown)

                    print(f"✓ Saved: {filepath}")
                    saved_count += 1

                    if result.links:
                        for link in result.links:
                            if isinstance(link, str):
                                raw_link = link
                            else:
                                raw_link = link.get("href", "")

                            normalized_link = normalize_url(raw_link, current_url)
                            
                            if normalized_link:
                                base_url = starting_urls[0] if isinstance(starting_urls, list) else starting_urls
                                if is_valid_link(normalized_link, base_url):
                                    if normalized_link not in visited_urls and normalized_link not in urls_to_crawl:
                                        urls_to_crawl.append(normalized_link)
                else:
                    print(f"✗ Skipping {current_url} - insufficient content")

            except Exception as e:
                print(f"✗ Error crawling {current_url}: {e}")

    print(f"\nCompleted! Saved {saved_count} pages. Documentation saved to: {output_dir}")


async def single_page_crawl(url: str, output_dir: str = "docs") -> None:
    """Crawl a single page."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"Crawling: {url}")

    async with AsyncWebCrawler() as crawler:
        try:
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(process_iframes=True, cache_mode=CacheMode.BYPASS),
            )

            if result.markdown:
                url_path = urlparse(url).path
                safe_filename = url_path.replace("/", "_").strip("_") or "index"
                if not safe_filename.endswith(".md"):
                    safe_filename += ".md"

                filepath = output_path / safe_filename
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# {url}\n\n")
                    f.write(result.markdown)

                print(f"✓ Saved: {filepath}")
            else:
                print("✗ No content extracted")

        except Exception as e:
            print(f"✗ Error: {e}")


async def crawl_urls_list(urls: list[str], output_dir: str = "docs") -> None:
    """Crawl a list of URLs."""
    for url in urls:
        await single_page_crawl(url, output_dir)


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate documentation from websites using crawl4ai")
    parser.add_argument("url", nargs="?", help="URL to crawl")
    parser.add_argument("--urls-file", "-f", help="File with URLs to crawl (one per line)")
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Enable recursive crawling of linked pages",
    )
    parser.add_argument(
        "--max-pages",
        "-m",
        type=int,
        default=10,
        help="Maximum number of pages to crawl per URL (default: 10)",
    )
    parser.add_argument("--output", "-o", default="docs", help="Output directory (default: docs)")

    args = parser.parse_args()

    if not args.url and not args.urls_file:
        parser.error("Either provide a URL or use --urls-file")

    if args.urls_file:
        urls = load_urls_from_file(args.urls_file)
        print(f"Loaded {len(urls)} URLs from {args.urls_file}")
    else:
        urls = [args.url]

    if args.recursive:
        asyncio.run(crawl_site(urls, args.max_pages, args.output))
    else:
        asyncio.run(crawl_urls_list(urls, args.output))


if __name__ == "__main__":
    main()
