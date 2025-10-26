# Tiny Crawl

Simple and straightforward crawler for simple and straightforward things.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Single URL
```bash
python crawler.py https://example.com
```

### Recursive Crawling
Follows all links on the same domain indefinitely:
```bash
python crawler.py https://example.com --recursive
```

### Multiple URLs from File
Create a file `urls.txt`:
```
https://example.com/page1
https://example.com/page2
https://example.com/page3
```

Then run:
```bash
python crawler.py --file urls.txt
```

### Options
- `url`: Single URL to crawl (optional if using --file)
- `--file`, `-f`: File containing URLs (one per line)
- `--recursive`, `-r`: Follow links on same domain recursively
- `--output`, `-o`: Output directory (default: docs)

### How It Works
- **No page limits**: Crawls until no more links are found
- **Smart skipping**: Automatically skips URLs that have already been crawled
- **Progress tracking**: Shows `✓ [X] filename.md (Y queued)` in real-time
- **Existing files**: Detects existing `.md` files and counts them as progress

## Output
Markdown files in the output directory. Each page becomes a separate `.md` file.
