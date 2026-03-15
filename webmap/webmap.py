#!/usr/bin/env python3
import argparse
import signal
import sys
from urllib.parse import urljoin, urlparse
from collections import defaultdict
import re
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ─── Colors ─────────────────────────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    BRED    = "\033[91m"
    BGREEN  = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE   = "\033[94m"
    BMAGENTA= "\033[95m"
    BCYAN   = "\033[96m"
    BWHITE  = "\033[97m"

    @staticmethod
    def strip(text):
        """Remove all ANSI codes (for clean output if needed)."""
        return re.sub(r'\033\[[0-9;]*m', '', text)


def banner():
    b = C.BCYAN + C.BOLD
    d = C.DIM + C.CYAN
    r = C.RESET
    print(f"""
{b}
  ██╗    ██╗███████╗██████╗ ███╗   ███╗ █████╗ ██████╗
  ██║    ██║██╔════╝██╔══██╗████╗ ████║██╔══██╗██╔══██╗
  ██║ █╗ ██║█████╗  ██████╔╝██╔████╔██║███████║██████╔╝
  ██║███╗██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══██║██╔═══╝
  ╚███╔███╔╝███████╗██████╔╝██║ ╚═╝ ██║██║  ██║██║
   ╚══╝╚══╝ ╚══════╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝
{r}{d}  web crawler for discovering files by extension  │  by sudokage-sh{r}
""")


def line(char="─", width=64, color=C.DIM):
    print(f"{color}{char * width}{C.RESET}")


# ─── Extension color map ────────────────────────────────────────────────────

EXT_COLORS = {
    # Scripts
    "js": C.BYELLOW, "ts": C.BYELLOW, "jsx": C.BYELLOW, "tsx": C.BYELLOW,
    "mjs": C.BYELLOW, "cjs": C.BYELLOW,
    # Styles
    "css": C.BCYAN, "scss": C.BCYAN, "sass": C.BCYAN, "less": C.BCYAN,
    # Images
    "png": C.MAGENTA, "jpg": C.MAGENTA, "jpeg": C.MAGENTA, "gif": C.MAGENTA,
    "svg": C.MAGENTA, "webp": C.MAGENTA, "ico": C.MAGENTA, "avif": C.MAGENTA,
    # Fonts
    "woff": C.BLUE, "woff2": C.BLUE, "ttf": C.BLUE, "eot": C.BLUE, "otf": C.BLUE,
    # Data
    "json": C.BGREEN, "xml": C.BGREEN, "csv": C.BGREEN, "yaml": C.BGREEN, "yml": C.BGREEN,
    # Docs
    "pdf": C.BRED, "doc": C.BRED, "docx": C.BRED, "xls": C.BRED, "xlsx": C.BRED,
    # Archives
    "zip": C.BRED, "tar": C.BRED, "gz": C.BRED, "rar": C.BRED,
    # Config / sensitive
    "env": C.BRED, "bak": C.BRED, "sql": C.BRED, "log": C.BRED, "map": C.BRED,
    "conf": C.BRED, "config": C.BRED,
    # Media
    "mp4": C.BMAGENTA, "mp3": C.BMAGENTA, "webm": C.BMAGENTA,
}

def ext_color(ext: str) -> str:
    return EXT_COLORS.get(ext.lower(), C.WHITE)


# ─── Secret Patterns ────────────────────────────────────────────────────────

SECRET_PATTERNS = {
    "aws_access_key":     r'AKIA[0-9A-Z]{16}',
    "aws_secret_key":     r'(?i)aws.{0,20}[\'"][0-9a-zA-Z/+]{40}[\'"]',
    "google_api_key":     r'AIza[0-9A-Za-z\-_]{35}',
    "google_oauth":       r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
    "github_token":       r'ghp_[0-9a-zA-Z]{36}',
    "github_oauth":       r'gho_[0-9a-zA-Z]{36}',
    "github_pat":         r'github_pat_[0-9a-zA-Z_]{82}',
    "stripe_live":        r'sk_live_[0-9a-zA-Z]{24,}',
    "stripe_test":        r'sk_test_[0-9a-zA-Z]{24,}',
    "stripe_publishable": r'pk_(live|test)_[0-9a-zA-Z]{24,}',
    "slack_token":        r'xox[baprs]-[0-9a-zA-Z\-]{10,}',
    "slack_webhook":      r'https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+',
    "jwt_token":          r'eyJ[A-Za-z0-9\-_=]{10,}\.[A-Za-z0-9\-_=]{10,}\.[A-Za-z0-9\-_.+/=]{10,}',
    "bearer_token":       r'(?i)bearer\s+[a-zA-Z0-9\-_=]{30,}',
    "private_key":        r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
    "firebase_key":       r'AAAA[A-Za-z0-9_-]{7}:[A-Za-z0-9_-]{140}',
    "twilio_sid":         r'AC[a-z0-9]{32}',
    "mailgun_key":        r'key-[0-9a-zA-Z]{32}',
    "sendgrid_key":       r'SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}',
    "npm_token":          r'npm_[A-Za-z0-9]{36}',
    "generic_api_key":    r'(?i)["\']?api[_\-]?key["\']?\s*[:=]\s*["\']([a-zA-Z0-9\-_]{32,})["\']',
    "generic_secret":     r'(?i)["\']?secret[_\-]?key["\']?\s*[:=]\s*["\']([a-zA-Z0-9\-_]{32,})["\']',
    "generic_token":      r'(?i)["\']?access[_\-]?token["\']?\s*[:=]\s*["\']([a-zA-Z0-9\-_\.]{32,})["\']',
    "source_map":         r'//[#@]\s*sourceMappingURL=(.+\.map)',
    "internal_ip":        r'(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}',
}

JS_SKIP_DOMAINS = {
    "google-analytics.com", "googletagmanager.com", "doubleclick.net",
    "facebook.net", "twitter.com", "linkedin.com", "youtube.com",
    "cloudflare.com", "jquery.com", "bootstrapcdn.com", "jsdelivr.net",
    "cdnjs.cloudflare.com", "unpkg.com",
}


def scan_secrets(content: str, source: str = "unknown") -> list:
    findings = []
    for name, pattern in SECRET_PATTERNS.items():
        try:
            matches = re.findall(pattern, content)
            if matches:
                unique = list(set([m if isinstance(m, str) else m[0] for m in matches]))
                findings.append({"type": name, "matches": unique[:5], "source": source})
        except Exception:
            pass
    return findings


def should_skip_js(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        return any(skip in domain for skip in JS_SKIP_DOMAINS)
    except Exception:
        return False


# ─── Main Class ─────────────────────────────────────────────────────────────

class ExtensionHunter:
    def __init__(self, start_url: str, scan_js: bool = False):
        self.start_url = start_url.rstrip('/')
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.queue = asyncio.Queue()
        self.found_files = defaultdict(list)
        self.network_files = defaultdict(list)
        self.request_count = 0
        self.running = True
        self.scan_js = scan_js

        self.js_secret_findings = []
        self.js_scanned_urls = set()
        self.js_endpoints = []

    def is_same_domain(self, url: str) -> bool:
        netloc = urlparse(url).netloc
        return netloc == self.domain or netloc.endswith('.' + self.domain)

    def get_extension(self, path: str) -> str | None:
        path = path.split('?')[0].split('#')[0].rstrip('/')
        if not path or path.endswith('/'):
            return None
        filename = path.split('/')[-1]
        if '.' not in filename:
            return None
        ext = filename.rsplit('.', 1)[-1].lower()
        if not ext or len(ext) > 10:
            return None
        return ext

    def record_file(self, url: str, source: str = "dom"):
        ext = self.get_extension(urlparse(url).path)
        if ext:
            bucket = self.found_files if source == "dom" else self.network_files
            if url not in bucket[ext]:
                bucket[ext].append(url)
                clr = ext_color(ext)
                tag = f"{C.DIM}[{C.RESET}{C.BBLUE}NET{C.RESET}{C.DIM}]{C.RESET}" if source == "net" \
                      else f"{C.DIM}[{C.RESET}{C.DIM}DOM{C.RESET}{C.DIM}]{C.RESET}"
                print(f"  {tag} {C.DIM}→{C.RESET} {clr}.{ext:<10}{C.RESET}  {C.DIM}{url}{C.RESET}")

    async def discover_links(self, page) -> set:
        links = set()
        selectors = [
            'a[href]', 'link[href]', 'script[src]', 'img[src]', 'img[data-src]',
            'source[src]', 'iframe[src]', '[data-src]', '[data-lazy-src]', '[data-original]'
        ]
        for sel in selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    for attr in ['href', 'src', 'data-src', 'data-lazy-src', 'data-original']:
                        val = await el.get_attribute(attr)
                        if val:
                            full = urljoin(page.url, val.strip())
                            if self.is_same_domain(full) and full not in self.visited:
                                links.add(full)
            except Exception:
                pass

        try:
            content = await page.content()
            for pattern in [
                r'''url\((?:"|')?([^"')]+)(?:"|')?\)''',
                r'''@import\s+(?:"|')?([^"')]+)'''
            ]:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    lnk = urljoin(page.url, match.group(1).strip())
                    if self.is_same_domain(lnk):
                        links.add(lnk)
        except Exception:
            pass

        to_visit = set()
        for link in links:
            ext = self.get_extension(urlparse(link).path)
            if ext:
                self.record_file(link, source="dom")
            else:
                to_visit.add(link)
        return to_visit

    def setup_network_listener(self, page):
        async def on_response(response):
            url = response.url
            if not self.is_same_domain(url):
                return
            ext = self.get_extension(urlparse(url).path)
            if ext and url not in self.network_files[ext]:
                self.record_file(url, source="net")
        page.on("response", on_response)

    async def process_url(self, url: str, context):
        if not self.running or url in self.visited:
            return
        self.visited.add(url)
        self.request_count += 1

        num  = f"{C.DIM}{self.request_count:5d}{C.RESET}"
        tag  = f"{C.BOLD}{C.BCYAN}visiting{C.RESET}"
        print(f"\n  {num}  {tag}  {C.WHITE}{url}{C.RESET}")

        page = None
        try:
            page = await context.new_page()
            self.setup_network_listener(page)
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)
            new_paths = await self.discover_links(page)
            for path in new_paths:
                await self.queue.put(path)
        except PlaywrightTimeoutError:
            print(f"  {C.YELLOW}⚠ timeout{C.RESET}  {C.DIM}{url}{C.RESET}")
        except Exception as e:
            print(f"  {C.RED}✖ error{C.RESET}   {C.DIM}{str(e)[:80]}{C.RESET}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def scan_js_files(self, context):
        all_js_urls = set(self.found_files.get("js", [])) | set(self.network_files.get("js", []))

        if not all_js_urls:
            print(f"\n  {C.YELLOW}⚠ no JS files found to scan{C.RESET}")
            return

        line()
        print(f"  {C.BOLD}{C.BYELLOW}JS SCAN{C.RESET}  {C.DIM}→ {len(all_js_urls)} file(s){C.RESET}")
        line()

        page = None
        try:
            page = await context.new_page()
            for url in all_js_urls:
                if not self.running:
                    break
                if url in self.js_scanned_urls or should_skip_js(url):
                    continue
                self.js_scanned_urls.add(url)
                fname = url.split('/')[-1][:55]
                try:
                    resp = await page.request.get(url, timeout=15000)
                    content = await resp.text()

                    findings = scan_secrets(content, source=url)
                    if findings:
                        self.js_secret_findings.extend(findings)
                        for f in findings:
                            print(f"  {C.BRED}[SECRET]{C.RESET} {C.BOLD}{f['type']}{C.RESET}  {C.DIM}{fname}{C.RESET}")

                    endpoints = re.findall(r'["`\']((?:/[a-zA-Z0-9_\-\.]+){2,})["`\']', content)
                    for ep in set(endpoints):
                        if not any(s in ep for s in ["/node_modules/", "//", "*"]):
                            entry = {"endpoint": ep, "found_in": url}
                            if entry not in self.js_endpoints:
                                self.js_endpoints.append(entry)

                    maps = re.findall(r'//[#@]\s*sourceMappingURL=(.+)', content)
                    for m in maps:
                        m = m.strip()
                        if not m.startswith("data:"):
                            map_url = m if m.startswith("http") else urljoin(url, m)
                            print(f"  {C.BRED}[SOURCEMAP]{C.RESET} {C.DIM}{map_url}{C.RESET}")

                    status = f"{C.BGREEN}✔{C.RESET}" if not findings else f"{C.BRED}!{C.RESET}"
                    print(f"  {status} {C.DIM}{fname}{C.RESET}")

                except Exception as e:
                    print(f"  {C.RED}✖{C.RESET} {C.DIM}{fname}: {str(e)[:60]}{C.RESET}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def crawl(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/130.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800},
                ignore_https_errors=True,
            )

            await self.queue.put(self.start_url)
            while self.running and not self.queue.empty():
                url = await self.queue.get()
                await self.process_url(url, context)

            if self.scan_js and self.running:
                await self.scan_js_files(context)

            await browser.close()
            self.save_report()

    def save_report(self):
        all_files = defaultdict(list)
        for ext, urls in self.found_files.items():
            all_files[ext].extend(urls)
        for ext, urls in self.network_files.items():
            for url in urls:
                if url not in all_files[ext]:
                    all_files[ext].append(url)

        report = {}
        total = 0
        for ext in sorted(all_files.keys()):
            unique = sorted(set(all_files[ext]))
            report[ext] = unique
            total += len(unique)

        line()
        print(f"  {C.BOLD}{C.BWHITE}SCAN COMPLETE{C.RESET}")
        line()
        print(f"  {C.DIM}Pages visited   {C.RESET}{C.BOLD}{len(self.visited)}{C.RESET}")
        print(f"  {C.DIM}Total requests  {C.RESET}{C.BOLD}{self.request_count}{C.RESET}")

        if total == 0:
            print(f"\n  {C.YELLOW}nothing found{C.RESET}")
        else:
            print(f"  {C.DIM}Files found     {C.RESET}{C.BOLD}{total}{C.RESET}\n")
            for ext in sorted(report.keys()):
                clr = ext_color(ext)
                bar_len = min(len(report[ext]), 30)
                bar = "█" * bar_len
                print(f"  {clr}.{ext:<12}{C.RESET} {C.DIM}→{C.RESET}  {C.BOLD}{len(report[ext]):4d}{C.RESET}  {C.DIM}{bar}{C.RESET}")

        output = {"files": report}

        if self.scan_js:
            line()
            print(f"  {C.BOLD}{C.BYELLOW}JS SCAN RESULTS{C.RESET}")
            line()
            print(f"  {C.DIM}JS scanned      {C.RESET}{C.BOLD}{len(self.js_scanned_urls)}{C.RESET}")
            print(f"  {C.DIM}Endpoints found {C.RESET}{C.BOLD}{len(self.js_endpoints)}{C.RESET}")
            if self.js_secret_findings:
                print(f"  {C.BRED}Secrets found   {C.RESET}{C.BOLD}{C.BRED}{len(self.js_secret_findings)}{C.RESET}")
                for f in self.js_secret_findings:
                    fname = f['source'].split('/')[-1][:50]
                    print(f"  {C.BRED}  ▸ {f['type']}{C.RESET}  {C.DIM}{fname}{C.RESET}")
            else:
                print(f"  {C.BGREEN}Secrets found   0{C.RESET}")

            output["js_scan"] = {
                "scanned": list(self.js_scanned_urls),
                "secrets": self.js_secret_findings,
                "endpoints": self.js_endpoints[:200],
            }

        with open("extensions_found.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        line()
        print(f"  {C.BGREEN}report saved{C.RESET}  {C.DIM}→ extensions_found.json{C.RESET}")
        line()
        print()

    def stop(self):
        self.running = False


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="webmap - web crawler for discovering files by extension",
        epilog="stop and save with ctrl+c",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-u", "--url", required=True, help="target URL")
    parser.add_argument("--js", action="store_true",
                        help="scan JS files for secrets & endpoints after crawl")
    args = parser.parse_args()

    if not args.url.startswith(('http://', 'https://')):
        args.url = 'https://' + args.url

    banner()
    line()
    print(f"  {C.DIM}target   {C.RESET}{C.BOLD}{C.BCYAN}{args.url}{C.RESET}")
    print(f"  {C.DIM}time     {C.RESET}{C.DIM}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.RESET}")
    print(f"  {C.DIM}js scan  {C.RESET}{C.BGREEN + 'enabled' + C.RESET if args.js else C.DIM + 'disabled  (use --js to enable)' + C.RESET}")
    print(f"  {C.DIM}stop     {C.RESET}{C.DIM}ctrl+c saves report and exits{C.RESET}")
    line()

    hunter = ExtensionHunter(start_url=args.url, scan_js=args.js)

    def signal_handler(sig, frame):
        print(f"\n  {C.YELLOW}⚠ stopping scan...{C.RESET}")
        hunter.stop()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        asyncio.run(hunter.crawl())
    except KeyboardInterrupt:
        hunter.stop()


if __name__ == "__main__":
    main()
