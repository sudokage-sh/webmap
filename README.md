```
  ██╗    ██╗███████╗██████╗ ███╗   ███╗ █████╗ ██████╗
  ██║    ██║██╔════╝██╔══██╗████╗ ████║██╔══██╗██╔══██╗
  ██║ █╗ ██║█████╗  ██████╔╝██╔████╔██║███████║██████╔╝
  ██║███╗██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══██║██╔═══╝
  ╚███╔███╔╝███████╗██████╔╝██║ ╚═╝ ██║██║  ██║██║
   ╚══╝╚══╝ ╚══════╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝
```

**web crawler for discovering files by extension**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Playwright](https://img.shields.io/badge/powered%20by-Playwright-orange?style=flat-square)](https://playwright.dev/)

---

## what is webmap ?

webmap is a lightweight, playwright-powered web crawler that discovers files by extension on target websites. 

unlike simple http-based crawlers, webmap runs a real chromium browser — so it catches dynamically loaded resources, xhr/fetch responses, lazy-loaded assets, and anything injected by javascript at runtime.

it stays strictly within scope (no crawling outside the target domain), stops cleanly with `ctrl+c`, and saves everything to json.

with `--js` mode, it also downloads and scans every javascript file for leaked secrets, exposed endpoints, and source maps.

---

## Features

- **real browser crawling** via Playwright — catches JS-rendered content
- **scope-safe** — never leaves the target domain or its subdomains
- **network-layer capture** — catches files loaded via XHR/fetch, not just DOM links
- **color-coded terminal output** — extensions grouped and highlighted by type
- **js secret scanning** (`--js`) — 24+ patterns: AWS, GitHub, Stripe, JWT, and more
- **endpoint extraction** — pulls API paths from JS source
- **source map detection** — flags exposed `.map` files
- **json report** — structured output for every run
- **ctrl+c safe** — graceful stop, always saves report

---

## Installation

```bash
# clone the repo
git clone https://github.com/sudokage-sh/webmap.git
cd webmap/webmap

# install dependencies
pip install playwright
playwright install chromium
```

**Requirements:** Python 3.10+

---

## Usage

### basic crawl

```bash
python webmap.py -u https://target.com
```

### crawl + js secret scan

```bash
python webmap.py -u https://target.com --js
```

### stop anytime

```
ctrl+c  →  gracefully stops, saves report to extensions_found.json
```

---

## Example Terminal Output

```

  ────────────────────────────────────────────────────────────────
  target   https://target.com
  time     2026-03-15 14:22:01
  js scan  enabled
  stop     ctrl+c saves report and exits
  ────────────────────────────────────────────────────────────────

      1  visiting  https://target.com
  [DOM] → .js          https://target.com/static/js/bundle.js
  [NET] → .json        https://target.com/api/config.json
  [DOM] → .css         https://target.com/css/main.css
  [NET] → .svg         https://target.com/assets/icon.svg

      2  visiting  https://target.com/about
  [NET] → .woff2       https://target.com/fonts/inter.woff2
  ...

  ────────────────────────────────────────────────────────────────
  SCAN COMPLETE
  ────────────────────────────────────────────────────────────────
  Pages visited    47
  Total requests   47
  Files found      128

  .css          →    18  ██████████████████
  .js           →    56  ████████████████████████████████████████████████████████
  .json         →    12  ████████████
  .svg          →    32  ████████████████████████████████
  .woff2        →    10  ██████████

  ────────────────────────────────────────────────────────────────
  JS SCAN RESULTS
  ────────────────────────────────────────────────────────────────
  JS scanned       56
  Endpoints found  43
  Secrets found    2
    ▸ google_api_key   analytics.min.js
    ▸ jwt_token        app.bundle.js
  ────────────────────────────────────────────────────────────────
  report saved  →  extensions_found.json
  ────────────────────────────────────────────────────────────────
```

---

## Output: extensions_found.json

```json
{
  "files": {
    "js": [
      "https://target.com/static/js/bundle.js",
      "https://target.com/static/js/vendor.js"
    ],
    "json": [
      "https://target.com/api/config.json"
    ]
  },
  "js_scan": {
    "scanned": ["https://target.com/static/js/bundle.js"],
    "secrets": [
      {
        "type": "google_api_key",
        "matches": ["AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"],
        "source": "https://target.com/static/js/bundle.js"
      }
    ],
    "endpoints": [
      {
        "endpoint": "/api/v1/users",
        "found_in": "https://target.com/static/js/bundle.js"
      }
    ]
  }
}
```

---

## Options

```
usage: webmap.py [-h] -u URL [--js]

options:
  -u, --url   target URL (required)
  --js        scan JS files for secrets & endpoints after crawl
  -h, --help  show this help message and exit
```

---

## How it works

1. Launches a headless Chromium browser via Playwright
2. Visits the target URL and waits for DOM content to load
3. Attaches a **network response listener** — captures every file loaded over the network
4. Parses the DOM for `<a>`, `<script>`, `<link>`, `<img>`, `<source>`, `<iframe>` tags
5. Also scans inline CSS for `url()` and `@import` references
6. Queues new same-domain pages for crawling, records files by extension
7. With `--js`: downloads each JS file, runs regex against 24 secret patterns, extracts API endpoint paths

All crawling stays strictly within the target domain and its subdomains.

---

## Ethical & Legal Warning

> **Use only on targets you have explicit permission to test.**
> Unauthorized scanning is illegal. Always stay in-scope for bug bounty programs or limit use to assets you own.

---

[MIT](LICENSE) © sudokage-sh
