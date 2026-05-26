#!/usr/bin/env python3
"""
aikorea24 블로그 주제 선정기
뉴스 DB → 키워드 추출 → 네이버 검색량 분석 → 황금 주제 선별
"""
import os, sys, json, subprocess, time, hmac, hashlib, base64, re
import concurrent.futures
from datetime import datetime, timedelta
from urllib.parse import quote

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'

def load_env(path):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env(os.path.join(PROJECT_DIR, '.env'))
load_env(os.path.join(PROJECT_DIR, 'api_test', '.env.sh'))

OPENAI_KEY      = os.environ.get('OPENAI_API_KEY', '')
NAVER_ID        = os.environ.get('NAVER_CLIENT_ID', '')
NAVER_SECRET    = os.environ.get('NAVER_CLIENT_SECRET', '')
NAVER_AD_CID    = os.environ.get('NAVER_AD_CUSTOMER_ID', '')
NAVER_AD_KEY    = os.environ.get('NAVER_AD_CLIENT_ID', '')
NAVER_AD_SECRET = os.environ.get('NAVER_AD_CLIENT_SECRET', '')


# ============================================
# 1. 뉴스 DB에서 최근 기사 수집
# ============================================
def fetch_recent_news(days=3):
    print(f"\n[1단계] 뉴스 DB에서 최근 {days}일 기사 수집...")
    try:
        r = subprocess.run(
            ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--yes',
             '--command',
             f"SELECT title, source, category FROM news WHERE created_at >= datetime('now', '-{days} days') ORDER BY created_at DESC;",
             '--json'],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            if isinstance(data, list) and data:
                results = data[0].get('results', [])
                print(f"  수집: {len(results)}건")
                return results
    except Exception as e:
        print(f"  실패: {e}")
    return []


# ============================================
# 2. 씨앗 키워드 → 네이버 연관키워드 확장
# ============================================

# AI 씨앗 키워드 (실제 검색량 있는 기본 키워드)
AI_SEED_KEYWORDS = [
    # AI 도구/서비스
    "ChatGPT", "Claude", "제미나이", "Copilot", "퍼플렉시티",
    "미드저니", "달리", "소라", "런웨이", "스테이블디퓨전",
    # AI 활용
    "AI글쓰기", "AI이미지생성", "AI번역", "AI코딩", "AI영상",
    "AI음악", "AI그림", "AI요약", "AI챗봇", "AI검색",
    # AI 교육/취업
    "AI자격증", "AI강의", "AI부트캠프", "AI스터디", "AI공부",
    # AI 기업/서비스
    "오픈AI", "구글AI", "MS코파일럿", "네이버AI", "카카오AI",
    # 개발 도구
    "커서AI", "윈드서프", "깃헙코파일럿", "볼트AI", "로빈코드",
    # 최신 모델
    "GPT4o", "GPT5", "Claude4", "라마3", "제미나이울트라",
]

def extract_ai_keywords(articles):
    """씨앗 키워드 + 뉴스 제목에서 언급된 고유명사 추출"""
    print(f"\n[2단계] 씨앗 키워드 + 뉴스 기반 키워드 구성...")

    # 뉴스 제목에서 자주 등장하는 AI 관련 고유명사 추출 (GPT 활용)
    news_keywords = []
    if OPENAI_KEY and articles:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)
            titles = [a['title'] for a in articles if a.get('title')]
            headlines_text = "\n".join([f"- {t}" for t in titles[:200]])
            prompt = f"""다음 AI 뉴스 헤드라인에서 **구체적인 제품명, 서비스명, 모델명, 기업명**만 추출하세요.
예시: ChatGPT, Claude, 제미나이, 딥시크, 커서, 윈드서프, 오픈AI, 앤트로픽, 퍼플렉시티

헤드라인:
{headlines_text}

규칙:
- 고유명사(제품명/서비스명/모델명)만 추출
- 일반 명사 제외 (AI기술, AI정책 등 제외)
- 한글 또는 영문 그대로
- 2~15글자
- 쉼표로 구분, 30개 이내

응답:"""
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=500)
            raw = resp.choices[0].message.content
            news_keywords = [kw.strip().replace(" ", "") for kw in raw.split(",")
                           if 2 <= len(kw.strip()) <= 15]
            print(f"  뉴스 고유명사: {len(news_keywords)}개")
        except Exception as e:
            print(f"  GPT 추출 실패: {e}")

    # 씨앗 + 뉴스 고유명사 합치기 (중복 제거)
    all_seeds = list(dict.fromkeys(AI_SEED_KEYWORDS + news_keywords))
    print(f"  총 씨앗 키워드: {len(all_seeds)}개 → 네이버 API 연관검색어 확장")
    return all_seeds


# ============================================
# 3. 네이버 광고 API - 검색량 조회
# ============================================
def generate_signature(timestamp, method, path, secret_key):
    message = f"{timestamp}.{method}.{path}"
    sig = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(sig).decode('utf-8')


def get_search_volume(keywords):
    print(f"\n[3단계] 네이버 검색량 조회 ({len(keywords)}개)...")
    if not all([NAVER_AD_CID, NAVER_AD_KEY, NAVER_AD_SECRET]):
        print("  네이버 광고 API 키 없음 - 검색량 조회 건너뜀")
        return {}

    results = {}
    uri = "/keywordstool"
    base_url = "https://api.naver.com"

    for i in range(0, len(keywords), 5):
        batch = [kw.strip().replace(" ", "") for kw in keywords[i:i+5] if kw.strip()]
        if not batch:
            continue
        timestamp = str(int(time.time() * 1000))
        sig = generate_signature(timestamp, "GET", uri, NAVER_AD_SECRET)
        headers = {
            "X-Timestamp": timestamp, "X-API-KEY": NAVER_AD_KEY,
            "X-Customer": NAVER_AD_CID, "X-Signature": sig,
            "Content-Type": "application/json; charset=UTF-8"
        }
        try:
            import requests
            url = f"{base_url}{uri}?hintKeywords={quote(','.join(batch), safe='')}&showDetail=1"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                for item in resp.json().get("keywordList", []):
                    kw = item.get("relKeyword", "").replace(" ", "")
                    pc = item.get("monthlyPcQcCnt", 0)
                    mo = item.get("monthlyMobileQcCnt", 0)
                    pc = 5 if pc == "< 10" else int(pc or 0)
                    mo = 5 if mo == "< 10" else int(mo or 0)
                    if kw and (pc + mo) > 0:
                        results[kw] = pc + mo
            time.sleep(0.1)
        except Exception as e:
            print(f"  배치 {i//5+1} 에러: {e}")

    # 연관키워드 중 씨앗에 없던 신규 키워드
    input_set = set(kw.strip().replace(" ", "") for kw in keywords)
    discovered = {kw: vol for kw, vol in results.items() if kw not in input_set}
    print(f"  검색량 조회 완료: {len(results)}개 (연관키워드 {len(discovered)}개 추가 발견)")
    return results, discovered


# ============================================
# 4. 블로그 포화도 계산
# ============================================
def get_blog_count(keyword):
    if not all([NAVER_ID, NAVER_SECRET]):
        return 0
    try:
        import requests
        resp = requests.get(
            "https://openapi.naver.com/v1/search/blog.json",
            headers={"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET},
            params={"query": keyword, "display": 1}, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("total", 0)
    except:
        pass
    return 0


def get_blog_counts_batch(keywords):
    print(f"  블로그 포화도 계산 중 ({len(keywords)}개)...")
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        future_map = {ex.submit(get_blog_count, kw): kw for kw in keywords}
        for future in concurrent.futures.as_completed(future_map):
            kw = future_map[future]
            try:
                results[kw] = future.result()
            except:
                results[kw] = 0
    return results


# ============================================
# 5. 관련 뉴스 묶기
# ============================================
def find_related_news(keyword, articles, max_count=5):
    keyword_clean = keyword.lower().replace(" ", "")
    keyword_parts = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', keyword)
    related = []
    for a in articles:
        title = a.get('title', '').lower()
        title_clean = title.replace(" ", "")
        if keyword_clean in title_clean:
            related.append(a)
            continue
        match_count = sum(1 for p in keyword_parts if p.lower() in title)
        if match_count >= 2:
            related.append(a)
    return related[:max_count]


# ============================================
# 6. 황금 주제 선별 + 출력
# ============================================
def select_golden_topics(keywords, search_volumes, blog_counts, articles, top_n=20):
    print(f"\n[5단계] 황금 주제 선별...")
    topics = []
    for kw in keywords:
        vol = search_volumes.get(kw, 0)
        if vol < 500:
            continue
        blog = blog_counts.get(kw, 0)
        if blog == 0:
            continue
        saturation = round(blog / vol, 2)
        if saturation > 2.0:
            continue

        if saturation <= 0.5:
            grade = "🟢 최우선"
        elif saturation <= 1.0:
            grade = "🟢 우선"
        elif saturation <= 1.5:
            grade = "🟡 보통"
        else:
            grade = "🟠 경쟁높음"

        related = find_related_news(kw, articles)
        topics.append({
            "keyword": kw,
            "monthly_search": vol,
            "blog_count": blog,
            "saturation": saturation,
            "grade": grade,
            "related_count": len(related),
            "related_titles": [a['title'] for a in related[:3]],
        })

    topics.sort(key=lambda x: (x['saturation'], -x['monthly_search']))
    return topics[:top_n]


# ============================================
# 메인
# ============================================
def main():
    print("=" * 60)
    print(f"aikorea24 블로그 주제 선정기 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 뉴스 수집
    articles = fetch_recent_news(days=3)
    if not articles:
        print("뉴스 없음. 종료.")
        return

    # 2. 키워드 추출
    keywords = extract_ai_keywords(articles)
    if not keywords:
        print("키워드 없음. 종료.")
        return

    # 3. 검색량 조회 (씨앗 → 연관키워드 확장 포함)
    search_volumes, discovered = get_search_volume(keywords)

    # 연관키워드까지 합쳐서 전체 풀 구성
    all_volumes = {**search_volumes, **discovered}

    # 검색량 500~500000 범위 롱테일 필터 (너무 크면 경쟁 심함, 너무 작으면 유입 없음)
    valid_keywords = [
        kw for kw, vol in all_volumes.items()
        if 500 <= vol <= 500000 and 4 <= len(kw) <= 20
    ]
    valid_keywords = sorted(valid_keywords, key=lambda k: all_volumes[k], reverse=True)[:100]
    print(f"  롱테일 후보 (500~50만): {len(valid_keywords)}개")

    if not valid_keywords:
        valid_keywords = sorted(all_volumes.keys(),
            key=lambda k: all_volumes[k], reverse=True)[:50]
        print(f"  기준 완화 - 상위 {len(valid_keywords)}개")

    # search_volumes에 discovered 병합
    search_volumes = all_volumes

    # 4. 블로그 포화도
    print("\n[4단계] 블로그 포화도 계산...")
    blog_counts = get_blog_counts_batch(valid_keywords[:100])

    # 5. 황금 주제 선별
    topics = select_golden_topics(keywords, search_volumes, blog_counts, articles, top_n=20)

    # 6. 결과 출력
    print("\n" + "=" * 60)
    print(f"블로그 주제 후보 TOP {len(topics)}")
    print("=" * 60)

    for i, t in enumerate(topics, 1):
        print(f"\n{i:02d}. [{t['grade']}] {t['keyword']}")
        print(f"    검색량: {t['monthly_search']:,} | 블로그수: {t['blog_count']:,} | 포화도: {t['saturation']}")
        if t['related_titles']:
            print(f"    관련뉴스:")
            for title in t['related_titles']:
                print(f"      - {title[:60]}")

    # JSON 저장
    out_path = os.path.join(PROJECT_DIR, 'api_test', 'blog_topics.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "topics": topics
        }, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")
    print("=" * 60)


if __name__ == '__main__':
    main()
