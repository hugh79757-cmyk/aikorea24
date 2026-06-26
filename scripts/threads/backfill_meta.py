"""
backfill_meta.py — posted_article_meta 백필 (기존 발행 이력에서 D1 조회)

사용법: python scripts/threads/backfill_meta.py
"""
import json
import os
import re
import subprocess
import sys

THREADS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(THREADS_DIR, '..', '..')
POSTED_FILE = os.path.join(THREADS_DIR, 'posted.json')

def d1_query(sql):
    cmd = ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--command', sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=PROJECT_DIR)
        if r.returncode != 0:
            print(f'  D1 error (rc={r.returncode}): {r.stderr[:200]}')
            return []
        m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', r.stdout)
        if m:
            return json.loads(m.group(1))
        return []
    except subprocess.TimeoutExpired:
        print('  D1 timeout')
        return []
    except FileNotFoundError:
        print('  npx/wrangler not found')
        return []

def main():
    print('=== posted_article_meta 백필 ===')

    with open(POSTED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    existing_meta = data.get('posted_article_meta', {})
    posted_ids = set(str(x) for x in data.get('posted_ids', []))
    pitch_history_ids = set()
    for h in data.get('pitch_history', []):
        for aid in h.get('article_ids', []):
            pitch_history_ids.add(str(aid).lstrip('#').strip())

    all_ids = posted_ids | pitch_history_ids
    missing_ids = [i for i in sorted(all_ids) if i and i not in existing_meta]

    if not missing_ids:
        print(f'모든 ID({len(all_ids)}개)가 이미 posted_article_meta에 있습니다.')
        return

    print(f'총 {len(all_ids)}개 ID 중 {len(missing_ids)}개 백필 필요')

    # Batch query (D1 allows up to 100 values per IN clause, but let's be safe and do 50)
    batch_size = 50
    fetched = {}

    for i in range(0, len(missing_ids), batch_size):
        batch = missing_ids[i:i + batch_size]
        ids_str = ', '.join(batch)
        sql = f"SELECT id, title, COALESCE(original_title, '') as original_title, COALESCE(description, '') as description FROM news WHERE id IN ({ids_str})"
        print(f'  Querying batch {i//batch_size + 1}/{(len(missing_ids)-1)//batch_size + 1} ({len(batch)} IDs)...')
        rows = d1_query(sql)
        for row in rows:
            rid = str(row.get('id', ''))
            if rid:
                fetched[rid] = {
                    'title': row.get('title', '') or '',
                    'original_title': row.get('original_title', '') or '',
                    'description': row.get('description', '') or '',
                }
        print(f'    → fetched {len(fetched)}/{min(i+len(batch), len(missing_ids))}')

    # Update posted.json
    data['posted_article_meta'].update(fetched)
    with open(POSTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_in_meta = len(data['posted_article_meta'])
    still_missing = sum(1 for i in missing_ids if i not in fetched)
    print(f'\n완료!')
    print(f'  posted_article_meta: {total_in_meta}개')
    print(f'  백필 성공: {len(fetched)}개')
    print(f'  D1에 없는 ID (삭제됨?): {still_missing}개')

if __name__ == '__main__':
    main()
