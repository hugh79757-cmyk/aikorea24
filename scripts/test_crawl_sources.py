import requests
import xml.etree.ElementTree as ET
import json
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}
TIMEOUT = 15

SOURCES = {
    # English AI/tech news sources
    "The Decoder": "https://the-decoder.com/feed/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "MarkTechPost": "https://marktechpost.com/feed/",
    "Fast Company AI": "https://www.fastcompany.com/feed",
    "Hacker News": "https://hnrss.org/newest?q=AI",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "AI News EU": "https://www.artificialintelligence-news.com/feed/",
    "Financial Times AI": "https://www.ft.com/rss/ai",
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "GitHub Blog": "https://github.blog/feed/",
    "HuggingFace Blog": "https://huggingface.co/blog/feed.xml",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "Nature ML": "https://www.nature.com/natmachintell.rss",
    "VentureBeat AI": "https://venturebeat.com/feed/",
    "The Guardian AI": "https://www.theguardian.com/technology/rss",
    "Guardian US News": "https://www.theguardian.com/us-news/rss",
    "SCMP China Tech": "https://www.scmp.com/rss/91/feed",
    "ZDNET AI": "https://www.zdnet.com/news/rss.xml",
    "Dev.to AI": "https://dev.to/feed/tag/artificial-intelligence",
    "NYT Technology": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "NYT AI Spotlight": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "CNN Technology": "http://rss.cnn.com/rss/tech_news.rss",
    "BBC Technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "CNBC Tech": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "Ars Technica AI": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "The Next Web": "https://thenextweb.com/feed/",
    "Washington Post Technology": "https://feeds.washingtonpost.com/rss/world",
    "Politico EU Tech": "https://www.politico.eu/feed/",
    "Al Jazeera AI (via Google News)": None,
    "Anthropic News (via Google News)": None,
    "Reuters Technology (via Google News)": None,
    "Axios": "https://api.axios.com/feed/",
    "Ben's Bites": "https://bensbites.beehiiv.com/feed",
    "Interconnects AI": "https://interconnects.substack.com/feed",
    "City AM": "https://www.cityam.com/feed/",
    "Herald Scotland": "https://www.heraldscotland.com/feed",
    "Memphis Flyer": "https://www.memphisflyer.com/feed",
    "NL Times": "https://nltimes.nl/rss",
    "The National News": "https://www.thenationalnews.com/arc/outboundfeeds/rss/",

    # Korean news sources
    "AI타임스": "https://www.aitimes.com/rss/all.xml",
    "IT조선": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    "인공지능신문": "https://www.ai-news.co.kr/rss",
    "디지털투데이": "https://www.dt.co.kr/rss",
    "전자신문": "https://www.etnews.com/rss",
    "네이버뉴스": None,
    "naver": None,

    # Korean government sources
    "과학기술정보통신부": None,
    "과기부 보도자료": None,
    "과기부 사업공고": None,
    "산업통상부": None,
    "중소벤처기업부": None,
    "금융위원회": None,
    "문화체육관광부": None,
    "보건복지부": None,
    "농림축산식품부": None,
    "기후에너지환경부": None,
    "해양수산부": None,
    "행정안전부": None,
    "정부공문서(정책보고서)": None,
    "서울특별시": None,
    "부산광역시": None,
    "대구광역시": None,
    "인천광역시": None,
    "광주광역시": None,
    "대전광역시": None,
    "울산광역시": None,
    "세종특별자치시": None,
    "경기도": None,
    "강원특별자치도": None,
    "충청북도": None,
    "충청남도": None,
    "전북특별자치도": None,
    "전라남도": None,
    "경상북도": None,
    "경상남도": None,
    "제주특별자치도": None,
}


def fetch_rss(url):
    if url is None:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            print(f"  RSS HTTP {resp.status_code}")
            return None
        # Try alternate RSS URL if first one fails
        root = ET.fromstring(resp.content)
        entries = []
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            link = entry.find("{http://www.w3.org/2005/Atom}link")
            if link is not None:
                href = link.get("href")
                if href:
                    entries.append(href)
        for item in root.iter("item"):
            link = item.find("link")
            if link is not None and link.text:
                entries.append(link.text)
        if not entries:
            # Try Atom links differently
            for link in root.iter("{http://www.w3.org/2005/Atom}link"):
                href = link.get("href")
                if href and ("http" in href):
                    entries.append(href)
        print(f"  Found {len(entries)} entries in RSS")
        return entries[:5]
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")
        return None
    except Exception as e:
        print(f"  RSS error: {e}")
        return None


def try_alternate_rss(source, entries):
    """Try alternate RSS URLs if the primary one failed."""
    alternates = {
        "AI타임스": ["https://www.aitimes.com/feed"],
        "IT조선": ["https://www.chosun.com/arc/outboundfeeds/rss/"],
        "Hacker News": ["https://hnrss.org/frontpage?q=artificial+intelligence"],
        "AI News EU": ["https://www.artificialintelligence-news.com/feed/"],
        "Politico EU Tech": ["https://www.politico.eu/feed/rss/"],
    }
    if source in alternates:
        for alt_url in alternates[source]:
            print(f"  Trying alternate RSS: {alt_url}")
            result = fetch_rss(alt_url)
            if result and result.get("entries"):
                return result
    return None


def crawl_article(url, source_name):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        status = resp.status_code
        content = resp.text
        content_len = len(content)
        if status != 200:
            return {"status": status, "content_length": content_len, "error": f"HTTP {status}"}

        # Try to extract main content using BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        meaningful_len = len(text)
        return {
            "status": status,
            "content_length": content_len,
            "meaningful_length": meaningful_len,
            "title": soup.title.string.strip() if soup.title and soup.title.string else None
        }
    except Exception as e:
        return {"status": 0, "content_length": 0, "error": str(e)}


def main():
    results = {"crawlable": [], "rss_only": [], "no_rss": []}

    for source, rss_url in SOURCES.items():
        print(f"\n{'='*60}")
        print(f"Source: {source}")
        print(f"{'='*60}")

        if rss_url is None:
            print("  NO RSS (None)")
            results["no_rss"].append({
                "name": source,
                "reason": "RSS URL not available / government source / API-based"
            })
            continue

        # Step 1: Fetch RSS
        print(f"  RSS URL: {rss_url}")
        entries = fetch_rss(rss_url)
        if not entries:
            results["rss_only"].append({
                "name": source,
                "rss_url": rss_url,
                "reason": "RSS feed not reachable or empty"
            })
            continue

        # Step 2: Crawl first article
        article_url = entries[0]
        print(f"  Article URL: {article_url}")
        crawl_result = crawl_article(article_url, source)

        if crawl_result.get("status") == 200 and crawl_result.get("meaningful_length", 0) > 100:
            print(f"  CRAWLABLE | HTTP {crawl_result['status']} | Content: {crawl_result['meaningful_length']} chars | Title: {crawl_result.get('title', 'N/A')}")
            results["crawlable"].append({
                "name": source,
                "rss_url": rss_url,
                "article_url": article_url,
                "avg_content_length": crawl_result["meaningful_length"],
                "status": crawl_result["status"]
            })
        else:
            reason = crawl_result.get("error", f"HTTP {crawl_result['status']}, content={crawl_result.get('meaningful_length', 0)}")
            print(f"  RSS ONLY | {reason}")
            results["rss_only"].append({
                "name": source,
                "rss_url": rss_url,
                "reason": f"Article crawl failed: {reason}"
            })

        time.sleep(0.5)

    # Save results
    out_path = "/Users/twinssn/Projects/aikorea24/config/crawlable_sources.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Crawlable: {len(results['crawlable'])} sources")
    for s in results["crawlable"]:
        print(f"  - {s['name']}: {s['rss_url']}")
    print(f"RSS only: {len(results['rss_only'])} sources")
    for s in results["rss_only"]:
        print(f"  - {s['name']}: {s['reason']}")
    print(f"No RSS: {len(results['no_rss'])} sources")
    for s in results["no_rss"]:
        print(f"  - {s['name']}: {s['reason']}")
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
