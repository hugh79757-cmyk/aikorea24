#!/usr/bin/env python3
"""AIK24-TOOLS-ENTITY-01 Part B — /tools 등록 도구 전수 실체 판정.

`scripts/entity_verify.py` 의 판정 기준을 그대로 쓴다(수집기와 같은 기준).
md 1건당 1행: 슬러그 · URL · 판정(pass/fail/hold) · 단계 · 사유 · 근거.

사용:
    # 전체 전수 (결과: scripts/logs/entity_audit_<ts>.json / .csv)
    python3 scripts/audit_tool_entities.py --workers 8

    # 캘리브레이션용 무작위 표본
    python3 scripts/audit_tool_entities.py --sample 20 --seed 20261124

    # 특정 슬러그만
    python3 scripts/audit_tool_entities.py --slug morphiqo-2 --slug chatgpt

주의: 네트워크만 사용한다(D1·LLM·git 0회, `--with-d1` 지정 시 D1 읽기 1회).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import entity_verify  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(ROOT, 'src', 'content', 'tools')
LOG_DIR = os.path.join(ROOT, 'scripts', 'logs')

_FM_RE = re.compile(r'^---\s*\n(.*?)\n---', re.S)


def _field(fm: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*(.*)$', fm, re.M)
    if not m:
        return ''
    v = m.group(1).strip()
    if v.startswith('"') and v.endswith('"') and len(v) > 1:
        v = v[1:-1]
    return v


def load_entries(slugs: list[str] | None = None) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(TOOLS_DIR, '*.md'))):
        slug = os.path.basename(path)[:-3]
        if slugs and slug not in slugs:
            continue
        text = open(path, encoding='utf-8').read()
        m = _FM_RE.match(text)
        fm = m.group(1) if m else ''
        out.append({
            'slug': slug,
            'name': _field(fm, 'name'),
            'url': _field(fm, 'url'),
            'order': _field(fm, 'order'),
            'updated': _field(fm, 'updated'),
            'draft': _field(fm, 'draft').lower() == 'true',
        })
    return out


def d1_published_slugs() -> dict:
    """status='published' 인 제출 건의 slug → id. (D1 읽기 1회)"""
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import cfnew  # noqa: PLC0415
        rows = cfnew.sql(
            "SELECT id, slug FROM tool_submissions WHERE status='published';",
            database_id=cfnew.A24_DB,
        )
        if isinstance(rows, list):
            return {r['slug']: r['id'] for r in rows}
        return {}
    except Exception as e:  # noqa: BLE001
        print(f"[D1] published 조회 실패: {type(e).__name__}: {e}")
        return {}


def judge(entry: dict, delay: float = 0.0) -> dict:
    if delay:
        time.sleep(delay)
    try:
        res = entity_verify.verify_entity(entry.get('url', ''))
    except Exception as e:  # noqa: BLE001
        res = {'url': entry.get('url', ''), 'verdict': entity_verify.HOLD, 'stage': 'error',
               'reason': f'검증 예외: {type(e).__name__}: {e}', 'evidence': {}}
    row = dict(entry)
    row.update({
        'verdict': res.get('verdict'),
        'stage': res.get('stage'),
        'reason': res.get('reason'),
        'evidence': res.get('evidence') or {},
    })
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--sample', type=int, default=0, help='무작위 표본 크기(캘리브레이션)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--slug', action='append', default=[])
    ap.add_argument('--delay', type=float, default=0.0, help='건당 추가 대기(초)')
    ap.add_argument('--with-d1', action='store_true', help='D1 published 여부를 함께 표기(읽기 1회)')
    ap.add_argument('--tag', default='')
    args = ap.parse_args()

    entries = load_entries(set(args.slug) if args.slug else None)
    if not entries:
        print('대상 md 없음')
        return 1

    if args.sample:
        rnd = random.Random(args.seed or None)
        entries = rnd.sample(entries, min(args.sample, len(entries)))

    published = d1_published_slugs() if args.with_d1 else {}
    print(f'[전수조사] 대상 {len(entries)}건 · workers={args.workers}'
          + (f' · D1 published {len(published)}건' if args.with_d1 else ''))

    rows = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = {pool.submit(judge, e, args.delay): e for e in entries}
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            if published:
                row['d1_published'] = row['slug'] in published
                row['d1_id'] = published.get(row['slug'])
            rows.append(row)
            if i % 25 == 0 or i == len(entries):
                print(f'  {i}/{len(entries)} … {time.time() - t0:.1f}s')

    rows.sort(key=lambda r: (r['verdict'], r['slug']))
    counts = {k: sum(1 for r in rows if r['verdict'] == k)
              for k in (entity_verify.PASS, entity_verify.FAIL, entity_verify.HOLD)}
    total = sum(counts.values())
    assert total == len(rows), '판정 합계 불일치'
    print(f"[결과] 통과 {counts['pass']} · 불통과 {counts['fail']} · 보류 {counts['hold']} "
          f"= {total}건 (대상 {len(entries)}건)")

    os.makedirs(LOG_DIR, exist_ok=True)
    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    tag = f'_{args.tag}' if args.tag else ''
    base = os.path.join(LOG_DIR, f'entity_audit{tag}_{ts}')
    with open(base + '.json', 'w', encoding='utf-8') as f:
        json.dump({'generated_at': dt.datetime.now().isoformat(timespec='seconds'),
                   'counts': counts, 'total': total,
                   'with_d1': bool(args.with_d1), 'rows': rows}, f,
                  ensure_ascii=False, indent=2)
    with open(base + '.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['slug', 'name', 'url', 'verdict', 'stage', 'reason',
                    'evidence', 'updated', 'order', 'd1_published', 'd1_id'])
        for r in rows:
            w.writerow([r['slug'], r['name'], r['url'], r['verdict'], r['stage'], r['reason'],
                        json.dumps(r['evidence'], ensure_ascii=False),
                        r.get('updated', ''), r.get('order', ''),
                        r.get('d1_published', ''), r.get('d1_id', '')])
    print(f'저장: {os.path.relpath(base, ROOT)}.json / .csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
