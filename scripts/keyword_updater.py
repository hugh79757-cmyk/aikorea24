#!/usr/bin/env python3
"""
aikorea24 키워드 자동 갱신기 v1.0
- scripts/seeds.json + 오늘 뉴스 키워드 추출
- 네이버 검색광고 API 검색량 조회
- grade/intent/db_query 자동 생성
- scripts/keywords.json 갱신 + 텔레그램 알림
"""
import os, re, json, sys, time, hmac, hashlib, base64
from datetime import datetime, date, timezone, timedelta
import urllib.parse

KST = timezone(timedelta(hours=9))
PROJECT_DIR = "/Users/twinssn/Projects/aikorea24"
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
SEEDS_PATH = os.path.join(PROJECT_DIR, "scripts", "seeds.json")
KEYWORDS_PATH = os.path.join(PROJECT_DIR, "scripts", "keywords.json")
DB_ID = "bec650ce-f732-46bc-87c0-bd76ed17e42a"
NAVER_BASE_URL = "https://api.searchad.naver.com"


# ============================================
# 로깅
# ============================================
def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ============================================
# 환경변수 로딩
# ============================================
def load_env():
    # 공통 환경변수 먼저 로드 (~/.env.common)
    common = os.path.expanduser('~/.env.common')
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') \
                   and '=' in line and not line.startswith('source'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(),
                                         v.strip().strip('"').strip("'"))

    if not os.path.exists(ENV_PATH):
        log(f"[WARN] .env 파일 없음: {ENV_PATH}")
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


# ============================================
# D1 쿼리 (REST API)
# ============================================
def query_d1(sql):
    import requests
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not account_id or not api_token:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID 또는 CLOUDFLARE_API_TOKEN 없음")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{DB_ID}/query"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        json={"sql": sql}
    )
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 query failed: {data.get('errors')}")
    if not data.get("result") or len(data["result"]) == 0:
        return []
    return data["result"][0]["results"]


# ============================================
# STEP 1: D1에서 오늘 뉴스 로드
# ============================================
def load_today_news():
    """오늘 날짜 기사 조회, 없으면 어제로 fallback"""
    today = date.today()
    yesterday = today - timedelta(days=1)

    for target_date in [today, yesterday]:
        date_str = target_date.strftime("%Y-%m-%d")
        sql = f"""
            SELECT title, description
            FROM news
            WHERE DATE(created_at) = '{date_str}'
              AND category IN ('global', 'news')
              AND title IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 100
        """
        try:
            rows = query_d1(sql)
        except Exception as e:
            log(f"  D1 쿼리 실패: {e}")
            continue

        if rows:
            log(f"D1 조회: {date_str} ({len(rows)}건)")
            return rows, date_str

    log("  오늘/어제 기사 없음")
    return [], ""


# ============================================
# STEP 2: OpenAI로 신규 키워드 추출
# ============================================
def extract_keywords_from_news(articles):
    """오늘 뉴스에서 AI/기술 고유명사 키워드 추출"""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # 기사 텍스트 조립 (토큰 제한 고려)
    article_texts = []
    for a in articles:
        title = (a.get("title") or "")[:200]
        desc = (a.get("description") or "")[:300]
        article_texts.append(f"제목: {title}\n내용: {desc}")

    articles_str = "\n\n".join(article_texts)
    if len(articles_str) > 15000:
        articles_str = articles_str[:15000] + "\n...(truncated)"

    system_prompt = "You are a keyword extraction specialist. Extract AI/tech proper noun keywords from the following news articles."

    user_prompt = f"""오늘의 AI/기술 뉴스에서 신규 고유명사 키워드를 추출해주세요.

# 조건
- AI/기술 관련 키워드만 추출
- 오늘 뉴스에서 처음 등장한 고유명사 우선 (제품명, 서비스명, 기술명, 기업명)
- "AI 이미지 생성", "챗GPT 사용법" 같은 범용 키워드는 제외
- 한국 네이버에서 검색할 만한 형태로 출력
- 10~20개 추출

# 뉴스
{articles_str}

# 출력 형식 (JSON)
{{"keywords": ["키워드1", "키워드2", ...]}}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=2000,
        temperature=0.3,
    )

    content = resp.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        keywords = data.get("keywords", [])
        log(f"OpenAI 키워드 추출: {len(keywords)}개")
        return keywords
    except json.JSONDecodeError:
        log(f"  OpenAI 응답 파싱 실패: {content[:200]}")
        return []


# ============================================
# STEP 3: seeds + 신규 키워드 병합
# ============================================
def merge_keywords(seed_keywords, new_keywords):
    """중복 제거 병합"""
    seen = set()
    merged = []
    for kw in seed_keywords + new_keywords:
        kw_stripped = kw.strip()
        if kw_stripped and kw_stripped not in seen:
            seen.add(kw_stripped)
            merged.append(kw_stripped)
    return merged


# ============================================
# STEP 4: 네이버 검색광고 API 조회
# ============================================
def naver_signature(method, path, timestamp, client_secret):
    msg = f"{timestamp}.{method}.{path}"
    sig = hmac.new(client_secret.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


def _parse_volume(val):
    """네이버 API 검색량 값 정수 변환 ('< 10' 같은 문자열 처리)"""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        # '< 10' 같은 문자열 → 숫자만 추출
        nums = re.findall(r'\d+', str(val))
        return int(nums[0]) if nums else 0


def fetch_naver_keyword_data(keywords_batch):
    """네이버 검색광고 API로 키워드 검색량+경쟁도 조회 (배치 단위)"""
    import requests

    client_id = os.environ.get("NAVER_AD_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_AD_CLIENT_SECRET", "")
    customer_id = os.environ.get("NAVER_AD_CUSTOMER_ID", "")

    if not client_id or not client_secret or not customer_id:
        raise RuntimeError("NAVER_AD_* 환경변수 누락")

    ts = str(int(time.time() * 1000))
    path = "/keywordstool"
    method = "GET"
    signature = naver_signature(method, path, ts, client_secret)

    hint = ",".join(keywords_batch)
    url = f"{NAVER_BASE_URL}{path}?hintKeywords={urllib.parse.quote(hint)}&showDetail=1"

    headers = {
        "X-Timestamp": ts,
        "X-API-KEY": client_id,
        "X-Customer": customer_id,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }

    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    results = {}

    for item in data.get("keywordList", []):
        kw = item.get("relKeyword", "")
        pc_cnt = _parse_volume(item.get("monthlyPcQcCnt"))
        mobile_cnt = _parse_volume(item.get("monthlyMobileQcCnt"))
        search_volume = pc_cnt + mobile_cnt
        competition = item.get("compIdx", "낮음")

        if kw in keywords_batch:
            results[kw] = {
                "search_volume": search_volume,
                "competition": competition,
            }

    return results


def lookup_naver_keywords(all_keywords):
    """전체 키워드 네이버 API 조회 (5개씩 배치, 실패 시 개별 재시도)"""
    naver_data = {}

    for i in range(0, len(all_keywords), 5):
        batch = all_keywords[i:i+5]
        log(f"  네이버 API 조회: {i+1}~{min(i+5, len(all_keywords))}/{len(all_keywords)}: {', '.join(batch)}")

        try:
            results = fetch_naver_keyword_data(batch)
            naver_data.update(results)
            for kw in batch:
                if kw in results:
                    sv = results[kw]["search_volume"]
                    comp = results[kw]["competition"]
                    log(f"    ✓ {kw}: 검색량={sv}, 경쟁도={comp}")
                else:
                    log(f"    △ {kw}: API에 없음 (검색량=0)")
        except Exception as e:
            log(f"    ✗ 배치(5개) 실패: {e}")
            # 400 에러 등 배치 실패 시 개별 재시도
            for kw in batch:
                try:
                    time.sleep(0.3)
                    single_result = fetch_naver_keyword_data([kw])
                    if kw in single_result:
                        naver_data[kw] = single_result[kw]
                        sv = single_result[kw]["search_volume"]
                        comp = single_result[kw]["competition"]
                        log(f"    ✓ {kw}: 검색량={sv}, 경쟁도={comp} (개별 재시도 성공)")
                    else:
                        log(f"    △ {kw}: API에 없음 (검색량=0)")
                except Exception as e2:
                    log(f"    ✗ {kw}: 개별 재시도 실패: {e2}")

        if i + 5 < len(all_keywords):
            time.sleep(0.3)

    return naver_data


# ============================================
# STEP 5: grade 계산
# ============================================
def calculate_grade(keyword, search_volume, competition, is_new):
    """
    S: search_volume >= 100000
    A: search_volume >= 30000 OR competition == "높음"
    B: 나머지
    신규 키워드는 search_volume=0이어도 grade=B 유지
    """
    if search_volume >= 100000:
        return "S"
    if search_volume >= 30000 or competition == "높음":
        return "A"
    if is_new and search_volume == 0:
        return "B"
    return "B"


# ============================================
# STEP 6+7: OpenAI로 intent + db_query 배치 생성
# ============================================
def generate_intent_and_db_query(all_keywords, new_keywords):
    """OpenAI로 키워드별 검색의도 + db_query 배치 생성"""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    new_set = set(new_keywords)
    examples = []
    for kw in all_keywords:
        is_new = "예" if kw in new_set else "아니오"
        examples.append(f"{kw} (신규: {is_new})")

    system_prompt = "You generate Korean search intent and LIKE query lists for keyword optimization."

    user_prompt = f"""아래 키워드 각각에 대해:

1) intent: 한국 네이버 검색의도 (20자 이내 짧게)
2) db_query: SQL LIKE 검색용 쿼리 리스트 (영문/한글 혼용 고려, 2~5개)

# db_query 규칙
- 영문/한글 혼용 키워드는 둘 다 포함
- 예: "챗GPT" → ["챗GPT", "ChatGPT", "OpenAI"]
- 예: "클로드" → ["클로드", "Claude", "Anthropic"]
- 예: "AI이미지" → ["AI이미지", "AI 이미지", "이미지 생성"]
- 연관 기업/제품명을 추가

# 출력 형식 (JSON)
{{
  "키워드1": {{"intent": "검색의도1", "db_query": ["a", "b", "c"]}},
  "키워드2": {{"intent": "검색의도2", "db_query": ["x", "y"]}},
  ...
}}

# 키워드 리스트
{json.dumps(examples, ensure_ascii=False, indent=2)}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=4000,
        temperature=0.3,
    )

    content = resp.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        log(f"OpenAI intent/db_query 생성: {len(data)}개 키워드")
        return data
    except json.JSONDecodeError:
        log(f"  OpenAI 응답 파싱 실패, fallback 처리")
        return {}


# ============================================
# keywords.json 백업
# ============================================
def backup_keywords():
    if os.path.exists(KEYWORDS_PATH):
        bak_path = KEYWORDS_PATH + ".bak"
        with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
            data = f.read()
        with open(bak_path, "w", encoding="utf-8") as f:
            f.write(data)
        log(f"백업 완료: {bak_path}")


# ============================================
# 텔레그램 알림
# ============================================
def send_telegram(message):
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log("  텔레그램 토큰/챗ID 없음, 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        log("  텔레그램 알림 전송 완료")
    except Exception as e:
        log(f"  텔레그램 전송 실패: {e}")


# ============================================
# 메인
# ============================================
def main():
    load_env()
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] 키워드 갱신 시작 ({today_str})")
    print()

    # ── STEP 1 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 1/9: seeds.json 로드")
    log("=" * 55)
    with open(SEEDS_PATH, "r", encoding="utf-8") as f:
        seeds_data = json.load(f)
    seed_keywords = seeds_data.get("seeds", [])
    log(f"  베이스 키워드: {len(seed_keywords)}개")
    print()

    # ── STEP 2 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 2/9: D1 뉴스 조회")
    log("=" * 55)
    articles, news_date = load_today_news()
    if not articles:
        log("  → 조회 가능한 뉴스 없음, seeds만으로 진행")
        new_keywords = []
    else:
        print()
        # ── STEP 3 ──────────────────────────────────────
        log("=" * 55)
        log("STEP 3/9: OpenAI 신규 키워드 추출")
        log("=" * 55)
        new_keywords = extract_keywords_from_news(articles)
        log(f"  추출된 신규 키워드: {new_keywords}")
    print()

    # ── STEP 4 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 4/9: 키워드 병합 (중복 제거)")
    log("=" * 55)
    all_keywords = merge_keywords(seed_keywords, new_keywords)
    log(f"  병합 완료: {len(all_keywords)}개 (seed {len(seed_keywords)}개 + 신규 {len(new_keywords)}개)")
    print()

    # ── STEP 5 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 5/9: 네이버 검색광고 API 조회")
    log("=" * 55)
    naver_data = lookup_naver_keywords(all_keywords)
    print()

    # ── STEP 6 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 6/9: grade 계산")
    log("=" * 55)
    new_set = set(new_keywords)
    keyword_info = {}

    for kw in all_keywords:
        source = "news" if kw in new_set else "seed"
        is_new = (source == "news")

        if kw in naver_data:
            sv = naver_data[kw]["search_volume"]
            comp = naver_data[kw]["competition"]
        else:
            sv = 0
            comp = "낮음"

        grade = calculate_grade(kw, sv, comp, is_new)
        keyword_info[kw] = {
            "search_volume": sv,
            "competition": comp,
            "grade": grade,
            "source": source,
        }
        log(f"  [{grade}] {kw}: 검색량={sv:,}, 경쟁도={comp}, 출처={source}")
    print()

    # ── STEP 7 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 7/9: OpenAI intent + db_query 생성")
    log("=" * 55)
    intent_data = generate_intent_and_db_query(all_keywords, new_keywords)
    print()

    # ── STEP 8 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 8/9: keywords.json 저장")
    log("=" * 55)
    output = {}
    for kw in all_keywords:
        info = keyword_info[kw]
        idata = intent_data.get(kw, {})

        output[kw] = {
            "search_volume": info["search_volume"],
            "competition": info["competition"],
            "grade": info["grade"],
            "db_query": idata.get("db_query", [kw]),
            "intent": idata.get("intent", ""),
            "source": info["source"],
        }

    backup_keywords()
    with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"keywords.json 저장 완료: {len(output)}개 키워드")
    print()

    # ── STEP 9 ──────────────────────────────────────────
    log("=" * 55)
    log("STEP 9/9: 텔레그램 알림")
    log("=" * 55)
    new_items = [(kw, info) for kw, info in output.items() if info["source"] == "news"]
    seed_items = [(kw, info) for kw, info in output.items() if info["source"] == "seed"]

    grade_order = {"S": 0, "A": 1, "B": 2}
    seed_items.sort(key=lambda x: (grade_order.get(x[1]["grade"], 99), -x[1]["search_volume"]))
    new_items.sort(key=lambda x: (grade_order.get(x[1]["grade"], 99), -x[1]["search_volume"]))

    msg_lines = [f"🔄 [{today_str}] keywords.json 갱신 완료 ({len(output)}개)"]

    if new_items:
        msg_lines.append(f"\n🆕 오늘 뉴스 기반 신규 ({len(new_items)}개):")
        for kw, info in new_items:
            msg_lines.append(f"  [{info['grade']}] {kw} (검색량: {info['search_volume']:,})")

    msg_lines.append(f"\n📌 베이스 키워드 ({len(seed_items)}개):")
    for kw, info in seed_items:
        msg_lines.append(f"  [{info['grade']}] {kw} (검색량: {info['search_volume']:,})")

    send_telegram("\n".join(msg_lines))
    print()

    log("✅ 키워드 갱신 완료!")


if __name__ == "__main__":
    main()
