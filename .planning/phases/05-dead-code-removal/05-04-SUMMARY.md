# Plan 05-04 Summary: auto_email_sender Template 1 복원

**Status:** ✅ Complete
**Wave:** Post-Phase 5

## Changes

| File | Action | Description |
|------|--------|-------------|
| `scripts/auto_email_sender.py` | 수정 | `generate_email_html` 전면 교체: simple template → rich template (template 1) |
| `CHANGES.md` | 수정 | 변경 이력 기록 |

## What Changed

### auto_email_sender.py

- **TOC 섹션 추가** — "📋 오늘의 브리핑" 목록 (모든 아이템 번호 + 제목)
- **아이템 카드 개선** — 숫자 뱃지(파랑 동그라미) + 제목 + 코멘트(파랑 좌측보더 박스) + 설명(150자)
- **링크 변경** — 외부 뉴스사이트(`news_link`) → 내부 브리핑 페이지(`aikorea24.kr/briefing/{date}#item-{n}`)
- **"전체 보기" 버튼** — 3개 초과 시 추가
- **AI 도구 섹션** — D1 `tools` 테이블에서 최신 6개 조회, 카테고리/가격/난이도 표시
- **헤더** — 🤖 + AI코리아24 + "오늘의 AI 브리핑 — {date}" + 그래디언트 라인
- **푸터** — 커뮤니티 링크 + 구독 해지
- **새 함수**: `get_tools()`, `_d1_query()`, `esc()` HTML 이스케이프

### Git History

| Commit | Message |
|--------|---------|
| `682ddb7` | `feat: auto_email_sender rich template 적용 (template 1)` |
| `4c0c411` | `docs: CHANGES.md 업데이트 — auto_email_sender template 1 전환` |

## Rationale

- 기존 **committed code**는 simple template (template 2) — 외부 링크, TOC/도구 없음
- **수동 발행** (`send-email.ts`)은 이미 rich template (template 1) 유지 중
- **working tree**에만 rich template 존재 (미커밋) → 발견 후 커밋
- 자동 발행(pipeline)과 수동 발행(admin UI)의 템플릿 일치 및 내부 링크 통일

## Verification

- `682ddb7` + `4c0c411` 정상 커밋 완료
- `git push origin/main` 필요 (별도 실행)
