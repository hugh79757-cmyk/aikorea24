#!/usr/bin/env python3
"""
aikorea24.kr - 정부 AI 특화 API 테스트
실행: python3 test_gov_ai_apis.py
"""

import os
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup

results = []
def log(name, status, detail=""):
    emoji = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
    results.append({"api": name, "status": status, "detail": detail})
    print(f"  {emoji} [{name}] {detail}")

print("=" * 60)
print(f"정부 AI 특화 API 테스트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ─────────────────────────────────────────
# [1] 정책브리핑 - 과기정통부 RSS (키 불필요)
# ─────────────────────────────────────────
print("\n📡 [1/6] 정책브리핑 과기정통부 RSS")
try:
    url = "https://www.korea.kr/rss/dept_msit.xml"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'xml')
        items = soup.find_all('item')
        ai_items = []
        for item in items:
            title = item.find('title').get_text(strip=True) if item.find('title') else ""
            if any(kw in title for kw in ['AI', '인공지능', '데이터', '디지털', 'ICT']):
                ai_items.append(title[:60])
        log("과기정통부 RSS", "OK",
            f"전체 {len(items)}건, AI관련 {len(ai_items)}건")
        for t in ai_items[:3]:
            print(f"    → {t}")
    else:
        log("과기정통부 RSS", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("과기정통부 RSS", "FAIL", str(e))

# ─────────────────────────────────────────
# [2] 정책브리핑 - 정책뉴스 RSS (AI 필터)
# ─────────────────────────────────────────
print("\n📡 [2/6] 정책브리핑 정책뉴스 RSS (AI 필터)")
try:
    url = "https://www.korea.kr/rss/policy.xml"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'xml')
        items = soup.find_all('item')
        ai_items = []
        for item in items:
            title = item.find('title').get_text(strip=True) if item.find('title') else ""
            desc = item.find('description').get_text(strip=True) if item.find('description') else ""
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            combined = title + " " + desc
            if any(kw in combined for kw in ['AI', '인공지능', '바우처', '데이터', '디지털전환', 'GPT', '생성형']):
                ai_items.append({"title": title[:60], "link": link})
        log("정책뉴스 RSS", "OK",
            f"전체 {len(items)}건, AI관련 {len(ai_items)}건")
        for item in ai_items[:3]:
            print(f"    → {item['title']}")
    else:
        log("정책뉴스 RSS", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("정책뉴스 RSS", "FAIL", str(e))

# ─────────────────────────────────────────
# [3] 보조금통합포털 - 공모사업 API
# ─────────────────────────────────────────
print("\n💰 [3/6] 보조금통합포털 공모사업 API")
try:
    api_key = os.environ.get("DATA_GO_KR_KEY", "")
    if not api_key:
        log("보조금 공모사업", "SKIP", "DATA_GO_KR_KEY 미설정")
    else:
        # 공모사업 목록 API
        url = "https://apis.data.go.kr/B552468/srchFrnrSbsdMng/getOpenBizList"
        params = {
            "serviceKey": api_key,
            "pageNo": "1",
            "numOfRows": "20",
            "type": "json"
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            try:
                data = r.json()
                # AI 관련 공모사업 필터링
                items = data.get("response", {}).get("body", {}).get("items", [])
                if isinstance(items, dict):
                    items = items.get("item", [])
                ai_items = [i for i in items
                           if any(kw in str(i) for kw in ['AI', '인공지능', '바우처', '데이터'])]
                log("보조금 공모사업", "OK",
                    f"전체 {len(items)}건, AI관련 {len(ai_items)}건")
            except:
                log("보조금 공모사업", "WARN", f"JSON 파싱 실패: {r.text[:100]}")
        else:
            log("보조금 공모사업", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("보조금 공모사업", "FAIL", str(e))

# ─────────────────────────────────────────
# [4] NIPA 사업공고 크롤링 (AI 바우처)
# ─────────────────────────────────────────
print("\n📋 [4/6] NIPA 사업공고 크롤링 (AI 바우처)")
try:
    r = requests.get("https://www.nipa.kr/home/2-2",
                     timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        ai_notices = []
        for tag in soup.find_all(['a', 'td', 'span']):
            text = tag.get_text(strip=True)
            if any(kw in text for kw in ['AI', '인공지능', '바우처', '데이터']):
                href = tag.get('href', '')
                if text and len(text) > 5 and text not in [t['title'] for t in ai_notices]:
                    ai_notices.append({"title": text[:70], "href": href})
        unique = {item['title']: item for item in ai_notices}
        log("NIPA 사업공고", "OK", f"AI 관련 {len(unique)}건")
        for title in list(unique.keys())[:5]:
            print(f"    → {title}")
    else:
        log("NIPA 사업공고", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("NIPA 사업공고", "FAIL", str(e))

# ─────────────────────────────────────────
# [5] IRIS R&D 사업공고 크롤링 (AI 과제)
# ─────────────────────────────────────────
print("\n🔬 [5/6] IRIS R&D 사업공고 (AI 과제)")
try:
    url = "https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do"
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        all_text = soup.get_text()
        ai_count = sum(1 for kw in ['AI', '인공지능', '데이터', '디지털']
                      if kw in all_text)
        log("IRIS 사업공고", "OK",
            f"페이지 로드 성공 ({len(r.text):,}bytes), AI키워드 {ai_count}종 발견")
    else:
        log("IRIS 사업공고", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("IRIS 사업공고", "FAIL", str(e))

# ─────────────────────────────────────────
# [6] AI허브 오픈API
# ─────────────────────────────────────────
print("\n🧠 [6/6] AI허브 데이터셋 페이지")
try:
    r = requests.get("https://www.aihub.or.kr/aihubdata/data/view.do",
                     timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        # 데이터셋 수 추출 시도
        text = soup.get_text()
        log("AI허브 데이터셋", "OK",
            f"페이지 로드 성공 ({len(r.text):,}bytes)")

        aihub_key = os.environ.get("AIHUB_API_KEY", "")
        if aihub_key:
            log("AI허브 API키", "OK", "AIHUB_API_KEY 설정됨")
        else:
            log("AI허브 API키", "SKIP",
                "AIHUB_API_KEY 미설정 (https://aihub.or.kr 가입 후 발급)")
    else:
        log("AI허브 데이터셋", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("AI허브 데이터셋", "FAIL", str(e))

# ─── 최종 리포트 ───
print("\n" + "=" * 60)
print("📊 정부 AI API 테스트 결과")
print("=" * 60)
ok = sum(1 for r in results if r["status"] == "OK")
fail = sum(1 for r in results if r["status"] == "FAIL")
skip = sum(1 for r in results if r["status"] == "SKIP")
warn = sum(1 for r in results if r["status"] == "WARN")
print(f"  ✅ 성공: {ok}  ❌ 실패: {fail}  ⚠️ 경고: {warn}  ⏭️ 스킵: {skip}")

print(f"""
━━━━ aikorea24.kr 전체 API 환경변수 목록 ━━━━

[필수 - 즉시 발급 가능]
  NAVER_CLIENT_ID        ← developers.naver.com (검색+데이터랩)
  NAVER_CLIENT_SECRET    ← 위와 동일
  OPENAI_API_KEY         ← platform.openai.com
  DATA_GO_KR_KEY         ← data.go.kr (보조금+공공서비스)

[필수 - 광고 계정 필요]
  NAVER_AD_API_KEY       ← manage.searchad.naver.com
  NAVER_AD_SECRET        ← 위와 동일
  NAVER_AD_CUSTOMER_ID   ← 위와 동일

[선택 - 나중에 발급]
  AIHUB_API_KEY          ← aihub.or.kr (AI 데이터셋)
  INSTAGRAM_ACCESS_TOKEN ← developers.facebook.com
  INSTAGRAM_BUSINESS_ID  ← 위와 동일
  GOOGLE_TRENDS_API_KEY  ← 공식 API 알파 (대기 중)

[키 불필요 - 바로 사용 가능]
  정책브리핑 RSS (과기정통부)  ← korea.kr/rss/dept_msit.xml
  정책브리핑 RSS (정책뉴스)    ← korea.kr/rss/policy.xml
  정책브리핑 RSS (보도자료)    ← korea.kr/rss/pressrelease.xml
  Google Trends RSS          ← trends.google.co.kr/trending/rss?geo=KR
  NIPA 사업공고               ← nipa.kr/home/2-2 (크롤링)
  IRIS R&D 공고               ← iris.go.kr (크롤링)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 환경변수: 13개 (필수 7개 + 선택 4개 + 경로 2개)
키 불필요 소스: 6개
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

# JSON 저장
report_path = "/Users/twinssn/Projects/aikorea24/api_test/test_gov_ai_report.json"
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "results": results
    }, f, ensure_ascii=False, indent=2)
print(f"📄 리포트: {report_path}")
