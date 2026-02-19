#!/bin/bash
# AI 노인복지 뉴스 개인 조회 스크립트
cd /Users/twinssn/Projects/aikorea24

echo "========================================"
echo "  AI 노인복지 뉴스 (최근 20건)"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "========================================"

npx wrangler d1 execute aikorea24-db --remote --json \
  --command "SELECT title, link, source, pub_date FROM news WHERE category='senior' ORDER BY created_at DESC LIMIT 20" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data[0].get('results', [])
if not items:
    print('\n  아직 수집된 노인복지 뉴스가 없습니다.')
    print('  수집 실행: python3 api_test/news_collector.py')
else:
    for i, r in enumerate(items, 1):
        print(f'\n  {i}. {r[\"title\"]}')
        print(f'     {r[\"source\"]} | {r[\"pub_date\"]}')
        print(f'     {r[\"link\"]}')
print(f'\n  총 {len(items)}건')
print('========================================')
"
