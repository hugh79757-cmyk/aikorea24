#!/usr/bin/env python3
"""발행된 12문항 실측 글을 **최신 측정값으로 다시 만든다** (기본 dry-run).

배경 (2026-11-19)
  hy4-flash-free 는 2026-11-17 08:36 에 11/12 로 측정돼 글이 발행됐다. 2026-11-19
  재측정에서 12/12 가 나왔다(1차에서만 실패한 Q1 지시이행이 통과). 그런데 발행 글은
  11/12·9개 중 7위 표기를 그대로 들고 있었다. 글을 손으로 고치면 형식이 어긋나므로,
  **발행 파이프라인이 쓰는 같은 생성기**(free_model_eval_auto.build_draft)와 같은
  게이트(gate_draft)로 본문을 다시 만들고, 고정 slug 에 본문만 교체한다.

지켜야 하는 것
  · slug 는 바꾸지 않는다(외부 링크·허브 링크 보존). emdash_publish.upsert_post 가
    기존 id 로 PUT+publish 한다.
  · featured_image 는 기존 값을 그대로 넘긴다(넘기지 않으면 PUT 이 지운다).
  · 게이트를 통과하지 못하면 쓰지 않는다.
  · 측정 이력(1차 점수)을 본문에 남긴다 — 재측정으로 점수가 오르면 그 사실 자체가 정보다.

사용
  ../.venv/bin/python3 scripts/refresh_eval_post.py --model hy4-flash-free \
      --slug hy4-flash-free-실측-1112-무료로-어디까지-쓸-수-있나
  ../.venv/bin/python3 scripts/refresh_eval_post.py ... --apply
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import emdash_publish as ep  # noqa: E402
import free_model_eval_auto as auto  # noqa: E402
import model_eval  # noqa: E402

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
HISTORY_HEADING = "## AIK24 실측 결과"


def insert_history(body, note):
    """`## AIK24 실측 결과` 절 끝에 측정 이력 문단을 붙인다."""
    if not note:
        return body
    lines = body.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(HISTORY_HEADING):
            idx = i
            break
    if idx is None:
        return body + "\n\n" + note + "\n"
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    while end > idx + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:end] + ["", note] + lines[end:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="모델 id (예: hy4-flash-free)")
    ap.add_argument("--slug", required=True, help="기존 발행 글 slug (변경 금지)")
    ap.add_argument("--day", default=dt.date.today().isoformat())
    ap.add_argument("--cli", default=None)
    ap.add_argument("--history", default=None,
                    help="본문에 남길 측정 이력 한 줄 (예: '1차 2026-11-17 11/12 …')")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    cache = model_eval.cache_load()
    entry = cache.get(a.model) or {}
    if not entry.get("details"):
        print(f"! {a.model}: 캐시에 측정 기록이 없다 — 먼저 12문항 평가를 돌린다")
        return 1
    if entry.get("qv") != model_eval.EVAL_QUESTIONS_VERSION:
        print(f"! {a.model}: 캐시 문항세트 qv{entry.get('qv')} ≠ 현재 qv"
              f"{model_eval.EVAL_QUESTIONS_VERSION} — 재평가 먼저")
        return 1

    cli_id = a.cli or auto.resolve_cli_id(a.model, "zen", auto.cli_catalog()) or a.model
    res = entry
    title, body, excerpt = auto.build_draft(
        a.model, res, cli_id, entry.get("measured_context"), day=a.day)
    body = insert_history(body, a.history)

    ok, issues, body2 = auto.gate_draft(title, body, a.model)
    print(f"제목: {title}")
    print(f"발췌: {excerpt[:160]}")
    print(f"본문 {len(body2)}자 · 게이트 {'통과' if ok else '미달 %d건' % len(issues)}")
    for it in issues:
        print("  ! " + it)
    if not ok:
        print("\n[중단] 게이트 미달 — 쓰지 않는다")
        return 2

    existing = (ep.get_post(a.slug) or {}).get("item") or {}
    if not existing:
        print(f"! {a.slug}: 기존 글을 찾지 못했다 (새 slug 를 만들지 않는다)")
        return 1
    data = existing.get("data") or {}
    feat = data.get("featured_image")
    print(f"대상 글 id={existing.get('id')} slug={existing.get('slug')} "
          f"publishedAt={existing.get('publishedAt')}")
    print(f"기존 제목: {data.get('title')}")
    print(f"썸네일: {json.dumps(feat, ensure_ascii=False)[:120]}")

    if not a.apply:
        print("\n[DRY-RUN] 새 본문 전문:\n")
        print(body2)
        return 0

    os.makedirs(LOGS, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(LOGS, f"backup_eval_post_{a.model.replace('/', '_')}_{ts}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=1)
    print(f"백업: {backup}")

    url = ep.upsert_post(a.slug, title, body2, excerpt=excerpt, featured_image=feat)
    print(f"upsert: {url}")
    if not url:
        return 1

    after = (ep.get_post(a.slug) or {}).get("item") or {}
    d2 = after.get("data") or {}
    same_slug = after.get("slug") == existing.get("slug")
    same_pub = after.get("publishedAt") == existing.get("publishedAt")
    blocks = d2.get("content") or []
    txt = json.dumps(blocks, ensure_ascii=False)
    print(f"사후검증 — 제목 일치: {d2.get('title') == title} | slug 보존: {same_slug} "
          f"| publishedAt 보존: {same_pub} | 본문 블록 {len(blocks)}"
          f" | '{a.model}' 표기 {txt.count(a.model)}회")
    return 0 if (same_slug and same_pub) else 1


if __name__ == "__main__":
    sys.exit(main())
