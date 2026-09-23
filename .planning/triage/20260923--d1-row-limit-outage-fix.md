---
date: 2026-09-23
type: fix
status: resolved
---

# D1 브리핑없음 장애 — row read 한도초과 원인 규명 + 쿼리 최적화

## What
09-22/09-23 06:00 파이프라인이 "오늘 브리핑 없음"으로 종료. D1 free tier 일일 row read 한도초과(615717/615720)가 직접 원인. 선정뉴스 0건 연쇄.

## Why
db_reader.py P2 `ORDER BY pub_date DESC LIMIT 2000` 풀스캔 + background_search.py `LIKE '%kw%'` 키워드별 N회 풀스캔이 row-read 폭증 주범. 부수 발견: 09-21 사례는 _d1_run() env 미해제로 인한 7403 오판(실제 briefing_id=306 발행됨), outline_generator.py는 실행 주체 없는 미사용 파일.

## Files changed
- scripts/thread_topics/outline_generator.py — [사용안함-DISABLED 2026-09-23] docstring + main() 첫줄 sys.exit(0)
- scripts/blog_draft_generator.py — get_today_briefing_id() except절 return None→raise (D1실패/진짜빈브리핑 구분)
- scripts/threads/db_reader.py — P1 +LIMIT 200, P2 LIMIT 2000→200 + pub_date>=-3d
- pipeline/threads/contrast/background_search.py — find_background/find_cross kw루프 N회→OR묶음 1회, -30d→-7d
- logs/destructive_2026-09-23.log — finnews Worker 미배포(10007) 확인 기록

## How
systematic-debugging 4단계(Phase1 로그 역추적 → Phase2 호출자 전수 → Phase3 가설 1개씩 검증) + parallel subagents 4대(D1 사례·outline 호출자·7403 vs 한도초과·무거운 쿼리 Top5). 함정: wrangler OAuth 전환엔 TOKEN+ACCOUNT_ID 둘 다 해제 필요.

## Verification
AST 파싱 + import 검증 OK. db_reader 직접 import 실패는 기존 from dedup 경로 문제(수정 범위 밖). 잔여: auto_news_selector/briefing_dedup 3-JOIN 쿼리 LIMIT 없음(행수 수십건, 최적화 불필요 판정), finnews db_reader LIMIT 2000 미패치.
