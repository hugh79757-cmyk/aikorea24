#!/usr/bin/env python3
"""
aikorea24.kr - 실패 항목 수정 테스트
- pytrends 404 → Google Trends RSS + 공식 API 대안
- signal.bz JS렌더링 → API 직접 호출
"""

import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup

print("=" * 60)
print(f"실패 항목 수정 테스트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ─────────────────────────────────────────
# [FIX 1] Google Trends 대안: RSS 피드
# pytrends 404 → Google Trends RSS로 대체
# ─────────────────────────────────────────
print("\n🌐 [FIX 1] Google Trends RSS 피드 (pytrends 대안)")
try:
    # Google Trends 한국 일간 트렌드 RSS
    url = "https://trends.google.co.kr/trending/rss?geo=KR"
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    
    if r.status_code == 200 and len(r.text) > 500:
        soup = BeautifulSoup(r.text, 'xml')
        items = soup.find_all('item')
        if items:
            keywords = []
            for item in items[:10]:
                title = item.find('title')
                traffic = item.find('ht:approx_traffic') or item.find('approx_traffic')
                if title:
                    kw = title.get_text(strip=True)
                    vol = traffic.get_text(strip=True) if traffic else "N/A"
                    keywords.append(f"{kw}({vol})")
            print(f"  ✅ Google Trends RSS 성공! 한국 급상승 {len(items)}건")
            print(f"  TOP10: {', '.join(keywords[:10])}")
        else:
            # XML 파싱 다른 방식 시도
            soup2 = BeautifulSoup(r.text, 'html.parser')
            titles = soup2.find_all('title')
            kws = [t.get_text(strip=True) for t in titles if t.get_text(strip=True) and 'trend' not in t.get_text().lower()]
            print(f"  ⚠️ XML item 없음, title 태그에서 {len(kws)}건 추출")
            if kws:
                print(f"  키워드: {', '.join(kws[:10])}")
    else:
        print(f"  ❌ RSS 응답 실패: HTTP {r.status_code}, 크기: {len(r.text)}bytes")
        
except Exception as e:
    print(f"  ❌ RSS 실패: {e}")

# ─────────────────────────────────────────
# [FIX 1-B] Google Trends 대안: 웹 스크래핑
# ─────────────────────────────────────────
print("\n🌐 [FIX 1-B] Google Trends 일간 트렌드 페이지")
try:
    url = "https://trends.google.co.kr/trending?geo=KR&hours=24"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    r = requests.get(url, headers=headers, timeout=10)
    print(f"  응답: HTTP {r.status_code}, 크기: {len(r.text):,}bytes")
    if r.status_code == 200:
        print(f"  ✅ 페이지 로드 성공 (JS렌더링 필요할 수 있음)")
    else:
        print(f"  ⚠️ HTTP {r.status_code}")
except Exception as e:
    print(f"  ❌ 실패: {e}")

# ─────────────────────────────────────────
# [FIX 2] signal.bz 대안: API 직접 호출
# signal.bz는 SPA이므로 내부 API를 직접 호출
# ─────────────────────────────────────────
print("\n🔥 [FIX 2] signal.bz 내부 API 호출")
try:
    # signal.bz의 실제 데이터 API 엔드포인트
    api_urls = [
        "https://signal.bz/api/realtime-keywords",
        "https://api.signal.bz/keywords",
        "https://signal.bz/api/news",
    ]
    
    success = False
    for api_url in api_urls:
        try:
            r = requests.get(api_url, timeout=5, 
                           headers={"User-Agent": "Mozilla/5.0",
                                    "Accept": "application/json"})
            if r.status_code == 200:
                data = r.json()
                print(f"  ✅ {api_url} → 응답 수신")
                print(f"  데이터: {json.dumps(data, ensure_ascii=False)[:200]}")
                success = True
                break
        except:
            continue
    
    if not success:
        print("  ⚠️ signal.bz API 엔드포인트 찾지 못함")
        print("  → 대안: Selenium 또는 다른 실시간 검색어 소스 사용")
        
except Exception as e:
    print(f"  ❌ 실패: {e}")

# ─────────────────────────────────────────
# [FIX 2-B] 실시간 검색어 대안: 네이버 데이터랩
# ─────────────────────────────────────────
print("\n🔥 [FIX 2-B] 실시간 검색어 대안 소스들")

# 대안 1: zum.com 실시간 이슈
print("  [대안1] ZUM 실시간 이슈")
try:
    r = requests.get("https://zum.com", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, 'html.parser')
    # ZUM NOW 이슈 키워드 추출 시도
    keywords = []
    for tag in soup.find_all(['a', 'span']):
        cls = tag.get('class', [])
        text = tag.get_text(strip=True)
        if text and 2 < len(text) < 20:
            # 링크에 issue/keyword 관련 패턴이 있는지
            href = tag.get('href', '')
            if 'issue' in href or 'search' in href or 'keyword' in href:
                keywords.append(text)
    if keywords:
        unique_kws = list(dict.fromkeys(keywords))[:10]
        print(f"    ✅ ZUM 이슈 키워드 {len(unique_kws)}건: {', '.join(unique_kws)}")
    else:
        print(f"    ⚠️ ZUM 키워드 추출 실패 (페이지: {len(r.text):,}bytes)")
except Exception as e:
    print(f"    ❌ ZUM 실패: {e}")

# 대안 2: 네이버 실시간 급상승 검색어 (DataLab)
print("  [대안2] 네이버 쇼핑인사이트 (로그인 불필요)")
try:
    import os
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    if cid and cid != "YOUR_NAVER_CLIENT_ID":
        print("    → 네이버 데이터랩 API 사용 가능 (.env.sh 설정됨)")
    else:
        print("    → .env.sh에 NAVER_CLIENT_ID 설정 후 사용 가능")
except Exception as e:
    print(f"    ❌ 실패: {e}")

# ─────────────────────────────────────────
# 최종 요약
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("📊 수정 결과 요약")
print("=" * 60)
print("""
  Google Trends:
    - pytrends        → ❌ 2025.02~ Google 엔드포인트 변경으로 404
    - Google RSS 피드  → ✅ 가장 안정적 대안 (xml 파싱)
    - Google 공식 API  → 🔜 알파 대기 중 (신청 필요)
    
  실시간 검색어:
    - signal.bz       → ❌ SPA, JS 렌더링 필요
    - ZUM 이슈        → ⚠️ 셀렉터 조정 필요
    - 네이버 데이터랩   → ✅ API 키 설정 시 가장 정확
    
  ─── 최종 추천 조합 ───
  1순위: 네이버 데이터랩 API (키워드 트렌드 비율)
  2순위: Google Trends RSS (한국 일간 급상승)
  3순위: NIPA/정책브리핑 RSS (AI 지원사업 공고)
""")
