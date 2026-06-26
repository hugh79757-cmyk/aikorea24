import requests
import feedparser
from bs4 import BeautifulSoup
import time

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
TIMEOUT = 15

SOURCES = [
    ("AI타임스", "https://www.aitimes.com/rss/index.xml"),
    ("전자신문", "https://www.etnews.com/rss/etnews.xml"),
    ("The Decoder", "https://the-decoder.com/feed/"),
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Hacker News", "https://hnrss.org/newest?q=AI"),
    ("MarkTechPost", "https://marktechpost.com/feed/"),
    ("Wired", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("AI News EU", "https://www.artificialintelligence-news.com/feed/"),
]

CONTENT_SELECTORS = [
    "article", "main", ".content", ".post-content", ".entry-content",
    ".article-content", "#article-content", ".story-body",
    ".article-body", ".post-body", '[itemprop="articleBody"]',
]


def extract_text(soup):
    for sel in CONTENT_SELECTORS:
        elem = soup.select_one(sel)
        if elem:
            text = elem.get_text(strip=True)
            if len(text) > 100:
                return text
    body = soup.find("body")
    return body.get_text(strip=True) if body else ""


def test_source(name, rss_url):
    result = {"name": name, "rss_url": rss_url, "article_url": "", "status": 0, "body_len": 0, "ok": False}
    try:
        resp = requests.get(rss_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            return result
        article_url = feed.entries[0].link
        result["article_url"] = article_url
        ar = requests.get(article_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
        result["status"] = ar.status_code
        if ar.status_code != 200:
            return result
        soup = BeautifulSoup(ar.text, "html.parser")
        text = extract_text(soup)
        result["body_len"] = len(text)
        result["ok"] = len(text) >= 500
    except Exception as e:
        result["error"] = str(e)
    return result


def main():
    print(f"{'소스명':<14} {'RSS 정상':<8} {'기사 URL':<60} {'HTTP':<6} {'본문길이':<10} {'크롤링':<8}")
    print("-" * 110)
    for name, rss_url in SOURCES:
        r = test_source(name, rss_url)
        status_str = str(r.get("status", 0)) if not r.get("error") else "ERR"
        ok_str = "✅ 가능" if r["ok"] else "❌ 불가"
        article_display = r["article_url"][:57] + ".." if len(r["article_url"]) > 59 else r["article_url"]
        print(f"{r['name']:<14} {'✅' if r['article_url'] else '❌':<8} {article_display:<60} {status_str:<6} {r['body_len']:<10} {ok_str:<8}")
        if r.get("error"):
            print(f"  └─ 오류: {r['error']}")
        time.sleep(1)


if __name__ == "__main__":
    main()
