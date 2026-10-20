#!/usr/bin/env python3
"""AIK24-PIPE-07 — 무료 모델 브리핑 "원문 보기" → 제공사 모델 페이지 (2026-10-20)

배경
----
PIPE-05 는 무료 모델 항목의 "원문 보기"를 AIK24 블로그 글(blog_link)로 보냈다.
그 결과 브리핑 카드에서 **"원문 보기"와 "이 뉴스, 더 깊이 읽기"가 같은 블로그로
가는** 문제가 생겼다(2026-10-20 대표님 지적). 원문 보기는 그 모델이 브리핑에
오른 출처(제공사)의 모델 페이지로 보내야 한다.

  OpenCode Zen        → https://opencode.ai/v2/docs/console/models/
  OpenRouter          → https://openrouter.ai/{org}/{model}
  Kilo                → https://kilo.ai/models/{slug}
  NVIDIA NIM          → https://build.nvidia.com/{org}/{model}

원칙
----
1) news.link 는 수집기 dedup 키다 (`news_collector_v2.save()` 가 최근 3,000개
   link 로 중복 제외). **절대 변경하지 않는다.**
2) 제공사 페이지는 news.origin_link 에 따로 담는다 (additive).
3) 렌더링은 COALESCE(n.origin_link, n.link) — origin_link 가 없으면 기존 link.
   비무료 뉴스는 origin_link 가 NULL 이므로 link(실제 원문)가 그대로 쓰인다.
4) blog_link 는 DB 에 남지만 "원문 보기"에는 더 이상 쓰지 않는다. 심층 분석
   링크는 briefing_items.deep_dive_url 이 담당한다.

사용
----
    python3 scripts/origin_link_resolver.py --report          # 현황만 (쓰기 없음)
    python3 scripts/origin_link_resolver.py --apply           # 컬럼 보장 + 백필
    python3 scripts/origin_link_resolver.py --apply --dry-run # 대상만 출력
    python3 scripts/origin_link_resolver.py --apply --verify  # Kilo 404 → 목록 페이지

D1 접근은 cfnew.py(REST) 를 쓴다 — launchd 환경·셸 양쪽에서 동일하게 동작한다.
"""
import argparse
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cfnew  # noqa: E402

KST = timezone(timedelta(hours=9))
BATCH = 40  # D1 쓰기 배치 — blog_link_resolver 와 동일 상한

# news.source → 제공사 키 (무료 모델 4종)
SOURCE_PROVIDER = {
    "OpenCode Zen": "zen",
    "OpenRouter Free Models": "openrouter",
    "Kilo Free Models": "kilo",
    "NVIDIA NIM Free": "nvidia",
}

# 제공사별 모델 목록/모델 페이지. per-model 페이지가 없는 제공사는 목록 페이지를 쓴다.
PROVIDER_LIST_PAGE = {
    # OpenCode Zen 은 모델별 페이지가 없다(/zen 은 제품 소개, 모델 표는 docs).
    "zen": "https://opencode.ai/v2/docs/console/models/",
    "openrouter": "https://openrouter.ai/models?max_price=0",
    "kilo": "https://kilo.ai/models",
    "nvidia": "https://build.nvidia.com/models",
}

FREE_SUFFIXES = (":free", "-free")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) aikorea24-origin-link/1.0"


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [origin-link] {msg}")


# ============================================
# 순수 함수 — 네트워크·DB 없음 (테스트 대상)
# ============================================
def provider_for_source(source):
    """news.source → 제공사 키. 무료 모델 4종이 아니면 None."""
    return SOURCE_PROVIDER.get((source or "").strip())


def strip_free_suffix(model_id):
    """`:free` / `-free` 접미사 제거 (models.dev·OpenRouter 표기 차이 흡수)."""
    s = (model_id or "").strip()
    for suffix in FREE_SUFFIXES:
        if s.lower().endswith(suffix):
            return s[: -len(suffix)]
    return s


def slugify_model(model_id):
    """Kilo 모델 URL 슬러그.

        minimax/minimax-m3.1-flash:free → minimax-minimax-m3-1-flash-free
    """
    return re.sub(r"[^a-z0-9]+", "-", (model_id or "").strip().lower()).strip("-")


def resolve_origin_link(source, model_id):
    """무료 모델 행의 "원문 보기" 목적지. 무료 모델 4종이 아니면 None.

    model_id 가 비면 제공사 목록 페이지로 폴백한다(브리핑에는 모델 id 가 항상
    있지만, 수동 백필·방어 목적).
    """
    provider = provider_for_source(source)
    if not provider:
        return None

    mid = (model_id or "").strip()
    list_page = PROVIDER_LIST_PAGE[provider]

    if provider == "zen":
        # 모델별 페이지 없음 — 모델 표가 있는 공식 문서로.
        return list_page

    if provider == "openrouter":
        core = strip_free_suffix(mid)
        # org/model 형태만 per-model 페이지가 성립한다. "free" 같은 단일 토큰은 목록으로.
        if "/" in core and not core.endswith("/"):
            return f"https://openrouter.ai/{core}"
        return list_page

    if provider == "kilo":
        slug = slugify_model(mid)
        return f"https://kilo.ai/models/{slug}" if slug else list_page

    if provider == "nvidia":
        core = strip_free_suffix(mid)
        if "/" in core and not core.endswith("/"):
            return f"https://build.nvidia.com/{core}"
        return list_page

    return list_page


def row_origin_link(row):
    """news 행(dict) → origin_link. link 는 dedup 키라 읽기만 한다."""
    return resolve_origin_link(row.get("source"), row.get("original_title"))


# ============================================
# HTTP 확인 (Kilo per-model 404 방어)
# ============================================
def http_ok(url, timeout=15):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except urllib.error.HTTPError as e:
        # HEAD 미지원(405)이면 GET 으로 한 번 더 확인
        if e.code not in (403, 405):
            return False
    except Exception:  # noqa: BLE001 — 네트워크 실패는 목록 페이지 폴백
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:  # noqa: BLE001
        return False


def downgrade_if_dead(url, source):
    """per-model 페이지가 404 면 제공사 목록 페이지로 내린다."""
    if provider_for_source(source) != "kilo":
        return url
    if not url or url == PROVIDER_LIST_PAGE["kilo"]:
        return url
    return url if http_ok(url) else PROVIDER_LIST_PAGE["kilo"]


# ============================================
# D1
# ============================================
def ensure_column(dry_run=False):
    """news.origin_link 컬럼 보장. 이미 있으면 False."""
    rows = cfnew.sql("PRAGMA table_info(news);", database_id=cfnew.A24_DB)
    if isinstance(rows, dict):
        raise RuntimeError(f"PRAGMA 실패: {rows}")
    names = {r.get("name") for r in (rows or []) if isinstance(r, dict)}
    if "origin_link" in names:
        return False
    if dry_run:
        log("[dry-run] ALTER TABLE news ADD COLUMN origin_link TEXT; (미실행)")
        return True
    cfnew.sql("ALTER TABLE news ADD COLUMN origin_link TEXT;", database_id=cfnew.A24_DB)
    log("컬럼 추가: news.origin_link")
    return True


def has_column():
    rows = cfnew.sql("PRAGMA table_info(news);", database_id=cfnew.A24_DB)
    if isinstance(rows, dict):
        raise RuntimeError(f"PRAGMA 실패: {rows}")
    return "origin_link" in {r.get("name") for r in (rows or []) if isinstance(r, dict)}


def fetch_rows(with_origin=True):
    sources = ", ".join("'" + s.replace("'", "''") + "'" for s in SOURCE_PROVIDER)
    cols = "id, source, original_title, link, blog_link"
    if with_origin:
        cols += ", origin_link"
    sql = f"SELECT {cols} FROM news WHERE source IN ({sources}) ORDER BY id;"
    rows = cfnew.sql(sql, database_id=cfnew.A24_DB)
    if isinstance(rows, dict):
        raise RuntimeError(f"조회 실패: {rows}")
    return rows or []


def set_origin_links(pairs):
    """[(news_id, url)] 일괄 UPDATE. 성공 건수 반환."""
    if not pairs:
        return 0
    updated = 0
    for i in range(0, len(pairs), BATCH):
        chunk = pairs[i : i + BATCH]
        cases = " ".join(
            "WHEN %d THEN '%s'" % (nid, url.replace("'", "''")) for nid, url in chunk
        )
        ids = ", ".join(str(nid) for nid, _ in chunk)
        sql = (
            f"UPDATE news SET origin_link = CASE id {cases} END "
            f"WHERE id IN ({ids});"
        )
        res = cfnew.sql(sql, database_id=cfnew.A24_DB)
        if isinstance(res, dict):
            raise RuntimeError(f"UPDATE 실패: {res}")
        updated += len(chunk)
        log(f"  배치 {i // BATCH + 1}: {len(chunk)}건 갱신")
    return updated


# ============================================
# CLI
# ============================================
def cmd_report():
    col = has_column()
    if not col:
        log("news.origin_link 컬럼 없음 — --apply 로 생성+백필 필요")
    rows = fetch_rows(with_origin=col)
    by_source = {}
    for r in rows:
        st = by_source.setdefault(
            r.get("source"), {"rows": 0, "missing": 0, "diff": 0, "models_dev_link": 0}
        )
        st["rows"] += 1
        target = row_origin_link(r)
        if not r.get("origin_link"):
            st["missing"] += 1
        elif r.get("origin_link") != target:
            st["diff"] += 1
        if "models.dev" in (r.get("link") or ""):
            st["models_dev_link"] += 1
    log(f"무료 모델 news {len(rows)}행")
    for source, st in sorted(by_source.items()):
        log(
            f"  {source}: {st['rows']}행 · origin_link 없음 {st['missing']} · "
            f"불일치 {st['diff']} · link가 models.dev {st['models_dev_link']}"
        )
    log("샘플(최신 5건):")
    for r in sorted(rows, key=lambda x: x.get("id") or 0, reverse=True)[:5]:
        log(
            f"  #{r.get('id')} [{r.get('source')}] {r.get('original_title')}\n"
            f"      link        = {r.get('link')}\n"
            f"      origin_link = {r.get('origin_link') or '(없음)'} → {row_origin_link(r)}"
        )


def cmd_apply(dry_run=False, verify=False):
    ensure_column(dry_run=dry_run)
    if dry_run and not has_column():
        # 컬럼이 없으면 origin_link 를 SELECT 할 수 없다 — link 기준으로만 판정.
        rows = cfnew.sql(
            "SELECT id, source, original_title, link FROM news WHERE source IN (%s) ORDER BY id;"
            % ", ".join("'" + s.replace("'", "''") + "'" for s in SOURCE_PROVIDER),
            database_id=cfnew.A24_DB,
        )
        if isinstance(rows, dict):
            raise RuntimeError(f"조회 실패: {rows}")
        rows = rows or []
        current = {}
    else:
        rows = fetch_rows()
        current = {r["id"]: r.get("origin_link") for r in rows}

    pairs, unchanged, dead = [], 0, 0
    cache = {}
    for r in rows:
        target = row_origin_link(r)
        if not target:
            continue
        if verify and target not in cache:
            cache[target] = downgrade_if_dead(target, r.get("source"))
        if verify:
            fixed = cache[target]
            if fixed != target:
                dead += 1
            target = fixed
        if current.get(r.get("id")) == target:
            unchanged += 1
            continue
        pairs.append((r.get("id"), target))

    log(
        f"대상 {len(rows)}행 · 변경 {len(pairs)} · 이미 일치 {unchanged}"
        + (f" · Kilo 404→목록 {dead}" if verify else "")
    )
    if dry_run:
        for nid, url in pairs[:10]:
            log(f"  [dry-run] #{nid} → {url}")
        if len(pairs) > 10:
            log(f"  [dry-run] … 외 {len(pairs) - 10}건")
        return 0
    updated = set_origin_links(pairs)
    log(f"완료: {updated}행 갱신")
    return updated


def main():
    ap = argparse.ArgumentParser(description="AIK24-PIPE-07 무료 모델 원문 링크(origin_link) 해석·백필")
    ap.add_argument("--report", action="store_true", help="현황만 출력 (기본)")
    ap.add_argument("--apply", action="store_true", help="컬럼 보장 + origin_link 백필")
    ap.add_argument("--dry-run", action="store_true", help="D1 쓰기 없이 대상만 출력")
    ap.add_argument("--verify", action="store_true", help="Kilo per-model 페이지 404 → 목록 페이지")
    args = ap.parse_args()

    if args.apply:
        cmd_apply(dry_run=args.dry_run, verify=args.verify)
    else:
        cmd_report()


if __name__ == "__main__":
    main()
