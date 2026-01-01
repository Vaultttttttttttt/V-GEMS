"""
Official Website Collection Script - Using Selenium

Strategy:
1. Use Selenium + undetected-chromedriver to bypass bot detection
2. Construct pagination URLs manually (q=keyword&first=11, first=21, etc.)
3. Extract all result URLs from each page
4. Save to JSON

Target: 1000 websites
"""

import json
from pathlib import Path
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time

# Configuration
OUTPUT_DIR = Path("generated_dataset")
WEBSITES_FILE = OUTPUT_DIR / "official_websites.json"
TARGET_TOTAL = 1000

# Target counts for each category
TARGET_MATRIX = {
    ("education", "cn"): 280,
    ("education", "en"): 183,
    ("conference", "cn"): 145,
    ("conference", "en"): 95,
    ("game", "cn"): 133,
    ("game", "en"): 86,
    ("organization", "cn"): 47,
    ("organization", "en"): 31,
}

# Search keywords
KEYWORDS = {
    ("education", "cn"): ["大学官网", "高校官网", "中国大学", "211大学", "985大学"],
    ("education", "en"): ["university official website", "college official website", "edu official website", "school official website"],
    ("conference", "cn"): ["学术会议官网", "国际会议", "学术研讨会", "国际论坛"],
    ("conference", "en"): ["conference official website", "symposium official website", "workshop official website", "summit official website"],
    ("game", "cn"): ["游戏官网", "游戏公司", "网络游戏", "手机游戏"],
    ("game", "en"): ["game official website", "gaming official website", "videogame official website"],
    ("organization", "cn"): ["协会官网", "学会官网", "组织官网", "基金会"],
    ("organization", "en"): ["organization official website", "association official website", "foundation official website", "institute official website"],
}


class SeleniumCollector:
    def __init__(self):
        self.websites = {}
        OUTPUT_DIR.mkdir(exist_ok=True)
        self.driver = None

    def load_existing(self):
        """Load existing websites."""
        if WEBSITES_FILE.exists():
            with open(WEBSITES_FILE, 'r', encoding='utf-8') as f:
                self.websites = json.load(f)
            print(f"✓ Loaded {len(self.websites)} existing websites")

    def save(self):
        """Save websites to file."""
        with open(WEBSITES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.websites, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved {len(self.websites)} websites")

    def count(self, domain, lang):
        """Count websites for a specific category."""
        return sum(
            1 for url, info in self.websites.items()
            if isinstance(info, dict) and info.get("domain") == domain and info.get("lang") == lang
        )

    def init_driver(self, lang="en"):
        """
        Initialize Selenium driver.

        IMPORTANT: Must use visible browser (no --headless) to bypass Bing detection.
        Headless mode causes Bing to return same results for all pages.
        """
        options = uc.ChromeOptions()
        # Do NOT add --headless - it breaks pagination
        options.add_argument('--lang=zh-CN' if lang == "cn" else '--lang=en-US')
        options.add_argument('--disable-blink-features=AutomationControlled')

        self.driver = uc.Chrome(options=options)

    def close_driver(self):
        """Close Selenium driver."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def fetch_page(self, url):
        """Fetch a page and extract result URLs."""
        print(f"    Fetching: {url[:80]}...")

        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Extract result URLs
            result_urls = []
            for result_item in soup.find_all('li', class_='b_algo'):
                link = result_item.find('a', href=True)
                if link:
                    url = link['href']
                    if url.startswith('http') and 'bing.com' not in url:
                        result_urls.append(url)

            return result_urls

        except Exception as e:
            print(f"      [ERROR] {e}")
            return []

    def collect_with_pagination(self, keyword, lang, max_pages=20):
        """
        Collect URLs by constructing pagination URLs directly.

        Key insight: Don't follow HTML next links - they contain tracking params.
        Instead, construct URLs manually:
        - Page 1: q=keyword
        - Page 2: q=keyword&first=11
        - Page 3: q=keyword&first=21
        """
        keyword_encoded = keyword.replace(' ', '+')

        all_urls = []

        for page_num in range(1, max_pages + 1):
            # Construct URL
            if page_num == 1:
                if lang == "cn":
                    page_url = f"https://cn.bing.com/search?q={keyword_encoded}"
                else:
                    page_url = f"https://www.bing.com/search?q={keyword_encoded}&setlang=en&cc=US"
            else:
                first_value = (page_num - 1) * 10 + 1
                if lang == "cn":
                    page_url = f"https://cn.bing.com/search?q={keyword_encoded}&first={first_value}"
                else:
                    page_url = f"https://www.bing.com/search?q={keyword_encoded}&first={first_value}&setlang=en&cc=US"

            print(f"  Page {page_num}:")

            # Fetch page
            result_urls = self.fetch_page(page_url)

            if not result_urls:
                print(f"    No results, stopping")
                break

            print(f"    Found {len(result_urls)} results")
            all_urls.extend(result_urls)

            time.sleep(2)  # Delay between pages

        return all_urls

    def collect_category(self, domain, lang, target):
        """Collect websites for one category."""
        keywords = KEYWORDS[(domain, lang)]

        print(f"\n{'='*70}")
        print(f"Collecting: {domain} ({lang}) - Target: {target}")
        print(f"{'='*70}")

        current = self.count(domain, lang)
        if current >= target:
            print(f"✓ Already have {current}/{target}")
            return

        print(f"Current: {current}/{target}, Need: {target - current}\n")

        # Initialize driver for this language
        self.init_driver(lang)

        try:
            for keyword in keywords:
                if current >= target:
                    break

                print(f"Keyword: '{keyword}'")

                # Collect URLs with pagination
                urls = self.collect_with_pagination(keyword, lang, max_pages=20)

                print(f"  Total: {len(urls)} URLs from all pages")

                # Add URLs to collection
                for url in urls:
                    if url in self.websites:
                        continue

                    self.websites[url] = {"domain": domain, "lang": lang}
                    current += 1
                    print(f"    [{current}/{target}] {url[:70]}")

                    if current % 20 == 0:
                        self.save()

                    if current >= target:
                        break

                time.sleep(2)  # Delay between keywords

        finally:
            self.close_driver()

        self.save()

    def collect_all(self):
        """Collect all 1000 websites."""
        print(f"\nTarget: {TARGET_TOTAL} websites\n")

        for (domain, lang), target in TARGET_MATRIX.items():
            self.collect_category(domain, lang, target)

        # Final statistics
        print("\n" + "="*70)
        print("COLLECTION COMPLETE")
        print("="*70 + "\n")

        for (domain, lang), target in TARGET_MATRIX.items():
            collected = self.count(domain, lang)
            status = "✓" if collected >= target else "✗"
            print(f"{domain:15} ({lang}): {collected:4}/{target:4} {status}")

        total = len(self.websites)
        cn_total = sum(self.count(d, "cn") for d in ["education", "conference", "game", "organization"])
        en_total = sum(self.count(d, "en") for d in ["education", "conference", "game", "organization"])

        print(f"\nTotal: {total}/{TARGET_TOTAL}")
        if total > 0:
            print(f"Chinese: {cn_total} ({cn_total/total*100:.1f}%)")
            print(f"English: {en_total} ({en_total/total*100:.1f}%)")


def main():
    collector = SeleniumCollector()
    collector.load_existing()
    collector.collect_all()


if __name__ == "__main__":
    main()
