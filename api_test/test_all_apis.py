#!/usr/bin/env python3
"""
aikorea24.kr - 전체 API 연결 테스트
실행: python3 test_all_apis.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta

# ─── 결과 저장 ───
results = []
def log(api_name, status, detail=""):
    emoji = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
    results.append({"api": api_name, "status": status, "detail": detail})
    print(f"{emoji} [{api_name}] {status} - {detail}")

print("=" * 60)
print(f"aikorea24.kr API 테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ─────────────────────────────────────────
# [TEST 1] 네이버 뉴스 검색 API
# ─────────────────────────────────────────
print("\n📰 [1/10] 네이버 뉴스 검색 API")
try:
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    csc = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or cid == "YOUR_NAVER_CLIENT_ID":
        log("네이버 뉴스 검색", "SKIP", "NAVER_CLIENT_ID 미설정")
    else:
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csc}
        params = {"query": "인공지능 AI", "display": 5, "sort": "date"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if "items" in data and len(data["items"]) > 0:
            log("네이버 뉴스 검색", "OK", f"뉴스 {data['total']}건, 첫 제목: {data['items'][0]['title'][:40]}")
        else:
            log("네이버 뉴스 검색", "FAIL", f"응답: {r.text[:100]}")
except Exception as e:
    log("네이버 뉴스 검색", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 2] 네이버 블로그 검색 API (포화도 계산용)
# ─────────────────────────────────────────
print("\n📝 [2/10] 네이버 블로그 검색 API")
try:
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    csc = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or cid == "YOUR_NAVER_CLIENT_ID":
        log("네이버 블로그 검색", "SKIP", "NAVER_CLIENT_ID 미설정")
    else:
        url = "https://openapi.naver.com/v1/search/blog.json"
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csc}
        params = {"query": "ChatGPT 사용법", "display": 1}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if "total" in data:
            log("네이버 블로그 검색", "OK", f"블로그 수: {data['total']:,}건")
        else:
            log("네이버 블로그 검색", "FAIL", f"응답: {r.text[:100]}")
except Exception as e:
    log("네이버 블로그 검색", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 3] 네이버 데이터랩 트렌드 API
# ─────────────────────────────────────────
print("\n📈 [3/10] 네이버 데이터랩 트렌드 API")
try:
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    csc = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or cid == "YOUR_NAVER_CLIENT_ID":
        log("네이버 데이터랩 트렌드", "SKIP", "NAVER_CLIENT_ID 미설정")
    else:
        url = "https://openapi.naver.com/v1/datalab/search"
        headers = {
            "X-Naver-Client-Id": cid,
            "X-Naver-Client-Secret": csc,
            "Content-Type": "application/json"
        }
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "week",
            "keywordGroups": [
                {"groupName": "ChatGPT", "keywords": ["ChatGPT", "챗GPT"]},
                {"groupName": "AI바우처", "keywords": ["AI바우처", "AI 바우처"]}
            ]
        }
        r = requests.post(url, headers=headers, json=body, timeout=10)
        data = r.json()
        if "results" in data:
            for res in data["results"]:
                latest = res["data"][-1] if res["data"] else {}
                log("네이버 데이터랩 트렌드", "OK",
                    f"{res['title']}: 최근 비율={latest.get('ratio', 'N/A')}")
        else:
            log("네이버 데이터랩 트렌드", "FAIL", f"응답: {r.text[:200]}")
except Exception as e:
    log("네이버 데이터랩 트렌드", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 4] Google Trends (pytrends)
# ─────────────────────────────────────────
print("\n🌐 [4/10] Google Trends (pytrends)")
try:
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl='ko-KR', tz=540)
    trending = pytrends.trending_searches(pn='south_korea')
    top5 = trending[0].tolist()[:5]
    log("Google Trends (pytrends)", "OK", f"실시간 급상승 TOP5: {', '.join(top5)}")
except ImportError:
    log("Google Trends (pytrends)", "FAIL", "pytrends 미설치: pip install pytrends")
except Exception as e:
    log("Google Trends (pytrends)", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 5] signal.bz 실시간 검색어 크롤링
# ─────────────────────────────────────────
print("\n🔥 [5/10] signal.bz 실시간 검색어")
try:
    from bs4 import BeautifulSoup
    r = requests.get("https://signal.bz/news", timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, 'html.parser')
    # signal.bz의 구조에 따라 셀렉터 조정 필요
    keywords = []
    for tag in soup.select('.rank-text, .list-title, span.rank-name'):
        text = tag.get_text(strip=True)
        if text and len(text) < 30:
            keywords.append(text)
    if keywords:
        log("signal.bz 크롤링", "OK", f"상위 키워드: {', '.join(keywords[:5])}")
    else:
        # 대체 시도
        all_text = soup.get_text()[:200]
        log("signal.bz 크롤링", "WARN", f"셀렉터 조정 필요. 페이지 로드 확인: {len(r.text)}bytes")
except Exception as e:
    log("signal.bz 크롤링", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 6] OpenAI API (뉴스 요약용)
# ─────────────────────────────────────────
print("\n🤖 [6/10] OpenAI API (GPT-4o-mini)")
try:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "YOUR_OPENAI_API_KEY":
        log("OpenAI API", "SKIP", "OPENAI_API_KEY 미설정")
    else:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-5-nano", reasoning_effort="minimal",
            messages=[
                {"role": "system", "content": "당신은 AI 뉴스 요약 전문가입니다."},
                {"role": "user", "content": "다음 제목을 한 줄로 요약하세요: 'OpenAI, GPT-5 출시 임박... 멀티모달 기능 대폭 강화'"}
            ],
            max_completion_tokens=100
        )
        summary = response.choices[0].message.content.strip()
        log("OpenAI API", "OK", f"요약 결과: {summary[:60]}")
except ImportError:
    log("OpenAI API", "FAIL", "openai 미설치: pip install openai")
except Exception as e:
    log("OpenAI API", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 7] 공공데이터포털 - 보조금통합포털 API
# ─────────────────────────────────────────
print("\n💰 [7/10] 보조금통합포털 오픈API")
try:
    api_key = os.environ.get("DATA_GO_KR_KEY", "")
    if not api_key or api_key == "YOUR_DATA_GO_KR_KEY":
        log("보조금통합포털", "SKIP", "DATA_GO_KR_KEY 미설정")
    else:
        # 보조사업현황 API
        url = "https://apis.data.go.kr/B552468/srchFrnrSbsdMng/getSubsiList"
        params = {
            "serviceKey": api_key,
            "pageNo": "1",
            "numOfRows": "5",
            "type": "json"
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            try:
                data = r.json()
                log("보조금통합포털", "OK", f"응답 수신: {len(str(data))}bytes")
            except:
                log("보조금통합포털", "WARN", f"JSON 파싱 실패, 상태코드: {r.status_code}")
        else:
            log("보조금통합포털", "FAIL", f"HTTP {r.status_code}: {r.text[:100]}")
except Exception as e:
    log("보조금통합포털", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 8] 공공데이터포털 - 공공서비스(혜택) API
# ─────────────────────────────────────────
print("\n🏛️ [8/10] 공공서비스(혜택) API")
try:
    api_key = os.environ.get("DATA_GO_KR_KEY", "")
    if not api_key or api_key == "YOUR_DATA_GO_KR_KEY":
        log("공공서비스(혜택)", "SKIP", "DATA_GO_KR_KEY 미설정")
    else:
        url = "https://apis.data.go.kr/1241000/PblcBnefService/pblcBnefInfoList"
        params = {
            "serviceKey": api_key,
            "pageNo": "1",
            "numOfRows": "5",
            "type": "json"
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            log("공공서비스(혜택)", "OK", f"응답 수신: 상태코드 {r.status_code}")
        else:
            log("공공서비스(혜택)", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("공공서비스(혜택)", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 9] NIPA AI 바우처 RSS 크롤링
# ─────────────────────────────────────────
print("\n📋 [9/10] NIPA 공고 크롤링")
try:
    r = requests.get("https://www.nipa.kr/home/2-2",
                     timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        titles = []
        for tag in soup.select('a, .board-title, .tit, td a'):
            text = tag.get_text(strip=True)
            if 'AI' in text or '인공지능' in text or '바우처' in text:
                titles.append(text[:50])
        if titles:
            log("NIPA 공고 크롤링", "OK", f"AI 관련 공고 {len(titles)}건: {titles[0]}")
        else:
            log("NIPA 공고 크롤링", "WARN", f"AI 키워드 공고 없음. 페이지 크기: {len(r.text)}bytes")
    else:
        log("NIPA 공고 크롤링", "FAIL", f"HTTP {r.status_code}")
except Exception as e:
    log("NIPA 공고 크롤링", "FAIL", str(e))

# ─────────────────────────────────────────
# [TEST 10] Pillow 이미지 생성 (카드뉴스)
# ─────────────────────────────────────────
print("\n🖼️ [10/10] Pillow 카드뉴스 이미지 생성")
try:
    from PIL import Image, ImageDraw, ImageFont
    
    # 1080x1080 인스타그램 정사각형 카드
    img = Image.new('RGB', (1080, 1080), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # 기본 폰트 (시스템 폰트 경로)
    font_paths = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",  # Linux
        "C:\\Windows\\Fonts\\malgunbd.ttf",  # Windows
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 48)
                break
            except:
                continue
    if font is None:
        font = ImageFont.load_default()
    
    # 제목 영역
    draw.rectangle([(40, 40), (1040, 200)], fill='#e94560')
    draw.text((60, 80), "aikorea24.kr", fill='white', font=font)
    
    # 본문
    draw.text((60, 260), "오늘의 AI 트렌드", fill='#eee', font=font)
    draw.text((60, 340), "2026-02-12", fill='#aaa', font=font)
    draw.text((60, 460), "1. ChatGPT 업데이트", fill='#0f3460', font=font)
    draw.text((60, 540), "2. AI 바우처 신청 시작", fill='#0f3460', font=font)
    draw.text((60, 620), "3. 구글 Gemini 2.0", fill='#0f3460', font=font)
    
    output_path = "/Users/twinssn/Projects/aikorea24/api_test/test_card.png"
    img.save(output_path)
    log("Pillow 카드뉴스", "OK", f"이미지 생성: {output_path} ({os.path.getsize(output_path):,}bytes)")
except ImportError:
    log("Pillow 카드뉴스", "FAIL", "Pillow 미설치: pip install Pillow")
except Exception as e:
    log("Pillow 카드뉴스", "FAIL", str(e))

# ─── 최종 리포트 ───
print("\n" + "=" * 60)
print("📊 테스트 결과 요약")
print("=" * 60)
ok = sum(1 for r in results if r["status"] == "OK")
fail = sum(1 for r in results if r["status"] == "FAIL")
skip = sum(1 for r in results if r["status"] == "SKIP")
warn = sum(1 for r in results if r["status"] == "WARN")
print(f"  ✅ 성공: {ok}  ❌ 실패: {fail}  ⚠️ 경고: {warn}  ⏭️ 스킵: {skip}")
print()
for r in results:
    emoji = "✅" if r["status"] == "OK" else "❌" if r["status"] == "FAIL" else "⚠️" if r["status"] == "WARN" else "⏭️"
    print(f"  {emoji} {r['api']}: {r['detail'][:70]}")

print()
print("─── 다음 단계 ───")
if skip > 0:
    print("  1. cp env_template.sh .env.sh → 실제 API 키 입력")
    print("  2. source .env.sh")
    print("  3. python3 test_all_apis.py (재실행)")
if fail > 0:
    print("  ※ 실패 항목의 에러 메시지 확인 후 수정 필요")
print()

# JSON 리포트 저장
report_path = "/Users/twinssn/Projects/aikorea24/api_test/test_report.json"
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "summary": {"ok": ok, "fail": fail, "warn": warn, "skip": skip},
        "results": results
    }, f, ensure_ascii=False, indent=2)
print(f"📄 리포트 저장: {report_path}")
