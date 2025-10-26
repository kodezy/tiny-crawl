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
```bash
python crawler.py https://example.com --recursive --max-pages 20
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
python crawler.py --urls-file urls.txt
```

### Options
- `url`: Single URL to crawl (optional if using --urls-file)
- `--urls-file`, `-f`: File containing URLs (one per line)
- `--recursive`, `-r`: Follow links on same domain
- `--max-pages`, `-m`: Max pages per URL (default: 10)
- `--output`, `-o`: Output directory (default: docs)

## Output
Markdown files in the output directory. Each page becomes a separate `.md` file.
