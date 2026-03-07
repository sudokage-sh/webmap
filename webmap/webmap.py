#!/usr/bin/env python3

import argparse
import signal
import sys
from urllib.parse import urljoin, urlparse
from collections import defaultdict
import re
import json
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

class ExtensionHunter:
    def __init__(self, start_url: str):
        self.start_url = start_url.rstrip('/')
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.queue = asyncio.Queue()
        self.found_files = defaultdict(list)  # ext -> [url, ...]
        self.request_count = 0
        self.running = True

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
        if not ext:
            return None
        return ext

    async def discover_extensions(self, page) -> set:
        links = set()

        selectors = [
            'a[href]', 'link[href]', 'script[src]', 'img[src]', 'img[data-src]',
            'source[src]', 'iframe[src]', '[data-src]', '[data-lazy-src]', '[data-original]'
        ]

        for sel in selectors:
            elements = await page.query_selector_all(sel)
            for el in elements:
                for attr in ['href', 'src', 'data-src', 'data-lazy-src', 'data-original']:
                    val = await el.get_attribute(attr)
                    if val:
                        full = urljoin(page.url, val.strip())
                        if self.is_same_domain(full) and full not in self.visited:
                            links.add(full)

        content = await page.content()
        for pattern in [
            r'''url\((?:"|')?([^"')]+)(?:"|')?\)''',
            r'''@import\s+(?:"|')?([^"')]+)'''
        ]:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                lnk = urljoin(page.url, match.group(1).strip())
                if self.is_same_domain(lnk):
                    links.add(lnk)

        to_visit = set()
        for link in links:
            ext = self.get_extension(urlparse(link).path)
            if ext:
                self.found_files[ext].append(link)
                print(f"  → .{ext:<10}  {link}")
            else:
                to_visit.add(link)

        return to_visit

    async def process_url(self, url: str, browser):
        if not self.running or url in self.visited:
            return

        self.visited.add(url)
        self.request_count += 1
        print(f"{self.request_count:5d} Visiting page: {url}")

        context = None
        page = None
        try:
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800},
                ignore_https_errors=True
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            new_paths = await self.discover_extensions(page)
            for path in new_paths:
                await self.queue.put(path)

        except PlaywrightTimeoutError:
            print(f"  Timeout → {url}")
        except Exception as e:
            print(f"  Error → {url}: {str(e)[:80]}")
        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass
            if context:
                try:
                    await context.close()
                except:
                    pass

    async def crawl(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )

            await self.queue.put(self.start_url)

            while self.running and not self.queue.empty():
                url = await self.queue.get()
                await self.process_url(url, browser)

            await browser.close()
            self.save_report()

    def save_report(self):
        report = {}
        total = 0
        for ext in sorted(self.found_files.keys()):
            unique = sorted(set(self.found_files[ext]))
            report[ext] = unique
            total += len(unique)

        print(f"\n--- Scanning Has Been Stopped ---")
        print(f"Total Visited Pages: {len(self.visited)}")
        print(f"Total Requests: {self.request_count}")

        if total == 0:
            print("Nothing Found.")
        else:
            print(f"Total Number of Files Found: {total}")
            for ext in sorted(report.keys()):
                print(f".{ext:12} → {len(report[ext]):6d}")

        with open("extensions_found.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("Report Saved → extensions_found.json")

    def stop(self):
        self.running = False


def signal_handler(sig, frame):
    print("\nScanning is being stopped...")
    hunter.stop() 


hunter = None  


def main():
    global hunter

    parser = argparse.ArgumentParser(description="webmap - stop and save with ctrl+c")
    parser.add_argument("-u", "--url", required=True, help="Target URL")

    args = parser.parse_args()

    if not args.url.startswith(('http://', 'https://')):
        args.url = 'https://' + args.url

    print(f"webmap starting → {args.url}")
    print("stop and save with ctrl+c \n")

    hunter = ExtensionHunter(start_url=args.url)


    signal.signal(signal.SIGINT, signal_handler)

    try:
        asyncio.run(hunter.crawl())
    except KeyboardInterrupt:
        hunter.stop()

        if hunter.running == False:
            hunter.save_report()


if __name__ == "__main__":
    main()
