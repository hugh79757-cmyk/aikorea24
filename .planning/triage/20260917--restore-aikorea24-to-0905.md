---
date: 2026-09-17
type: chore
status: resolved
---

# aikorea24.kr 09-05 정지 시점으로 전체 복원 + 강제 푸시

## What

블로그/쓰레드/전체 기능+설정을 09-05 정지 시점 상태로 되돌리고, 파이프라인
수동 1회 실행 + 블로그 6건 발행까지 완료.

## Why

사용자 판단: 쓰레드 정보 밀도 저하 + 블로그 이상 증상의 기점이 09-05 정지 /
09-13 재개 사이에 있었음. 그 구간 이후 변경분을 전부 되돌리라는 지시.

- 정지: 09-05 (`launchctl bootout` + `disable`, triage 20260905)
- 재개: 09-13 (triage 20260913)
- 복원 기준점: `39ba4689` (09-02 22:43, 정지 직전 마지막 커밋)

## Files changed

- git reset --hard `39ba4689` → 46 커밋 / 블로그 154 파일 / 도구 88건 롤백
- `src/content/blog/` — 신규 6건 (`2026-09-17-001` ~ `-006`) + 썸네일
- `.planning/worklog/WL-20260917-restore-0905.md` (신규)
- `logs/destructive_2026-09-17.log`

## How

파괴적 작업 프로토콜 4단계 준수:
1. **사전 카운트** — remote 46 커밋, 롤백 대상 블로그 154 파일
2. **롤백 수단** — tag `pre-restore-20260917_141848` + branch + stash
3. **실행** — `git reset --hard 39ba4689`, `npm run build`, `wrangler deploy`,
   파이프라인 수동 실행, `blog_draft_generator` 수동 실행 (6건 + 썸네일 + 배포)
4. **사후 검증** — `curl https://aikorea24.kr` 200, 블로그 6건 라이브 확인

`git push origin main` → non-fast-forward 거부 → 사용자 명시 지시
("포스 푸쉬해줘") 후 `git push --force origin main`
(`+ 005d2b54...59a15109 main -> main (forced update)`).

백업 tag/branch는 로컬에만 존재.

## Verification

- 라이브: `curl -I https://aikorea24.kr` 200.
- 블로그 6건 배포 확인.
- 파이프라인 수동 실행: 뉴스 6건 선택 → 브리핑 + 이메일 + 배포, 에러 0.
- 브라우저(Aside) 확인: 7개 페이지 유형 (홈/블로그 목록/본문 2건/브리핑
  목록+본문/뉴스/도구/용어사전) 전부 200 + 한국어 정상.
- 영어 누수: 신규 블로그 6건 본문 영어 문장 0 (제품명·URL만), 브리핑 본문
  한국어 (출처 라벨만 영문).
- 강제 푸시 로그: `logs/destructive_2026-09-17.log`
  `GIT_FORCE_PUSH origin main | 사전=remote 005d2b54(46 commits post-0905) | 백업=tag pre-restore-20260917_141848+branch | 사후=59a15109 | 사용자명령=explicit`

## 잔존 위험

- **백업 tag/branch가 로컬에만 존재** — 원격에는 09-05 이후 46 커밋이 남아
  있지 않음. 다른 머신에서 복구하려면 로컬 백업에 의존해야 함.
- D1 데이터 및 launchd 스케줄러는 git 범위 밖이라 복원 대상 아님
  (별도 확인 필요).
- 브리핑 아카이브에 09-17 삼중 엔트리 (수동 파이프라인 3회 실행 → D1 중복 행).
- `blog_draft_generator`가 `scripts/scripts/` 중복 경로에 kicker7 초안을
  떨어뜨리는 기존 버그 (미수정, 미추적 상태로 잔류).
