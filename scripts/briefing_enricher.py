#!/usr/bin/env python3
"""
S3: 브리핑 코멘트 어긋남 보강기.

selected_items(els 뉴스 6건)를 받아:
  S1(어긋남 후보 생성) → 후보 선별 → S2(가설 생성) → 가설 선별 →
  결정론적 템플릿 조립 → 기존 comment 뒤에 삽입

사용법:
  python scripts/briefing_enricher.py --dry-run              # 오늘 D1에서 읽기
  python scripts/briefing_enricher.py --from-json FILE       # JSON 파일에서 읽기
  python scripts/briefing_enricher.py                        # 실제 D1 업데이트
"""
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional

# ── 경로 설정 ──────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)

from abductive_finder import find_abduction_candidates
from hypothesis_generator import generate_hypotheses
from evidence_checker import check_evidence

def log(msg):
    print(msg)

# ── D1 유틸 ──────────────────────────────────────────────
_WRANGLER = "/opt/homebrew/bin/wrangler"
_DB = "aikorea24-db"


def _d1_run(sql: str) -> Optional[list]:
    """wrangler d1 execute 실행, results 반환."""
    cmd = [_WRANGLER, "d1", "execute", _DB, "--remote", "--command", sql]
    env = dict(os.environ)
    env.pop("CLOUDFLARE_API_TOKEN", None)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                           env=env, cwd=_PROJECT_ROOT)
        if r.returncode != 0:
            log(f"  wrangler 오류 (rc={r.returncode}): {r.stderr[:200]}")
            return None
        m = re.search(r'"results"\s*:\s*(\[.*?\])\s*,\s*"success"',
                      r.stdout, re.DOTALL)
        return json.loads(m.group(1)) if m else []
    except Exception as e:
        log(f"  wrangler 예외: {e}")
        return None


def query_d1(sql: str) -> list[dict]:
    """D1 SELECT 실행."""
    results = _d1_run(sql)
    if results is None:
        raise RuntimeError("D1 query failed")
    return results


def execute_d1(sql: str) -> bool:
    """D1 UPDATE/INSERT 실행."""
    return _d1_run(sql) is not None


def get_today_briefing_items() -> list[dict]:
    """오늘 발행된 브리핑의 briefing_items + news를 D1에서 읽기 전용으로 가져온다."""
    sql = """
        SELECT n.id, n.title, n.description, n.source, n.link, n.pub_date,
               bi.briefing_id, bi.sort_order, bi.comment
        FROM briefing_items bi
        JOIN news n ON bi.news_id = n.id
        JOIN briefings b ON bi.briefing_id = b.id
        WHERE b.date LIKE date('now') || '%'
        ORDER BY bi.sort_order
    """
    return query_d1(sql)


# ── 후보 선별 ──────────────────────────────────────────────
def select_candidates(candidates: list[dict], max_n: int = 2) -> list[dict]:
    """
    후보 선별: type이 서로 다른 것 우선, 등장 순서 유지, 상한 max_n개.
    """
    if not candidates:
        return []
    seen_types: set[str] = set()
    selected: list[dict] = []
    for c in candidates:
        t = c.get("type", "")
        if t in seen_types:
            continue
        seen_types.add(t)
        selected.append(c)
        if len(selected) >= max_n:
            break
    return selected


# ── 가설 선별 ──────────────────────────────────────────────
_CONFIDENCE_ORDER = {"상": 0, "중": 1, "하": 2}


def select_hypotheses(hypotheses: list[dict], max_n: int = 3) -> list[dict]:
    """
    가설 선별: 신뢰도 상 > 중 > 하 순 정렬 후 상위 max_n개.
    상/중이 3개 이상이면 "하"는 제외.
    """
    if not hypotheses:
        return []
    sorted_h = sorted(hypotheses,
                      key=lambda h: _CONFIDENCE_ORDER.get(h.get("confidence", "하"), 2))
    # 상/중이 충분하면 하 제외
    high_med = [h for h in sorted_h if h.get("confidence") in ("상", "중")]
    if len(high_med) >= max_n:
        return high_med[:max_n]
    return sorted_h[:max_n]


# ── 산문 조립 ──────────────────────────────────────────────
def _compose_prose(candidate: dict, hypotheses: list[dict]) -> str:
    """
    결정론적 템플릿으로 산문 조립. 줄바꿈 문자 절대 없음.
    총길이 350자 초과 시 가설을 뒤에서부터 잘라냄.
    """
    gap = candidate.get("gap_summary", "")
    if not gap or not hypotheses:
        return ""

    one_lines = [h.get("one_line", "") for h in hypotheses]
    one_lines = [ol for ol in one_lines if ol]  # 빈 문자열 제거

    if not one_lines:
        return ""

    # 접속사 조정
    count = len(one_lines)
    if count == 1:
        connector = "한 가지로"
    elif count == 2:
        connector = "두 가지로"
    else:
        connector = "몇 가지로"

    # 가설 목록 조립
    ordinals = ["첫째", "둘째", "셋째", "넷째", "다섯째"]
    parts = []
    for i, ol in enumerate(one_lines):
        ordinal = ordinals[i] if i < len(ordinals) else f"{i+1}번째"
        sentence = f"{ordinal}, {ol}"
        # 마침표 정규화
        if not sentence.endswith(("!", ".", "?")):
            sentence += "."
        parts.append(sentence)

    # 문장 조립
    prose = f"{gap} 이 지점은 {connector} 읽을 수 있다. {' '.join(parts)}"

    # 마침표 정규화 (gap_summary 끝)
    if not prose.startswith(("\"", "'")) and not prose[0].isupper():
        pass  # 이미 평서체

    # 총길이 350자 상한 — 가설 뒤에서부터 잘라냄
    if len(prose) > 350:
        # gap + connector + 첫 가설까지만 시도
        for keep in range(len(one_lines), 0, -1):
            trimmed_parts = []
            for i in range(keep):
                ordinal = ordinals[i] if i < len(ordinals) else f"{i+1}번째"
                sentence = f"{ordinal}, {one_lines[i]}"
                if not sentence.endswith(("!", ".", "?")):
                    sentence += "."
                trimmed_parts.append(sentence)
            trimmed = f"{gap} 이 지점은 {connector} 읽을 수 있다. {' '.join(trimmed_parts)}"
            if len(trimmed) <= 350:
                prose = trimmed
                break
        else:
            # 1개도 350자 안에 안 맞으면 gap만 반환
            prose = gap

    # 줄바꿈 문자 제거 (방어적)
    prose = prose.replace("\n", " ").replace("\r", "")
    # 연속 공백 정규화
    prose = re.sub(r' {2,}', ' ', prose).strip()

    return prose


# ── 주입 ──────────────────────────────────────────────
def _inject(items: list[dict], enriched_map: dict[int, str]) -> list[dict]:
    """
    enriched_map: {news_id: 추가_산문} → 해당 item의 comment 뒤에 공백 하나로 연결.
    기존 comment 훼손 금지.
    """
    result = []
    for item in items:
        new_item = dict(item)  # shallow copy
        nid = item.get("id")
        addition = enriched_map.get(nid)
        if addition and item.get("comment"):
            new_item["comment"] = f"{item['comment']} {addition}"
        elif addition:
            new_item["comment"] = addition
        result.append(new_item)
    return result


# ── 메인 ──────────────────────────────────────────────
def enrich_briefing(selected_items: list[dict], dry_run: bool = True) -> list[dict]:
    """
    브리핑 코멘트를 어긋남 분석으로 보강한다.

    Args:
        selected_items: 뉴스 6건 (id, title, body/description, source, ...)
        dry_run: True면 D1 쓰기 없이 결과만 반환

    Returns:
        comment가 보강된 items (원본 불변)
    """
    if not selected_items:
        return selected_items

    log(f"=== 어긋남 보강 시작 (dry_run={dry_run}) ===")

    # S1: 어긋남 후보 생성
    try:
        candidates = find_abduction_candidates(selected_items)
        log(f"  어긋남 후보: {len(candidates)}건")
    except Exception as e:
        log(f"  S1 실패: {e}")
        return selected_items

    if not candidates:
        log("  어uten남 후보 없음, 원본 반환")
        return selected_items

    # 후보 선별 (최대 2개, type 다르게)
    selected_cands = select_candidates(candidates, max_n=2)
    log(f"  선별된 후보: {len(selected_cands)}건 ({[c['type'] for c in selected_cands]})")

    # 각 후보에 대해 S2 + 선별 + 조립
    enriched_map: dict[int, str] = {}  # {news_id: 산문}

    # LLM이 [뉴스 1] 형태의 위치 번호를 source_item_ids로 반환하므로
    # 실제 id로 매핑한다
    id_map = {str(i + 1): item.get("id") for i, item in enumerate(selected_items)}

    for cand in selected_cands:
        source_ids = cand.get("source_item_ids", [])
        # LLM 위치 번호를 실제 item id로 변환
        target_id = id_map.get(source_ids[0]) if source_ids else None

        if target_id is None:
            continue

        # S2: 가설 생성
        try:
            hypotheses = generate_hypotheses(cand, selected_items)
            log(f"    후보 {cand['type']}: 가설 {len(hypotheses)}건")
        except Exception as e:
            log(f"    S2 실패 (후보 {cand['type']}): {e}")
            continue

        if not hypotheses:
            continue

        # 가설 선별 (최대 3개)
        selected_hyps = select_hypotheses(hypotheses, max_n=3)
        log(f"    선별된 가설: {len(selected_hyps)}건 "
            f"({[h.get('confidence') for h in selected_hyps]})")

        # 산문 조립
        prose = _compose_prose(cand, selected_hyps)
        if prose:
            # 산문 근거 검증: gap_summary 부분은 통과 (S1에서 이미 검증됨)
            # 가설 부분은 S2에서 이미 검증됨
            # 다만 전체 산문이 원문을 크게 벗어나는지 최종 방어
            # LLM 위치 번호를 실제 id로 변환하여 소스 텍스트 수집
            mapped_ids = set()
            for sid in source_ids:
                real_id = id_map.get(str(sid))
                if real_id is not None:
                    mapped_ids.add(str(real_id))
            source_combined = ""
            for item in selected_items:
                if str(item.get("id", "")) in mapped_ids:
                    source_combined += " " + (item.get("body") or item.get("summary") or "")
            if source_combined and not check_evidence(prose, source_combined, threshold=0.3, min_matched=3):
                log(f"    ⚠️ 산문 근거 검증 실패, 주입 보류: {prose[:60]}...")
            else:
                enriched_map[target_id] = prose
                log(f"    조립된 산문 ({len(prose)}자): {prose[:80]}...")

    if not enriched_map:
        log("  보강할 산문 없음, 원본 반환")
        return selected_items

    # 주입
    enriched_items = _inject(selected_items, enriched_map)

    # dry_run diff 출력
    if dry_run:
        log("\n=== 보강 전/후 diff ===")
        for orig, new in zip(selected_items, enriched_items):
            if orig.get("comment") != new.get("comment"):
                log(f"  [{orig.get('id')}] {orig.get('title', '')[:40]}")
                log(f"    BEFORE: {orig.get('comment', '(없음)')}")
                log(f"    AFTER:  {new.get('comment', '(없음)')}")

    return enriched_items


# ── CLI ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="브리핑 코멘트 어긋남 보강")
    parser.add_argument("--dry-run", action="store_true",
                        help="D1 쓰기 없이 결과만 출력")
    parser.add_argument("--from-json", type=str, default=None,
                        help="JSON 파일에서 selected_items 로드")
    args = parser.parse_args()

    # 입력 확보
    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            selected_items = json.load(f)
        log(f"JSON에서 {len(selected_items)}건 로드")
    else:
        try:
            selected_items = get_today_briefing_items()
            log(f"D1에서 {len(selected_items)}건 로드")
        except Exception as e:
            log(f"D1 로드 실패: {e}")
            sys.exit(1)

    if not selected_items:
        log("로드된 아이템 없음")
        sys.exit(0)

    # 보강 실행
    enriched = enrich_briefing(selected_items, dry_run=args.dry_run)

    # dry_run이면 결과 출력
    if args.dry_run:
        print(json.dumps(enriched, ensure_ascii=False, indent=2))
    else:
        # D1 업데이트
        update_count = 0
        for item in enriched:
            orig = next((o for o in selected_items if o.get("id") == item.get("id")), None)
            if orig and orig.get("comment") != item.get("comment"):
                comment_escaped = (item.get("comment") or "").replace("'", "''")
                briefing_id = item.get("briefing_id")
                news_id = item.get("id")
                if briefing_id and news_id:
                    sql = (f"UPDATE briefing_items SET comment = '{comment_escaped}' "
                           f"WHERE briefing_id = {briefing_id} AND news_id = {news_id}")
                    if execute_d1(sql):
                        update_count += 1
                        log(f"  D1 업데이트: news_id={news_id}")
        log(f"총 {update_count}건 D1 업데이트 완료")


if __name__ == "__main__":
    main()
