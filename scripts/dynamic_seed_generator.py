#!/usr/bin/env python3
"""
aikorea24 동적 시드 생성기 v1.0
- 현재 seeds.json 앵커 키워드로 네이버 API relKeyword 최대 수집
- keyword_history D1 테이블로 신생 키워드 판별
- 필터링 → OpenAI 선별 → seeds.json 갱신
- 주 1회 실행 권장
"""
import os, re, json, sys, time, hmac, hashlib, base64
from datetime import datetime, date, timezone, timedelta
import urllib.parse

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

KST = timezone(timedelta(hours=9))
from pipeline.infra.env_loader import EnvConfig
_config = EnvConfig()
_config.load_to_environ()
from pipeline.infra import project_root; PROJECT_DIR = project_root()
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
SEEDS_PATH = os.path.join(PROJECT_DIR, "scripts", "seeds.json")
KEYWORDS_PATH = os.path.join(PROJECT_DIR, "scripts", "thread_topics", "keywords.json")
DB_ID = "bec650ce-f732-46bc-87c0-bd76ed17e42a"
NAVER_BASE_URL = "https://api.searchad.naver.com"

# 필터 기준
MIN_VOLUME = 300
MAX_VOLUME = 100000
EXCLUDE_COMPETITION = "높음"
MAX_SEEDS = 30
NAVER_CALL_INTERVAL = 0.4  # 초당 3회 제한 → 0.4초 간격 (여유)


# Strangler Fig: replace with logger.info() in Phase 3
def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


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
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


def query_d1(sql, params=None):
    import requests
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{DB_ID}/query"
    body = {"sql": sql}
    if params:
        body["params"] = params
    r = requests.post(url,
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        json=body
    )
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 query failed: {data.get('errors')}")
    if not data.get("result") or len(data["result"]) == 0:
        return []
    return data["result"][0].get("results", [])


# ============================================
# 네이버 API
# ============================================
def naver_signature(method, path, timestamp, client_secret):
    msg = f"{timestamp}.{method}.{path}"
    sig = hmac.new(client_secret.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


def _parse_volume(val):
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        nums = re.findall(r'\d+', str(val))
        return int(nums[0]) if nums else 0


def fetch_related_keywords(anchor_keyword):
    """
    앵커 키워드 1개 입력 → relKeyword 전체 수집 (최대 100개)
    입력 키워드 자신 포함 검색량/경쟁도 함께 반환
    """
    import requests

    client_id = os.environ.get("NAVER_AD_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_AD_CLIENT_SECRET", "")
    customer_id = os.environ.get("NAVER_AD_CUSTOMER_ID", "")

    ts = str(int(time.time() * 1000))
    path = "/keywordstool"
    signature = naver_signature("GET", path, ts, client_secret)

    # 공백 제거 (API 제한)
    hint = anchor_keyword.replace(" ", "")
    url = f"{NAVER_BASE_URL}{path}?hintKeywords={urllib.parse.quote(hint)}&showDetail=1"

    headers = {
        "X-Timestamp": ts,
        "X-API-KEY": client_id,
        "X-Customer": customer_id,
        "X-Signature": signature,
    }

    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    results = []
    for item in data.get("keywordList", []):
        kw = item.get("relKeyword", "").strip()
        if not kw:
            continue
        pc = _parse_volume(item.get("monthlyPcQcCnt"))
        mobile = _parse_volume(item.get("monthlyMobileQcCnt"))
        volume = pc + mobile
        competition = item.get("compIdx", "낮음")
        results.append({
            "keyword": kw,
            "search_volume": volume,
            "competition": competition,
        })

    return results


# ============================================
# STEP 1: 앵커 키워드로 relKeyword 수집
# ============================================
def collect_all_related(anchor_keywords):
    """
    앵커 키워드 N개 × 최대 100개 relKeyword 수집
    초당 3회 제한 준수
    """
    all_raw = {}  # keyword → {search_volume, competition}

    for i, anchor in enumerate(anchor_keywords):
        log(f"  [{i+1}/{len(anchor_keywords)}] '{anchor}' relKeyword 수집 중...")
        try:
            results = fetch_related_keywords(anchor)
            new_count = 0
            for item in results:
                kw = item["keyword"]
                if kw not in all_raw:
                    all_raw[kw] = item
                    new_count += 1
                else:
                    # 이미 있으면 더 높은 검색량으로 업데이트
                    if item["search_volume"] > all_raw[kw]["search_volume"]:
                        all_raw[kw] = item
            log(f"    → {len(results)}개 수집, 신규 {new_count}개 (누적 {len(all_raw)}개)")
        except Exception as e:
            log(f"    ✗ 실패: {e}")

        if i < len(anchor_keywords) - 1:
            time.sleep(NAVER_CALL_INTERVAL)

    return all_raw


# ============================================
# STEP 2: 검색량/경쟁도 필터링
# ============================================
def filter_keywords(all_raw):
    """
    MIN_VOLUME ~ MAX_VOLUME, 경쟁도 높음 제외
    """
    filtered = {}
    for kw, info in all_raw.items():
        sv = info["search_volume"]
        comp = info["competition"]
        if sv < MIN_VOLUME:
            continue
        if sv > MAX_VOLUME:
            continue
        if comp == EXCLUDE_COMPETITION:
            continue
        filtered[kw] = info

    log(f"  필터링 결과: {len(all_raw)}개 → {len(filtered)}개")
    log(f"  기준: 검색량 {MIN_VOLUME:,}~{MAX_VOLUME:,}, 경쟁도 높음 제외")
    return filtered


# ============================================
# STEP 3: keyword_history 대조 → 신생 판별
# ============================================
def classify_by_history(filtered, today_str):
    """
    D1 keyword_history 조회
    - 없는 키워드 → 신생 (new)
    - 있는 키워드 → 기존 (existing), last_seen/search_volume_latest 업데이트
    반환: new_keywords dict, existing_keywords dict
    """
    if not filtered:
        return {}, {}

    # 현재 history 전체 로드
    try:
        rows = query_d1("SELECT keyword, first_seen, seen_count, search_volume_latest FROM keyword_history")
        history = {r["keyword"]: r for r in rows}
    except Exception as e:
        log(f"  keyword_history 조회 실패: {e}")
        history = {}

    new_keywords = {}
    existing_keywords = {}

    for kw, info in filtered.items():
        if kw not in history:
            new_keywords[kw] = info
        else:
            existing_keywords[kw] = {
                **info,
                "first_seen": history[kw]["first_seen"],
                "seen_count": history[kw]["seen_count"],
            }

    log(f"  신생 키워드: {len(new_keywords)}개")
    log(f"  기존 키워드: {len(existing_keywords)}개")
    return new_keywords, existing_keywords


# ============================================
# STEP 4: keyword_history D1 업데이트
# ============================================
def update_keyword_history(new_keywords, existing_keywords, today_str):
    """
    신생 → INSERT
    기존 → UPDATE (last_seen, seen_count, search_volume_latest)
    """
    import requests

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{DB_ID}/query"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    # 신생 키워드 INSERT
    insert_count = 0
    for kw, info in new_keywords.items():
        sv = info["search_volume"]
        comp = info["competition"]
        grade = "B"
        if sv >= 100000:
            grade = "S"
        elif sv >= 30000:
            grade = "A"

        sql = (
            "INSERT OR IGNORE INTO keyword_history "
            "(keyword, first_seen, last_seen, seen_count, source, "
            "search_volume_first, search_volume_latest, grade) "
            "VALUES (?, ?, ?, 1, 'dynamic', ?, ?, ?)"
        )
        try:
            r = requests.post(url, headers=headers, json={
                "sql": sql,
                "params": [kw, today_str, today_str, sv, sv, grade]
            })
            if r.json().get("success"):
                insert_count += 1
        except Exception as e:
            log(f"    INSERT 실패 ({kw}): {e}")

    # 기존 키워드 UPDATE
    update_count = 0
    for kw, info in existing_keywords.items():
        sv = info["search_volume"]
        sql = (
            "UPDATE keyword_history SET "
            "last_seen=?, seen_count=seen_count+1, search_volume_latest=? "
            "WHERE keyword=?"
        )
        try:
            r = requests.post(url, headers=headers, json={
                "sql": sql,
                "params": [today_str, sv, kw]
            })
            if r.json().get("success"):
                update_count += 1
        except Exception as e:
            log(f"    UPDATE 실패 ({kw}): {e}")

    log(f"  D1 업데이트: INSERT {insert_count}개 / UPDATE {update_count}개")


# ============================================
# STEP 5: OpenAI로 신생 키워드 AI 관련성 판별 + 최종 선별
# ============================================
def select_best_seeds(new_keywords, existing_keywords, current_seeds):
    """
    신생 키워드 우선 + 기존 키워드 보완
    OpenAI로 AI/기술 블로그 적합성 판별
    최대 MAX_SEEDS개 반환
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    current_set = set(current_seeds)

    # 신생 키워드 정렬 (검색량 높은 순)
    new_sorted = sorted(new_keywords.items(), key=lambda x: -x[1]["search_volume"])
    # 기존 키워드 중 현재 seeds에 없는 것 (검색량 높은 순)
    existing_not_in_seeds = {
        k: v for k, v in existing_keywords.items() if k not in current_set
    }
    existing_sorted = sorted(existing_not_in_seeds.items(), key=lambda x: -x[1]["search_volume"])

    # 후보 풀: 신생 우선 50개 + 기존 20개
    candidates = []
    for kw, info in new_sorted[:50]:
        candidates.append({
            "keyword": kw,
            "search_volume": info["search_volume"],
            "competition": info["competition"],
            "is_new": True,
        })
    for kw, info in existing_sorted[:20]:
        candidates.append({
            "keyword": kw,
            "search_volume": info["search_volume"],
            "competition": info["competition"],
            "is_new": False,
        })

    if not candidates:
        log("  선별 후보 없음")
        return current_seeds

    log(f"  OpenAI 선별 대상: {len(candidates)}개")

    candidate_str = json.dumps([
        {
            "keyword": c["keyword"],
            "search_volume": c["search_volume"],
            "competition": c["competition"],
            "is_new": c["is_new"],
        }
        for c in candidates
    ], ensure_ascii=False, indent=2)

    system_prompt = "You are a Korean SEO keyword specialist for AI/technology blog content."

    user_prompt = f"""아래 후보 키워드 중에서 AI/기술 블로그 시드 키워드로 적합한 것을 선별해주세요.

# 선별 기준 (우선순위 순)
1. AI/기술 관련 키워드일 것 (무관한 키워드 제외)
2. is_new=true 키워드 우선 선발
3. 네이버 블로그에서 상위노출 가능성 있는 세부 키워드 우선
   - 너무 광범위한 키워드 제외 (예: "AI", "기술", "인터넷")
   - 구체적인 서비스/기능/방법 키워드 우선 (예: "챗GPT 사용법", "미드저니 프롬프트")
4. 현재 seeds와 중복되지 않을 것

# 현재 seeds (제외 대상)
{json.dumps(current_seeds, ensure_ascii=False)}

# 후보 키워드
{candidate_str}

# 출력 형식 (JSON)
최대 {MAX_SEEDS}개 선별. is_new=true 키워드를 최대한 포함할 것.
{{
  "selected": [
    {{"keyword": "키워드", "reason": "선별 이유 한줄"}}
  ],
  "excluded": ["제외키워드1", "제외키워드2"]
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=3000,
        temperature=0.3,
    )

    content = resp.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        selected = data.get("selected", [])
        excluded = data.get("excluded", [])
        log(f"  선별 완료: {len(selected)}개 선택 / {len(excluded)}개 제외")
        for item in selected:
            is_new_mark = "🆕" if any(c["keyword"] == item["keyword"] and c["is_new"] for c in candidates) else "♻️"
            log(f"    {is_new_mark} {item['keyword']} ({item['reason']})")
        return [item["keyword"] for item in selected]
    except Exception as e:
        log(f"  OpenAI 파싱 실패: {e}")
        return current_seeds


# ============================================
# STEP 6: seeds.json 갱신
# ============================================
def update_seeds(new_seed_list, current_seeds):
    """
    기존 seeds + 신규 선별 키워드 병합 후 저장
    중복 제거, 최대 MAX_SEEDS개
    """
    # 기존 seeds는 유지하되 신규를 앞에 배치
    seen = set()
    merged = []
    for kw in new_seed_list + current_seeds:
        if kw not in seen:
            seen.add(kw)
            merged.append(kw)

    final = merged[:MAX_SEEDS]

    # 백업
    bak_path = SEEDS_PATH + ".bak"
    with open(SEEDS_PATH, "r", encoding="utf-8") as f:
        bak_data = f.read()
    with open(bak_path, "w", encoding="utf-8") as f:
        f.write(bak_data)
    log(f"  seeds.json 백업: {bak_path}")

    with open(SEEDS_PATH, "w", encoding="utf-8") as f:
        json.dump({"seeds": final}, f, ensure_ascii=False, indent=2)
    log(f"  seeds.json 저장 완료: {len(final)}개")
    return final


# ============================================
# STEP 7: 텔레그램 알림
# ============================================
def send_telegram(message):
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
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
    log(f"동적 시드 생성기 시작 ({today_str})")
    print()

    # seeds.json 로드
    with open(SEEDS_PATH, "r", encoding="utf-8") as f:
        seeds_data = json.load(f)
    current_seeds = seeds_data.get("seeds", [])
    log(f"현재 seeds: {len(current_seeds)}개 → {current_seeds}")
    print()

    # ── STEP 1 ──────────────────────────────
    log("=" * 55)
    log("STEP 1/6: 네이버 API relKeyword 수집")
    log(f"  앵커: {len(current_seeds)}개 × 최대 100개 = 최대 {len(current_seeds)*100}개")
    log("=" * 55)
    all_raw = collect_all_related(current_seeds)
    log(f"  총 수집: {len(all_raw)}개 raw 키워드")
    print()

    # ── STEP 2 ──────────────────────────────
    log("=" * 55)
    log("STEP 2/6: 검색량/경쟁도 필터링")
    log("=" * 55)
    filtered = filter_keywords(all_raw)
    print()

    if not filtered:
        log("  필터링 후 후보 없음, 종료")
        return

    # ── STEP 3 ──────────────────────────────
    log("=" * 55)
    log("STEP 3/6: keyword_history 대조 (신생 판별)")
    log("=" * 55)
    new_keywords, existing_keywords = classify_by_history(filtered, today_str)
    print()

    # ── STEP 4 ──────────────────────────────
    log("=" * 55)
    log("STEP 4/6: keyword_history D1 업데이트")
    log("=" * 55)
    update_keyword_history(new_keywords, existing_keywords, today_str)
    print()

    # ── STEP 5 ──────────────────────────────
    log("=" * 55)
    log("STEP 5/6: OpenAI 최종 선별")
    log("=" * 55)
    selected_seeds = select_best_seeds(new_keywords, existing_keywords, current_seeds)
    print()

    # ── STEP 6 ──────────────────────────────
    log("=" * 55)
    log("STEP 6/6: seeds.json 갱신 + 텔레그램 알림")
    log("=" * 55)
    final_seeds = update_seeds(selected_seeds, current_seeds)

    new_added = [kw for kw in final_seeds if kw not in set(current_seeds)]
    msg_lines = [
        f"🌱 [{today_str}] 동적 시드 생성 완료",
        f"",
        f"📊 수집: {len(all_raw)}개 raw → 필터링 {len(filtered)}개",
        f"🆕 신생 키워드: {len(new_keywords)}개",
        f"♻️  기존 키워드: {len(existing_keywords)}개",
        f"",
        f"✅ seeds.json: {len(final_seeds)}개",
    ]
    if new_added:
        msg_lines.append(f"\n새로 추가된 키워드 ({len(new_added)}개):")
        for kw in new_added:
            msg_lines.append(f"  🆕 {kw}")

    send_telegram("\n".join(msg_lines))
    print()
    log("✅ 동적 시드 생성 완료!")


if __name__ == "__main__":
    main()
