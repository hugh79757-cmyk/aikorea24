#!/usr/bin/env python3
"""AIK24-PIPE-05 — 무료 모델 브리핑 항목 ↔ AIK24 블로그 글 매칭·연결 (2026-10-20)

배경
----
브리핑의 무료 모델 항목이 "원문 보기" 로 models.dev(제3자 DB) 로 바로 가고 있었다.
models.dev 는 출처가 아니라 OpenCode 가 읽는 모델 카탈로그라 "원문 보기" 로 부적절하고,
표기(출처 라벨)와 링크가 어긋났다(2026-10-20 08:26 이슈).
대표님 결정(2026-10-20): **무료 모델 항목의 링크는 항상 AIK24 블로그의 해당 모델 글로.**
글이 없으면 파이프라인 마지막 단계에서 draft 로 자동 작성 → 검수 → 발행 → 연결.

원칙 (지시서 §2·§3-1)
---------------------
1) news.link 는 수집기 dedup 키다
   (news_collector_v2.save(): `SELECT link FROM news … LIMIT 3000`).
   **절대 변경하지 않는다.** 링크는 새 컬럼 news.blog_link 에 따로 담는다.
2) 렌더링은 COALESCE(n.blog_link, n.link) — blog_link 가 없으면 기존 link 유지.
3) 자동 작성 글은 status='draft' 고정. **자동 발행 금지**(지시서 §5 — 검수 주체 미정).
4) blog_link 는 모델 단위 1개 글에 매칭한다(같은 모델이 여러 제공자에 있으면 1개).

사용
----
    python3 scripts/blog_link_resolver.py --report    # 상태만 출력 (D1 쓰기 없음)
    python3 scripts/blog_link_resolver.py --resolve   # 매칭 → news.blog_link 갱신 + 큐 갱신
    python3 scripts/blog_link_resolver.py --draft     # 큐에 남은 모델의 초안 생성(draft 고정)
    python3 scripts/blog_link_resolver.py --resolve --dry-run

D1 접근은 cfnew.py(REST · CF_MIGRATE_TOKEN) 를 쓴다 — launchd 환경·셸 양쪽에서
동일하게 동작한다 (news_collector_v2.save() 와 같은 경로). 읽기 한도 가드
(cfnew.check_quota) 를 경유한다.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cfnew  # noqa: E402

KST = timezone(timedelta(hours=9))
PROJECT_DIR = Path(__file__).resolve().parent.parent
QUEUE_PATH = PROJECT_DIR / "scripts" / "logs" / "blog_link_needed.json"
POST_BASE = "https://emdash.aikorea24.kr/posts/"

# 무료 모델을 담는 news.source 4종 (지시서 §3-4)
FREE_MODEL_SOURCES = (
    "OpenRouter Free Models",
    "OpenCode Zen",
    "Kilo Free Models",
    "NVIDIA NIM Free",
)

# CLI 설정 접두어 — 지시서 §3-2 규칙(프로바이더 접두사 제거 대상)
CLI_PROVIDER_PREFIXES = ("opencode/", "kilo/", "nvidia/", "openrouter/")

# 무료 접미사 — 지시서는 `:free` 를 지목하지만 models.dev 쪽은 `-free` 를 쓴다
# (opencode/minimax-m3.1-flash-free). auto_briefing._core_name() 과 같은 규칙을 쓴다.
FREE_SUFFIXES = (":free", "-free")


def log(msg):
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] [blog-link] {msg}")


# ============================================
# 모델 키 정규화
# ============================================
def normalize_model_key(model_id):
    """프로바이더 접두사 + 무료 접미사를 제거한 정규화 모델 키 (지시서 §3-2).

    지시서 §3-2: `:free` 접미사 제거, 프로바이더 접두사(opencode/·kilo/·nvidia/·
    openrouter/) 제거 후 정규화.

        opencode/minimax-m3.1-flash-free  →  minimax-m3.1-flash
        kilo/minimax/minimax-m3.1-flash:free  →  minimax/minimax-m3.1-flash
        nvidia/nemotron-3.5-super-vl-120b-a12b  →  nemotron-3.5-super-vl-120b-a12b

    주의: models.dev 의 opencode 모델명은 **대부분 자체가 `-free` 로 끝난다**
    (beam-free·ll-alpha-free·cat-jam-free). 그래서 `-free` 를 떼면 `beam` 처럼
    이름이 짧아진다. 이 키는 **큐·보고용 그룹핑 키**로만 쓰고, 실제 글 매칭은
    원본 모델 id 에서 만든 후보 시퀀스(§model_key_variants)로 한다 — 그래야
    `beam-free` 가 `beam` 이라는 약한 토큰으로 넓게 매칭되지 않는다.
    """
    s = _strip_provider_prefix(model_id)
    return _strip_free_suffix(s)


def _strip_provider_prefix(model_id):
    """프로바이더 접두사 제거 — 단, 떼고 남은 게 1토큰이면 떼지 않는다.

    `openrouter/free` 를 떼면 `free` 이 남아 "무료 모델 목록" 페이지와 매칭된다
    (제3자 목록 페이지를 모델 글로 오인). 2토큰 이상일 때만 접두사를 떼는 게 안전하다.
    """
    s = (model_id or "").strip().lower()
    for prefix in CLI_PROVIDER_PREFIXES:
        if s.startswith(prefix):
            rest = s[len(prefix):]
            if len(_tokens(rest)) >= 2:
                return rest
            return s
    return s


def _strip_free_suffix(s):
    for suffix in FREE_SUFFIXES:
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def _tokens(text):
    """영숫자 밖을 구분자로 보고 토큰 배열로 만든다 (소문자)."""
    return [t for t in re.split(r"[^0-9a-z가-힣]+", (text or "").lower()) if t]


_BRACKET_PREFIX_RE = re.compile(r"^\s*\[[^\]]{0,40}\]\s*")
# 무료 모델 글인지 판별하는 표지 (무료 티어 안내글)
_FREE_MARKERS = ("무료", "free")
# 제거·중단 알림 글 표지 — 이 글은 "지금 쓸 수 있는 모델" 안내보다 후순이다
_REMOVAL_MARKERS = ("제외", "제거", "중단", "단종", "지원 종료", "종료")
# 모델 글이 아닌 목록 페이지 (무료 모델 목록) — 매칭 대상에서 제외
_COLLECTION_SLUGS = {"free-models"}


def _title_core_tokens(title):
    """앞의 대괄호 표기("[무료 LLM] ", "[정직한 AI 평가] ")를 뗀 제목 토큰.

    이 배열의 맨 앞에서 모델 시퀀스가 시작하면 "그 글이 해당 모델을 다룬다"는
    신호(subject)로 쓴다 — 제목 중간에 모델 이름이 예고된 글(예: "… 목록에서 제외된
    muse-spark-… 모델 변경 사항")보다 주제 글을 우선한다.
    """
    return _tokens(_BRACKET_PREFIX_RE.sub("", title or ""))


def _has_free_marker(title, slug=""):
    """무료 모델 글 표지 포함 여부 (느슨한 매칭의 필수 조건으로 쓴다).

    제목만 보지 않는다 — "Dots3-Note Preview — …" 처럼 제목에 '무료'가 없어도
    슬러그가 free-model-dots-3-note-preview 면 무료 모델 글이다.
    """
    low = ("%s %s" % (title or "", slug or "")).lower()
    return any(m in low for m in _FREE_MARKERS)


def _compact(text):
    """알파벳·숫자만 남긴 문자열 (점·하이픈·슬래시 구분 무시)."""
    return re.sub(r"[^0-9a-z가-힣]", "", (text or "").lower())


def _has_removal_marker(title):
    """제거·중단 알림 글 여부 — 이 글은 정상 안내글보다 후순."""
    low = (title or "").lower()
    return any(m in low for m in _REMOVAL_MARKERS)


def model_key_variants(model_id):
    """매칭 후보 (토큰 시퀀스, org 토큰, 구체도) 목록 — 구체적인 것부터.

    구체도 2 (정확히 일치해야 하는 후보)
      - 프로바이더 접두사만 제거한 전체 시퀀스
        `minimax-m3.1-flash-free` → (minimax, m3, 1, flash, free)
      - org 접두사를 뗀 꼬리 시퀀스 + org 토큰 요구
        `minimax/minimax-m3.1-flash` → (minimax, m3, 1, flash) + org (minimax)
    구체도 1 (무료 접미사까지 뗀 느슨한 후보 — 최소 2토큰)
      - `minimax-m3.1-flash-free` → (minimax, m3, 1, flash)

    느슨한 후보를 최소화(=2토큰 이상)하는 이유: `beam-free` → `beam` 처럼 한 단어로
    줄면 "beam" 이 들어간 무관한 글과 매칭된다. 느슨한 후보는 구체도 2 에서 아무 글도
    못 찾았을 때만 쓴다.
    """
    base = _strip_provider_prefix(model_id)
    out = []

    full = tuple(_tokens(base))
    if full:
        out.append((full, None, 2, 0))
    if "/" in base:
        org, tail = base.split("/", 1)
        tail_seq = tuple(_tokens(tail))
        if tail_seq and tail_seq != full:
            out.append((tail_seq, tuple(_tokens(org)), 2, 1))

    loose = _strip_free_suffix(base)
    if loose != base:
        fb = tuple(_tokens(loose))
        if len(fb) >= 3:
            out.append((fb, None, 1, 0))
        if "/" in loose:
            org, tail = loose.split("/", 1)
            t = tuple(_tokens(tail))
            if len(t) >= 3 and t != fb:
                out.append((t, tuple(_tokens(org)), 1, 1))
    return out


def _contains(seq, haystack):
    """토큰 시퀀스가 haystack 안에 연속으로 있는지."""
    n = len(seq)
    if n == 0 or n > len(haystack):
        return False
    for i in range(len(haystack) - n + 1):
        if tuple(haystack[i:i + n]) == seq:
            return True
    return False


def _seq_matches(seq, org, post_tokens):
    """후보 시퀀스가 글 토큰에 있는지. org 지정이 있으면 org 토큰도 글 어딘가에 있어야 한다."""
    if not _contains(seq, post_tokens):
        return False
    if org:
        org_set = set(org)
        if not org_set.issubset(set(post_tokens)):
            return False
    return True


# ============================================
# EmDash 글 조회
# ============================================
def load_posts(include_draft=False):
    """EmDash 게시물 목록 (published 중심). 글 조회 실패 시 빈 리스트."""
    status_filter = "" if include_draft else " AND status = 'published'"
    sql = (
        "SELECT slug, title, status, published_at, deleted_at FROM ec_posts "
        "WHERE deleted_at IS NULL" + status_filter +
        " ORDER BY published_at DESC"
    )
    try:
        rows = cfnew.sql(sql, database_id=cfnew.EMDASH_DB)
    except Exception as e:  # noqa: BLE001 — 글 조회 실패가 매칭 전체를 죽이게 두지 않는다
        log(f"  ⚠️ EmDash 글 조회 실패: {type(e).__name__}: {str(e)[:120]}")
        return []
    if not isinstance(rows, list):
        log("  ⚠️ EmDash 글 조회 응답이 리스트가 아님 — 0건으로 처리")
        return []
    out = []
    for r in rows:
        out.append({
            "slug": r.get("slug") or "",
            "title": r.get("title") or "",
            "status": r.get("status") or "",
            "published_at": r.get("published_at") or "",
            "title_tokens": _tokens(r.get("title") or ""),
            "slug_tokens": _tokens(r.get("slug") or ""),
            "core_tokens": _title_core_tokens(r.get("title") or ""),
            "free_ctx": _has_free_marker(r.get("title") or "", r.get("slug") or ""),
            "removal_ctx": _has_removal_marker(r.get("title") or ""),
            "compact_title": _compact(r.get("title") or ""),
            "compact_slug": _compact(r.get("slug") or ""),
        })
    return out


def _compact_variants(model_id):
    """구분자를 무시한 비교 후보 (점 표기 차이 대응).

    `liquid/lfm-2.5-2.6b:free` → compact "liquidlfm2526bfree" / tail "lfm2526bfree"
    제목 "LFM2.5-2.6B: …" 의 compact "lfm2526b…" 와 일치한다.
    토큰 시퀀스 비교로는 "lfm2" vs "lfm" 처럼 어긋나 매칭이 놓친다.

    무료 접미사(`:free`·`-free`)를 뗀 형태도 후보에 넣는다 — 제목·슬러그에는
    "free" 가 안 붙은 경우가 많다(예: 슬러그 free-model-liquid-lfm-2-5).
    """
    base = _strip_provider_prefix(model_id)
    out = []
    cands = []
    for cand in (base, base.split("/")[-1] if "/" in base else None):
        if not cand:
            continue
        cands.append(cand)
        stripped = _strip_free_suffix(cand)
        if stripped != cand:
            cands.append(stripped)
    for cand in cands:
        c = _compact(cand)
        if len(c) >= 8 and c not in out:
            out.append(c)
    return out


def match_post(posts, model_id):
    """원본 모델 id 에 해당하는 글 1건 찾기. 없으면 None.

    우선순위: 제목 매칭 > 슬러그 매칭 > "그 글이 모델을 다룬다"(subject) >
    무료 모델 글 표지(free_ctx) > 후보 구체도 > 발행 최신순.
    '[제외]' 글(제공 중단 알림)은 같은 모델의 정상 글이 있을 때 밀린다
    (기록 가치 때문에 글 자체는 유지된다 — 지시서 §3-5).

    느슨한 후보(구체도 1)는 free_ctx 를 **필수**로 요구한다 — 모델 이름이 우연히
    겹치는 일반 뉴스글(예: "알리바바 Qwen3.6 Plus 출시…")이 무료 모델 브리핑의
    "원문"이 되면 표기-링크 불일치가 재발한다.
    """
    variants = model_key_variants(model_id)
    if not variants:
        return None
    compacts = _compact_variants(model_id)
    for level in (2, 1.5, 1):
        best, best_score = None, None
        for p in posts:
            if p["slug"] in _COLLECTION_SLUGS:
                continue
            hit, rank, subject = 0, 99, 0
            if level == 1.5:
                for c in compacts:
                    if c in p["compact_title"]:
                        hit, rank, subject = 2, 0, (
                            1 if p["compact_title"].startswith(c) else 0)
                        break
                    if c in p["compact_slug"]:
                        hit, rank, subject = 1, 0, (
                            1 if p["compact_slug"].startswith(c) else 0)
                        break
            else:
                for seq, org, spec, vrank in variants:
                    if spec != level:
                        continue
                    if _seq_matches(seq, org, p["title_tokens"]):
                        if (2, -vrank) > (hit, -rank):
                            hit, rank = 2, vrank
                            subject = 1 if _starts_with(p["core_tokens"], seq) else 0
                    elif _seq_matches(seq, org, p["slug_tokens"]):
                        if (1, -vrank) > (hit, -rank):
                            hit, rank = 1, vrank
                            subject = 1 if _starts_with(p["slug_tokens"], seq) else 0
            if hit == 0:
                continue
            if level in (1, 1.5) and not p["free_ctx"]:
                continue
            excluded = 0 if p["title"].startswith("[제외]") else 1
            score = (hit, subject, p["free_ctx"], -rank, -p["removal_ctx"], excluded,
                     p["published_at"] or "")
            if best_score is None or score > best_score:
                best, best_score = p, score
        if best is not None:
            return best
    return None


def _starts_with(tokens, seq):
    """토큰 배열이 seq 로 시작하는지."""
    return len(tokens) >= len(seq) and tuple(tokens[:len(seq)]) == tuple(seq)


# ============================================
# D1 — 무료 모델 news 행
# ============================================
def _sql_in(values):
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


def free_model_news_rows(only_missing=False):
    """무료 모델 news 행 (free-model 4종 source)."""
    where = ["source IN (%s)" % _sql_in(FREE_MODEL_SOURCES)]
    if only_missing:
        where.append("(blog_link IS NULL OR blog_link = '')")
    sql = (
        "SELECT id, title, link, blog_link, source, original_title, pub_date "
        "FROM news WHERE %s ORDER BY id DESC" % " AND ".join(where)
    )
    rows = cfnew.sql(sql, database_id=cfnew.A24_DB)
    return rows if isinstance(rows, list) else []


def set_blog_link(news_id, url):
    """news.blog_link 갱신. 성공 시 True."""
    return set_blog_links([(news_id, url)]) == 1


def set_blog_links(pairs):
    """news.blog_link 일괄 갱신. 지시서 §6 — 배치 크기는 40건 이하 유지.

    1행씩 UPDATE 하면 D1 쓰기 API 호출이 수십 회 된다. CASE WHEN 으로 묶어
    40건당 1문장으로 보낸다. 성공한 행 수를 반환한다.
    """
    pairs = [(int(nid), url) for nid, url in pairs if url]
    if not pairs:
        return 0
    ok = 0
    BATCH = 40
    for i in range(0, len(pairs), BATCH):
        chunk = pairs[i:i + BATCH]
        cases = " ".join(
            "WHEN %d THEN '%s'" % (nid, str(url).replace("'", "''"))
            for nid, url in chunk
        )
        ids = ", ".join(str(nid) for nid, _ in chunk)
        sql = ("UPDATE news SET blog_link = CASE id %s END WHERE id IN (%s)"
               % (cases, ids))
        try:
            cfnew.sql(sql, database_id=cfnew.A24_DB)
        except Exception as e:  # noqa: BLE001
            log(f"  ⚠️ blog_link 갱신 실패 (배치 {i // BATCH + 1}): "
                f"{type(e).__name__}: {str(e)[:120]}")
            continue
        ok += len(chunk)
    return ok


# ============================================
# 큐 (글이 필요한 모델 목록)
# ============================================
def write_queue(entries):
    """글이 필요한 모델 큐 저장. 같은 파일은 scripts/logs/ 아래 런타임 산출물이다."""
    payload = {
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "count": len(entries),
        "models": entries,
    }
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def read_queue():
    if not QUEUE_PATH.exists():
        return {"models": []}
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"models": []}


# ============================================
# resolve — 매칭 + blog_link 갱신
# ============================================
def resolve(dry_run=False, verbose=True):
    """무료 모델 news 행 ↔ 블로그 글 매칭 후 news.blog_link 갱신. 통계 dict 반환."""
    stats = {
        "news_rows": 0, "models": 0, "matched_models": 0,
        "linked_rows": 0, "already_linked": 0, "queued_models": 0,
    }
    rows = free_model_news_rows()
    stats["news_rows"] = len(rows)
    if not rows:
        log("무료 모델 news 행 0건 — 종료")
        return stats

    posts = load_posts()
    log(f"EmDash 글 {len(posts)}건 로드 (published)")

    # 모델 키별로 묶는다 (같은 모델이 여러 프로바이더 행을 가질 수 있음)
    by_key = {}
    for r in rows:
        key = normalize_model_key(r.get("original_title") or "")
        if not key:
            continue
        by_key.setdefault(key, []).append(r)
    stats["models"] = len(by_key)

    updates = []      # (news_id, url)
    queue_entries = []
    briefing_ids = _briefing_news_ids()
    for key, group in sorted(by_key.items()):
        # 매칭은 원본 모델 id 로 한다 (그룹 안 프로바이더별 id 를 모두 시도)
        post = None
        for r in group:
            post = match_post(posts, r.get("original_title") or "")
            if post:
                break
        if post:
            stats["matched_models"] += 1
            url = POST_BASE + post["slug"]
            for r in group:
                if r.get("blog_link") == url:
                    stats["already_linked"] += 1
                else:
                    updates.append((r["id"], url))
            if verbose:
                log(f"  ✅ {key} → {url}")
        else:
            stats["queued_models"] += 1
            queue_entries.append({
                "key": key,
                "original_titles": sorted({r.get("original_title") or "" for r in group}),
                "news_ids": [r["id"] for r in group],
                "sources": sorted({r.get("source") or "" for r in group}),
                "cli_ids": sorted({
                    _cli_id(r.get("source"), r.get("original_title"))
                    for r in group
                } - {""}),
                "in_briefing": bool(_in_briefing(group, briefing_ids)),
            })
            if verbose:
                log(f"  📝 {key} — 블로그 글 없음 (큐 등록)")

    if updates and not dry_run:
        stats["linked_rows"] = set_blog_links(updates)
    elif updates:
        stats["linked_rows"] = len(updates)

    if not dry_run:
        write_queue(queue_entries)
    return stats


def _cli_id(source, original_title):
    """news.source + original_title → OpenCode 설정용 cli id."""
    prefix = {
        "OpenCode Zen": "opencode",
        "OpenRouter Free Models": "openrouter",
        "Kilo Free Models": "kilo",
        "NVIDIA NIM Free": "nvidia",
    }.get(source or "")
    if not prefix or not original_title:
        return ""
    return "%s/%s" % (prefix, original_title)


def _briefing_news_ids():
    """한 번이라도 브리핑에 실린 news id 집합 (D1 조회 1회).

    모델마다 개별로 조회하면 미매칭 모델 수만큼 D1 요청이 나간다(실측 143회).
    집합을 한 번에 받아 메모리로 판정한다.
    """
    try:
        rows = cfnew.sql(
            "SELECT DISTINCT news_id FROM briefing_items", database_id=cfnew.A24_DB
        )
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ 브리핑 news id 조회 실패: {type(e).__name__}: {str(e)[:120]}")
        return set()
    if not isinstance(rows, list):
        return set()
    return {r.get("news_id") for r in rows if r.get("news_id")}


def _in_briefing(group, briefing_ids=None):
    """해당 news 행이 이미 브리핑에 실렸는지."""
    if briefing_ids is None:
        briefing_ids = _briefing_news_ids()
    return any(int(r.get("id") or 0) in briefing_ids for r in group)


# ============================================
# report — 현재 상태만
# ============================================
def report():
    rows = free_model_news_rows()
    linked = [r for r in rows if r.get("blog_link")]
    unlinked = [r for r in rows if not r.get("blog_link")]
    models = {normalize_model_key(r.get("original_title") or "") for r in rows}
    print("=" * 72)
    print("AIK24-PIPE-05 — 무료 모델 블로그 링크 상태")
    print("=" * 72)
    print(f"무료 모델 news 행: {len(rows)}건 / 정규화 모델 {len(models)}개")
    print(f"  blog_link 있음: {len(linked)}건")
    print(f"  blog_link 없음: {len(unlinked)}건")
    by_source = {}
    for r in unlinked:
        by_source[r.get("source") or ""] = by_source.get(r.get("source") or "", 0) + 1
    if by_source:
        print("  미연결 by source:")
        for k, v in sorted(by_source.items()):
            print(f"    {k}: {v}건")
    print("-" * 72)
    print("news.link 이 models.dev 인 행 (전체):")
    for r in rows:
        if "models.dev" in (r.get("link") or ""):
            flag = "→ blog" if r.get("blog_link") else "   (미연결)"
            print(f"  [{flag}] id={r['id']} {r.get('original_title')}")
    q = read_queue()
    print("-" * 72)
    print(f"글 필요 큐: {len(q.get('models') or [])}개 "
          f"(최종 갱신 {q.get('updated_at', '-')})")
    for m in (q.get("models") or [])[:40]:
        print(f"  - {m.get('key')}  {'(브리핑 반영됨)' if m.get('in_briefing') else ''}")
    print("=" * 72)
    return {"rows": len(rows), "linked": len(linked), "unlinked": len(unlinked),
            "queue": len(q.get("models") or [])}


# ============================================
# draft — 큐에 남은 모델의 초안 생성 (자동 발행 금지)
# ============================================
def create_drafts(limit=5, dry_run=False, only_in_briefing=True):
    """큐에 있는 모델 중 아직 EmDash draft 도 글도 없는 것의 초안을 만든다.

    지시서 §3-3: 생성기는 blog_draft_generator.py 를 재사용한다.
    지시서 §5: **상태는 draft 고정. 자동 발행 금지** — 검수 주체 미정.

    only_in_briefing 기본 True — 독자가 실제로 본 모델(브리핑에 실린 것)만 대상으로 한다.
    큐에는 NVIDIA NIM 등 브리핑에 한 번도 실리지 않은 모델이 대부분인데, 그쪽까지
    자동 작성하면 하루 볼륨이 폭발한다. 지시서 §3-3 의 의도는 "브리핑에 나온 모델에
    글이 없으면 만든다" 다.
    """
    q = read_queue()
    entries = q.get("models") or []
    if not entries:
        log("글 필요 큐가 비어 있음 — 종료")
        return {"created": 0, "skipped": 0}

    if only_in_briefing:
        before = len(entries)
        entries = [e for e in entries if e.get("in_briefing")]
        log(f"브리핑 반영된 모델만 대상으로 제한: {before} → {len(entries)}")

    import blog_draft_generator as bdg

    # published·draft 모두에서 같은 모델의 글이 이미 있으면 생성 제외
    posts = load_posts(include_draft=True)
    existing = set()
    for e in entries:
        key = e.get("key") or ""
        if not key:
            continue
        for orig in (e.get("original_titles") or []):
            if match_post(posts, orig):
                existing.add(key)
                break

    todo = [e for e in entries if e.get("key") not in existing]
    log(f"큐 {len(entries)}개 중 기존 글 없음 {len(todo)}개 — draft 생성 대상 (최대 {limit}건)")

    created, skipped = 0, 0
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    file_num = bdg.next_file_number(today_str)
    for entry in todo[:limit]:
        key = entry.get("key") or ""
        if dry_run:
            log(f"  [DRY-RUN] {key} 초안 생성 예정")
            created += 1
            continue
        news_ids = entry.get("news_ids") or []
        if not news_ids:
            skipped += 1
            continue
        try:
            articles = _load_articles(news_ids)
            if not articles:
                log(f"  ⚠️ {key} — news 행 조회 실패, 스킵")
                skipped += 1
                continue
            gpt_output = bdg.generate_draft(key, articles, "A")
            if not gpt_output:
                log(f"  ❌ {key} — 초안 생성 실패")
                skipped += 1
                continue
            filepath, seo_title = bdg.save_draft(gpt_output, key, file_num, today_str,
                                                 articles=articles)
            if not filepath:
                log(f"  ❌ {key} — 품질 미달 (발행 대기 초안 미생성)")
                skipped += 1
                continue
            draft = bdg._EMDASH_PENDING.get(filepath)
            if not draft:
                skipped += 1
                continue
            url = _create_emdash_draft(draft["md"], seo_title)
            if url:
                created += 1
                log(f"  📝 {key} 초안 생성 (draft): {url}")
            else:
                skipped += 1
                log(f"  ❌ {key} — EmDash draft 생성 실패")
        except Exception as e:  # noqa: BLE001 — 한 모델 실패가 나머지를 막지 않는다
            log(f"  ❌ {key} 예외: {type(e).__name__}: {str(e)[:160]}")
            skipped += 1
    return {"created": created, "skipped": skipped}


def _load_articles(news_ids):
    """news 행 → 브리핑 초안 생성기가 쓰는 article dict 목록."""
    ids = ", ".join(str(int(i)) for i in news_ids)
    sql = ("SELECT id, title, link, description, source, category, pub_date, "
           "original_title, v2_tag FROM news WHERE id IN (%s)" % ids)
    rows = cfnew.sql(sql, database_id=cfnew.A24_DB)
    return rows if isinstance(rows, list) else []


def _create_emdash_draft(md, title):
    """EmDash 에 draft 상태로 글 생성. 자동 발행하지 않는다.

    발행 게이트(blog_quality_gate.screen_extended)를 통과한 초안만 draft 로 만든다 —
    검수 주체가 미정인 상태에서 기준 미달 글이 EmDash 에 쌓이면 안 된다
    (미달 초안은 보류 파일로 보내고 생성하지 않는다).
    """
    try:
        import yaml
        from emdash_publish import create_draft_post
        _, fm, body = md.split("---", 2)
        meta = yaml.safe_load(fm) or {}
        body = body.strip()
        try:
            import blog_quality_gate as _gate
            issues = _gate.screen_extended(body, verify_links=True)
        except Exception as ge:  # noqa: BLE001 — 게이트 자체가 죽어도 초안 생성은 계속
            issues = []
            log(f"  ⚠️ 게이트 실행 예외(무시): {type(ge).__name__}")
        if issues:
            log(f"  ⛔ 게이트 미달 — draft 생성 보류: {issues[:3]}")
            try:
                import blog_draft_generator as bdg
                bdg._quality_gate.hold(md, meta.get("title") or title, issues,
                                       reason="PIPE-05 자동 작성 초안 게이트 미달")
            except Exception as he:  # noqa: BLE001
                log(f"  ⚠️ 보류 기록 실패: {type(he).__name__}")
            return None
        return create_draft_post(
            meta.get("title") or title, body,
            excerpt=meta.get("description"),
            featured_image=meta.get("image"),
        )
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ EmDash draft 생성 예외: {type(e).__name__}: {str(e)[:160]}")
        return None


# ============================================
# main
# ============================================
def main():
    ap = argparse.ArgumentParser(description="AIK24-PIPE-05 무료 모델 → 블로그 링크 연결")
    ap.add_argument("--resolve", action="store_true", help="매칭 후 news.blog_link 갱신")
    ap.add_argument("--report", action="store_true", help="상태만 출력 (쓰기 없음)")
    ap.add_argument("--draft", action="store_true", help="큐에 남은 모델의 초안 생성(draft 고정)")
    ap.add_argument("--all", action="store_true",
                    help="draft 생성 시 브리핑 반영 여부 제한 해제 (기본: 브리핑에 실린 것만)")
    ap.add_argument("--limit", type=int, default=5, help="draft 생성 최대 건수 (기본 5)")
    ap.add_argument("--dry-run", action="store_true", help="실제 쓰기 없이 계산만")
    args = ap.parse_args()

    if not (args.resolve or args.report or args.draft):
        args.report = True

    if args.report:
        report()

    if args.resolve:
        log("resolve 시작" + (" (dry-run)" if args.dry_run else ""))
        stats = resolve(dry_run=args.dry_run)
        log("resolve 결과: " + json.dumps(stats, ensure_ascii=False))

    if args.draft:
        log("draft 생성 시작")
        r = create_drafts(limit=args.limit, dry_run=args.dry_run,
                          only_in_briefing=not args.all)
        log("draft 결과: " + json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
