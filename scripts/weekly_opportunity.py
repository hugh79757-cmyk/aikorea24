#!/usr/bin/env python3
"""aikorea24 주간 무료 기회 수집 (AIK24-PIPE-03 §작업7)

대표님이 매주 월요일 직접 큐레이션한 scripts/logs/weekly_opportunities.json 을 읽어
news 테이블에 INSERT 한다. 선정기(auto_news_selector)의 슬롯 1 이 이 행(v2_tag='free-opportunity')
을 최신 1건 집어 브리핑에 싣는다.

  - access='unverified' 는 넣지 않는다 (미검증 정보를 실으면 신뢰가 깎인다).
  - expires 가 지난 항목은 넣지 않는다.
  - 접근성 표기를 description 끝에 자동 부착한다 — (a) 바로 선택 / (b) 커스텀 프로바이더 /
    로컬 브리지. (b)를 (a)처럼 표현하지 않는다 (지시서 §11).

사용:
  python3 scripts/weekly_opportunity.py --dry-run   # D1 쓰기 없이 선별 결과만
  python3 scripts/weekly_opportunity.py             # D1 INSERT
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

INPUT_PATH = Path(__file__).resolve().parent / "logs" / "weekly_opportunities.json"
KST = timezone(timedelta(hours=9))
SOURCE = "무료 기회"

# ── AIK24-PIPE-11 (2026-10-22) ────────────────────────────────────────────────
# free-opportunity 큐레이션 항목의 "목록 페이지" 를 실제 모델로 전개한다.
# 배경: news 56082 "OpenRouter 무료 모델 (:free 태그)" 의 link 가
#   https://openrouter.ai/models?max_price=0&order=newest (목록 페이지) 라
#   브리핑 1번 슬롯이 "일반론" 항목이 되어 PIPE-10 사고(허위 실측)로 이어졌다.
#
# 모델 ID 를 담는 기존 필드: news 에 model_id 컬럼이 없다.
#   → 컬럼을 추가한다(추가형 변경 · 기존 컬럼·인덱스 무변경).
#   참고: free-llm 행은 이미 original_title 에 모델 ID 를 담고 있다.
MODEL_ID_COLUMN = "model_id"

# 1회 전개로 저장하는 최대 모델 수 (무료 모델 목록은 수십~수백 개 · 슬롯 소비는 1일 1건)
MAX_EXPAND_MODELS = 20
CATEGORIES = ("provider_credit", "event_promo", "government", "hackathon", "cloud_compute", "student")
REQUIRED = ("title", "description", "link", "category", "access", "expires")
ACCESS_LABEL = {
    "direct": "(a) OpenCode에서 바로 선택 가능",
    "custom": "(b) 커스텀 프로바이더 설정 후 연결 가능",
    "local": "로컬 브리지(Ollama 등) 필요",
}


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [opportunity] {msg}")


# --------------------------------------------------------------------- 펼치기
def _fetch_openrouter_models_all():
    """OpenRouter 모델 목록 원본(무료 필터 전). (모델 dict, 오류 메시지) 반환.

    실패하면 ({}, 사유)를 돌려준다(조용히 넘어가지 않는다).
    """
    try:
        import model_eval
    except Exception as e:  # noqa: BLE001
        return {}, f"model_eval import 실패: {type(e).__name__}: {e}"
    try:
        models = model_eval._fetch_openrouter_models()
    except Exception as e:  # noqa: BLE001
        return {}, f"OpenRouter 모델 목록 조회 실패: {type(e).__name__}: {e}"
    if not models:
        return {}, "OpenRouter 모델 목록 조회 실패(빈 결과)"
    return models, None


def _fetch_openrouter_free_models(max_models: int = MAX_EXPAND_MODELS):
    """OpenRouter 무료 모델 목록 — 최신순. (레코드 리스트, 오류 메시지) 반환.

    실패하면 빈 리스트 + 사유를 돌려준다(조용히 넘어가지 않는다).
    """
    models, err = _fetch_openrouter_models_all()
    if err:
        return [], err

    def is_free(rec):
        mid = str(rec.get("id") or "")
        if mid.endswith(":free"):
            return True
        pricing = rec.get("pricing") or {}
        try:
            return float(pricing.get("prompt", 1)) == 0 and float(pricing.get("completion", 1)) == 0
        except (TypeError, ValueError):
            return False

    rows = [r for r in models.values() if is_free(r)]
    rows.sort(key=lambda r: float(r.get("created") or 0), reverse=True)  # 최신순
    return rows[:max_models], None


def expand_openrouter_free_models(entry, max_models: int = MAX_EXPAND_MODELS):
    """'OpenRouter 무료 모델' 큐레이션 항목 → 모델별 개별 항목 리스트."""
    models, err = _fetch_openrouter_free_models(max_models)
    if err:
        return [], err
    provider = "OpenRouter"
    items = []
    for rec in models:
        mid = str(rec.get("id") or "").strip()
        if not mid:
            continue
        name = str(rec.get("name") or mid).strip()
        desc = str(rec.get("description") or "").strip()
        try:
            created_dt = datetime.fromtimestamp(float(rec.get("created") or 0), KST)
        except (TypeError, ValueError, OSError):
            created_dt = datetime.now(KST)
        items.append({
            # model_catalog.py 의 free-llm 행과 같은 제목 형식 → 생성기 라우팅·정규화 일관
            "title": f"[무료 LLM] {mid} — {provider} 무료 티어",
            "link": f"https://openrouter.ai/{mid}",
            "origin_link": f"https://openrouter.ai/{mid}",
            "model_id": mid,
            "description": (desc or f"{name} — {provider} 무료 티어 모델")[:300],
            "source": SOURCE,
            "category": "benefit",
            "access": entry.get("access", "custom"),
            "expires": entry.get("expires"),
            "pub_date": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "_expanded_from": entry.get("title"),
            # 원본(목록 페이지) link — soft-disable 대상
            "_expanded_from_link": entry.get("link"),
        })
    return items, None


EXPANDERS = {"openrouter_free_models": expand_openrouter_free_models}


def _looks_like_list_page(link) -> bool:
    link = str(link or "").lower()
    if not link:
        return False
    return ("/models" in link or "/model-list" in link) and (
        "?" in link or link.rstrip("/").endswith("/models"))


def expand_entries(entries, max_models: int = MAX_EXPAND_MODELS):
    """큐레이션 항목 → 전개된 항목 리스트. (items, notes) 반환.

    - `expand` 키가 있으면 해당 전개기로 펼친다.
    - `expand` 키가 없는데 link 가 목록 페이지면 **경고만** 남긴다(조용히 일반 처리).
    """
    items, notes = [], []
    for e in entries or []:
        kind = str(e.get("expand") or "").strip()
        if not kind:
            items.append(e)
            if _looks_like_list_page(e.get("link")):
                notes.append(f"⚠️ 목록 페이지 link 인데 expand 키가 없다: {e.get('title')} — "
                             f"전개되지 않으면 일반론 글이 된다")
            continue
        fn = EXPANDERS.get(kind)
        if fn is None:
            notes.append(f"⚠️ 알 수 없는 expand={kind} — 원본 그대로 유지")
            items.append(e)
            continue
        sub, err = fn(e, max_models)
        if err:
            notes.append(f"⚠️ 전개 실패 ({kind}): {err} — 원본 그대로 유지")
            items.append(e)
            continue
        notes.append(f"전개: {e.get('title')} → {len(sub)}건 (모델별)")
        items.extend(sub)
    return items, notes


# --------------------------------------------------------------------- D1 보조
def ensure_model_id_column():
    """news.model_id 컬럼 보장 (없으면 추가). 멱등.

    조회가 실패해도 기존 흐름을 막지 않는다(경고만) — 컬럼이 없으면 INSERT 가 D1 에서
    실패하고 그건 loudly 보고된다.
    """
    try:
        rows = cfnew.sql("SELECT name FROM pragma_table_info('news');", database_id=cfnew.A24_DB) or []
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ news 컬럼 조회 실패: {type(e).__name__}: {e} — 추가 건너뜀")
        return False
    names = {str(r.get("name")) for r in rows if isinstance(r, dict)}
    if MODEL_ID_COLUMN in names:
        return True
    log(f"news.{MODEL_ID_COLUMN} 컬럼 없음 → 추가")
    try:
        cfnew.sql(f"ALTER TABLE news ADD COLUMN {MODEL_ID_COLUMN} TEXT;", database_id=cfnew.A24_DB)
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ 컬럼 추가 실패: {type(e).__name__}: {e}")
        return False
    return True


def existing_model_ids():
    """이미 저장된 모델 ID 집합 — 전개 시 같은 모델 중복 저장 방지."""
    # 주의: model_id 컬럼은 2026-10-22 에 추가됐다. 그 이전에 수집된 free-llm 행은
    #   model_id 가 NULL 이고 original_title 에 모델 ID 가 들어 있다 → 양쪽 모두 본다.
    rows = cfnew.sql(
        "SELECT original_title, model_id FROM news "
        "WHERE model_id IS NOT NULL AND model_id <> '' "
        "   OR source IN ('OpenRouter Free Models','Kilo Free Models',"
        "                'OpenCode Zen','NVIDIA NIM Free');",
        database_id=cfnew.A24_DB) or []
    out = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        for key in ("model_id", "original_title"):
            v = str(r.get(key) or "").strip()
            if v and "/" in v:
                out.add(v)
                out.add(v.replace(":free", ""))
    return out


def retire_superseded(entries, notes):
    """전개로 대체된 목록 페이지 행을 v2_pass=0 으로 soft-disable 한다 (삭제 아님).

    이유: 목록 페이지 행이 이미 브리핑에 실렸으면 `id NOT IN (briefing_items)` 제외로 자동 빠지지만,
    1번 항목이 다른 news 행으로 교체되면(2026-10-22 실제 발생) 다시 후보로 살아난다.
    """
    # soft-disable 대상은 **원본 목록 페이지 행**이다(전개 항목의 link 가 아니라 원본 link).
    targets = [str(e.get("_expanded_from_link") or "").strip() for e in entries
               if e.get("_expanded_from") and str(e.get("_expanded_from_link") or "").strip()]
    done = 0
    for link in targets:
      try:
        rows = cfnew.sql(
            "SELECT id, title, v2_pass FROM news WHERE link = '%s' AND v2_tag = 'free-opportunity';"
            % link.replace("'", "''"), database_id=cfnew.A24_DB) or []
        for r in rows:
            if not isinstance(r, dict) or int(r.get("v2_pass") or 0) == 0:
                continue
            cfnew.sql("UPDATE news SET v2_pass = 0 WHERE id = %s;" % r.get("id"),
                      database_id=cfnew.A24_DB)
            log(f"  ♻️ 목록 페이지 행 soft-disable: id={r.get('id')} '{str(r.get('title'))[:40]}'")
            notes.append(f"soft-disable: news id={r.get('id')}")
            done += 1
      except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ soft-disable 실패 (link={link[:50]}): {type(e).__name__}: {e}")
    return done


def load_entries(path=None):
    p = Path(path or INPUT_PATH)
    if not p.exists():
        log(f"입력 파일 없음: {p} — 이번 주 큐레이션 없음으로 처리")
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"입력은 배열이어야 합니다: {type(data).__name__}")
    return data


def select_entries(entries, today=None):
    """INSERT 대상 선별 (순수 함수 — D1 호출 없음). (선별, 제외사유목록) 반환."""
    today = today or datetime.now(KST).strftime("%Y-%m-%d")
    out, skipped = [], []
    for e in entries or []:
        if not isinstance(e, dict):
            skipped.append(("<non-dict>", f"형식 오류: {type(e).__name__}"))
            continue
        title = (e.get("title") or "").strip() or "<제목 없음>"
        missing = [k for k in REQUIRED if not str(e.get(k) or "").strip()]
        if missing:
            skipped.append((title, "필수 필드 누락: " + ",".join(missing)))
            continue
        if e["category"] not in CATEGORIES:
            skipped.append((title, f"알 수 없는 category={e['category']}"))
            continue
        if e["access"] == "unverified":
            skipped.append((title, "access=unverified (미검증)"))
            continue
        if e["access"] not in ACCESS_LABEL:
            skipped.append((title, f"알 수 없는 access={e['access']}"))
            continue
        if str(e["expires"]) < today:
            skipped.append((title, f"만료 {e['expires']}"))
            continue
        out.append(e)
    return out, skipped


def describe(entry):
    """브리핑에 실릴 description — 접근성 표기 자동 부착."""
    return f"{str(entry['description']).strip()} · {ACCESS_LABEL[entry['access']]}"


def build_inserts(entries, now=None):
    """news INSERT 문 생성 (순수 함수). 컬럼·이스케이프는 news_collector_v2.save() 와 동일."""
    ts = (now or datetime.now(KST)).strftime("%Y-%m-%d %H:%M:%S")

    def lit(v):
        return "'" + str(v or "").replace("'", "''")[:500] + "'"

    stmts = []
    for e in entries:
        # AIK24-PIPE-11: 전개 항목은 pub_date 를 모델 생성시각으로, origin_link 를 모델 페이지로,
        #   model_id 를 구조화해 저장한다. (브리핑 표시 링크 = COALESCE(origin_link, link) → 모델 페이지)
        stmts.append(
            "INSERT OR IGNORE INTO news "
            "(title, link, description, source, category, pub_date, source_url, original_title, country, "
            " v2_pass, v2_tag, origin_link, model_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
            % (
                lit(e["title"][:200]), lit(e["link"]), lit(describe(e)),
                lit(SOURCE), lit("benefit"),
                lit(str(e.get("pub_date") or ts)[:19]),
                lit(e["link"]), lit(e.get("original_title") or e["title"][:200]), lit("kr"),
                1, lit("free-opportunity"),
                lit(e.get("origin_link") or ""), lit(e.get("model_id") or ""),
            )
        )
    return stmts


def existing_titles():
    rows = cfnew.sql("SELECT title FROM news WHERE source = '%s';" % SOURCE,
                     database_id=cfnew.A24_DB) or []
    return {r.get("title") for r in rows if isinstance(r, dict)}


def _link_list(entries):
    """entries → 중복 제거된 SQL IN 리스트 문자열."""
    links = [str(e.get("link") or "").strip() for e in (entries or [])]
    links = [l for l in links if l]
    uniq = list(dict.fromkeys(links))
    return ",".join("'" + l.replace("'", "''") + "'" for l in uniq)


def link_conflicts(entries):
    """INSERT 전 링크 충돌 사전 점검.

    news.link 는 UNIQUE 라, 다른 source 가 같은 링크를 이미 점유하고 있으면
    `INSERT OR IGNORE` 가 그 행을 **소리 없이** 버린다 (2026-10-16 실측: id=56069 가
    'https://openrouter.ai/models?max_price=0' 을 점유해 8건 중 1건이 로그상
    '8건 전송'인데 실제로는 7건만 남았다). 점유 행을 미리 찾아 명시적으로 건너뛴다.

    반환: {link: {'id':..,'title':..,'source':..}} — 충돌 없으면 빈 dict.
    """
    in_list = _link_list(entries)
    if not in_list:
        return {}
    rows = cfnew.sql("SELECT id, title, source, link FROM news WHERE link IN (%s);" % in_list,
                     database_id=cfnew.A24_DB) or []
    return {str(r.get("link")): r for r in rows if isinstance(r, dict)}


def landed_count(entries):
    """INSERT 후 실제 반영 수 — 전송 수와 다르면 조용히 넘기지 않는다 (fail-silent 금지)."""
    in_list = _link_list(entries)
    if not in_list:
        return 0
    rows = cfnew.sql("SELECT COUNT(*) AS c FROM news WHERE link IN (%s);" % in_list,
                     database_id=cfnew.A24_DB) or []
    return int((rows[0] or {}).get("c") or 0) if isinstance(rows[0], dict) else 0


def main():
    ap = argparse.ArgumentParser(description="주간 무료 기회 → news INSERT (v2_tag=free-opportunity)")
    ap.add_argument("--dry-run", action="store_true", help="D1 쓰기 없이 선별 결과만 출력")
    ap.add_argument("--path", default=str(INPUT_PATH), help="입력 JSON 경로")
    ap.add_argument("--max-models", type=int, default=MAX_EXPAND_MODELS,
                    help="전개 최대 모델 수 (기본 20)")
    args = ap.parse_args()

    try:
        entries = load_entries(Path(args.path))
    except Exception as e:  # noqa: BLE001
        log(f"입력 로드 실패: {type(e).__name__}: {e}")
        return 1

    selected, skipped = select_entries(entries)
    for title, why in skipped:
        log(f"  제외: {title} — {why}")
    log(f"선별 {len(selected)}건 / 입력 {len(entries)}건")

    # AIK24-PIPE-11: 목록 페이지 항목을 실제 모델로 전개
    expanded, notes = expand_entries(selected, max_models=args.max_models)
    for n in notes:
        log(f"  {n}")
    log(f"전개 후 {len(expanded)}건 (전개 전 {len(selected)}건)")

    if args.dry_run:
        for e in expanded:
            mid = e.get("model_id")
            log(f"  [INSERT 예정] {e['title'][:70]} ({e['category']}/{e['access']})"
                + (f" · model_id={mid} · link={e['link']}" if mid else "")
                + (f" — {describe(e)}" if not mid else ""))
        return 0
    if not expanded:
        return 0

    try:
        cfnew.check_quota()  # 지시서 §작업7 — 쓰기 전 가드
        ensure_model_id_column()
        known = existing_titles()
        todo = [e for e in expanded if e["title"] not in known]
        if len(todo) != len(expanded):
            log(f"이미 등록됨 {len(expanded) - len(todo)}건 스킵")

        # AIK24-PIPE-11: 같은 모델이 이미 저장돼 있으면 전개 항목 제외(중복 저장 방지)
        try:
            seen_models = existing_model_ids()
        except Exception as e:  # noqa: BLE001
            log(f"  ⚠️ 기존 모델 ID 조회 실패: {e}")
            seen_models = set()
        if seen_models:
            kept = []
            for e in todo:
                mid = str(e.get("model_id") or "").strip()
                if mid and (mid in seen_models or mid.replace(":free", "") in seen_models):
                    log(f"  ⏭ 모델 중복: {mid} — 이미 news 행 있음, 전개 항목 제외")
                    continue
                kept.append(e)
            if len(kept) != len(todo):
                log(f"모델 중복 제외 {len(todo) - len(kept)}건")
            todo = kept

        # 링크 충돌 사전 점검 (2026-10-16: link UNIQUE 점유로 1건이 소리 없이 사라졌다)
        conflicts = link_conflicts(todo)
        if conflicts:
            kept = []
            for e in todo:
                held = conflicts.get(str(e.get("link") or "").strip())
                if held:
                    log(f"  ⚠️ 링크 충돌: '{e['title']}' → 기존 id={held.get('id')} "
                        f"(source={held.get('source')}, '{str(held.get('title'))[:40]}') — 건너뜀")
                    continue
                kept.append(e)
            todo = kept

        if not todo:
            log("신규 없음")
            retire_superseded(expanded, notes)
            return 0
        res = cfnew.sql(";\n".join(build_inserts(todo)), database_id=cfnew.A24_DB)
        log(f"INSERT {len(todo)}건 전송 (ok={isinstance(res, list)})")

        # 사후 검증 — 전송 수 ≠ 실제 반영 수면 성공으로 보고하지 않는다
        landed = landed_count(todo)
        if landed != len(todo):
            missing = ", ".join(f"'{e['title']}'" for e in todo)
            log(f"⚠️ 등록 건수 불일치: 전송 {len(todo)} / 확인 {landed} — 확인 대상: {missing}")
            return 1
        log(f"확인: {landed}건 반영됨")

        # AIK24-PIPE-11: 전개로 대체된 목록 페이지 행은 soft-disable (v2_pass=0)
        retire_superseded(expanded, notes)
    except Exception as e:  # noqa: BLE001 — 실패를 조용히 넘기지 않는다
        log(f"D1 쓰기 실패: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
