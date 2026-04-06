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
Follows links recursively up to the specified depth.

If the start URL has a path (example: `/products`), recursion is automatically limited to that path.
```bash
python crawler.py https://site.com.br/products --recursive
```

Or specify a custom depth:
```bash
python crawler.py https://example.com --recursive --depth 3
```

Optionally force a custom path scope:
```bash
python crawler.py https://site.com.br --recursive --scope /products
python crawler.py https://site.com.br --recursive --scope products
python crawler.py https://site.com.br --recursive --scope site.com.br/products
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

### Cache
Enable HTTP caching to avoid re-downloading pages:
```bash
python crawler.py https://example.com -c
python crawler.py https://example.com --cache
```

### Options
- `url`: Single URL to crawl (optional if using --file)
- `-f`, `--file`: File containing URLs (one per line)
- `-c`, `--cache`: Enable HTTP cache (default: disabled)
- `-r`, `--recursive`: Follow links on same domain recursively
- `-d`, `--depth`: Max depth for recursive crawling (default: 2)
- `--scope`, `--only-under`, `--recursive-scope`: Only follow links under this prefix
- `-o`, `--output`: Output directory or .json file (default: output/)

### How It Works
- **HTTP Cache**: Use `--cache` to enable crawl4ai's HTTP caching system
- **Verbose output**: Shows crawl4ai's built-in progress information
- **Depth control**: Limits crawling depth to avoid runaway crawling
- **Stream mode**: Processes pages incrementally for better performance

## Output
Markdown files in the output directory. Each page becomes a separate `.md` file.
