import argparse
import asyncio
import re
import signal
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig


class Stats:
    """Stats class to track the number of saved pages."""

    def __init__(self) -> None:
        self.saved: int = 0
        self.lock: asyncio.Lock = asyncio.Lock()
        self.interrupted: bool = False


def extract_links_from_html(html: str, current_url: str) -> list[str]:
    """Extract links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"])
        full_url = urljoin(current_url, href)
        links.append(full_url)

    return links


def get_filename_from_url(url: str) -> str:
    """Get a filename from a URL."""
    path = urlparse(url).path.replace("/", "_").strip("_") or "index"
    return path + ".md" if not path.endswith(".md") else path


def is_valid_link(url: str, base_url: str) -> bool:
    """Check if a link is valid."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    if not parsed.netloc or parsed.netloc != base_parsed.netloc:
        return False

    path = parsed.path.strip()
    if not path or path in ["/", "/#", "#"]:
        return False

    if "javascript:" in url.lower() or "mailto:" in url.lower():
        return False

    file_exts = [".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".ico", ".webp"]
    if any(ext in path.lower() for ext in file_exts):
        return False

    return True


def normalize_url(url: str, base_url: str) -> str | None:
    """Normalize a URL."""
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme:
        return url

    absolute_link = urljoin(base_url, url)
    if absolute_link and absolute_link.startswith(("http://", "https://")):
        return absolute_link

    return None


def extract_all_links(result: Any, current_url: str) -> list[str]:
    """Extract all links from a result."""
    links = set()

    if result.html:
        links.update(extract_links_from_html(result.html, current_url))

    if result.links:
        for link in result.links:
            if isinstance(link, str):
                links.add(link)
            elif isinstance(link, dict):
                links.add(link.get("href", ""))

    return [link for link in links if link]


async def crawl_page(crawler: AsyncWebCrawler, url: str, stats: Stats) -> tuple | None:
    """Crawl a page."""
    try:
        result = await crawler.arun(
            url=url,
            config=CrawlerRunConfig(process_iframes=True, cache_mode=CacheMode.BYPASS, verbose=False),
        )

        if result.markdown and len(result.markdown.strip()) > 100:
            links = extract_all_links(result, url)
            return (url, result.markdown, links)

    except Exception as e:
        print(f"✗ Error: {e}")

    return None


def save_page(output_path: Path, url: str, content: str) -> str:
    """Save a page to a file."""
    filename = get_filename_from_url(url)
    filepath = output_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {url}\n\n")
        f.write(content)

    return filename


def file_exists_for_url(output_path: Path, url: str) -> bool:
    """Check if a file exists for a URL."""
    filename = get_filename_from_url(url)
    return (output_path / filename).exists()


async def extract_existing_urls(output_path: Path) -> set[str]:
    """Extract URLs from saved files to add to visited set."""
    existing_urls = set()

    for filepath in output_path.glob("*.md"):
        try:
            first_line = filepath.read_text(encoding="utf-8").split("\n")[0]

            if first_line.startswith("# "):
                url = first_line[2:].strip()

                if url:
                    existing_urls.add(url)

        except:
            pass

    return existing_urls


async def worker(
    crawler: AsyncWebCrawler,
    url_queue: deque[str],
    visited: set[str],
    url_set: set[str],
    output_path: Path,
    base_url: str,
    stats: Stats,
) -> None:
    """Worker function to crawl pages."""
    try:
        while url_queue:
            if stats.interrupted:
                break

            current_url = url_queue.popleft()

            if current_url in visited:
                continue

            visited.add(current_url)

            file_exists = file_exists_for_url(output_path, current_url)

            result = await crawl_page(crawler, current_url, stats)

            if result:
                url, content, links = result

                async with stats.lock:
                    if stats.interrupted:
                        break

                    if not file_exists:
                        filename = save_page(output_path, url, content)
                        stats.saved += 1
                        queued = len(url_queue)
                        total = stats.saved + queued
                        print(f"✓ [{stats.saved}/{total}] {filename}")

                for link in links:
                    normalized_link = normalize_url(link, url)

                    if normalized_link and is_valid_link(normalized_link, base_url):
                        if normalized_link not in url_set:
                            url_set.add(normalized_link)
                            url_queue.append(normalized_link)
    except asyncio.CancelledError:
        pass


def extract_links_from_markdown(content: str, current_url: str) -> list[str]:
    """Extract links from markdown content."""
    links = []

    link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
    matches = re.findall(link_pattern, content)

    for _, url in matches:
        if url.startswith("http"):
            links.append(url)
        else:
            absolute_link = urljoin(current_url, url)
            if absolute_link.startswith(("http://", "https://")):
                links.append(absolute_link)

    return links


def populate_queue_from_markdown(output_path: Path, base_url: str, url_set: set[str]) -> deque[str]:
    """Extract links from existing .md files."""
    url_queue: deque[str] = deque()

    md_files = list(output_path.glob("*.md"))

    if md_files:
        print(f"   Extracting links from {len(md_files)} markdown files...")

        for filepath in md_files:
            try:
                content = filepath.read_text(encoding="utf-8")
                first_line = content.split("\n")[0]
                saved_url = first_line[2:].strip() if first_line.startswith("# ") else None

                if saved_url:
                    links = extract_links_from_markdown(content, saved_url)

                    for link in links:
                        normalized_link = normalize_url(link, saved_url)

                        if normalized_link and is_valid_link(normalized_link, base_url):
                            if normalized_link not in url_set:
                                url_set.add(normalized_link)
                                url_queue.append(normalized_link)
            except:
                continue

    return url_queue


def signal_handler(stats: Stats):
    """Handle SIGINT signal to gracefully stop the crawler."""

    def handler(signum, frame):
        stats.interrupted = True

    return handler


async def crawl_site(urls: list[str], output_dir: str) -> None:
    """Crawl a site."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    if not urls:
        print("✗ No URLs to crawl")
        return

    existing_files = list(output_path.glob("*.md"))
    existing_urls = await extract_existing_urls(output_path)

    visited: set[str] = set(existing_urls)
    url_set: set[str] = set()
    stats = Stats()

    for _ in existing_files:
        stats.saved += 1

    base_url = urls[0]

    print(f"\n🕷️  Tiny Crawl")
    print(f"   Base URL: {base_url}")
    print(f"   Output: {output_dir}")
    print(f"   Existing: {stats.saved} files")

    initial_queue = populate_queue_from_markdown(output_path, base_url, url_set)

    for url in urls:
        if url not in url_set:
            initial_queue.append(url)
            url_set.add(url)

    print(f"   Initial queue: {len(initial_queue)} URLs\n")

    signal.signal(signal.SIGINT, signal_handler(stats))

    try:
        async with AsyncWebCrawler() as crawler:
            await worker(crawler, initial_queue, visited, url_set, output_path, base_url, stats)

    except (KeyboardInterrupt, Exception) as e:
        if stats.interrupted or isinstance(e, KeyboardInterrupt):
            pass
        else:
            raise

    if stats.interrupted:
        print(f"\n\n✓ Interrupted by user! {stats.saved} pages saved in {output_dir}")
    else:
        print(f"\n✓ Completed! {stats.saved} pages in {output_dir}")


async def single_page_crawl(url: str, output_dir: str) -> None:
    """Crawl a single page."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"Crawling: {url}")

    async with AsyncWebCrawler() as crawler:
        stats = Stats()
        result = await crawl_page(crawler, url, stats)

        if result:
            url, content, _ = result
            filename = save_page(output_path, url, content)
            print(f"✓ {filename}")
        else:
            print("✗ No content extracted")


async def crawl_urls_list(urls: list[str], output_dir: str) -> None:
    """Crawl a list of URLs."""
    print("Crawling...")

    for url in urls:
        await single_page_crawl(url, output_dir)


def load_urls_from_file(filepath: str) -> list[str]:
    """Load URLs from a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Web crawler using crawl4ai",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL to crawl",
    )
    parser.add_argument(
        "--file",
        "-f",
        help="File with URLs to crawl",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Enable recursive crawling of linked pages",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="docs",
        help="Output directory",
    )

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("Either provide a URL or use --file")

    urls = load_urls_from_file(args.file) if args.file else [args.url]

    if args.recursive:
        asyncio.run(crawl_site(urls, args.output))
    else:
        asyncio.run(crawl_urls_list(urls, args.output))


if __name__ == "__main__":
    main()
