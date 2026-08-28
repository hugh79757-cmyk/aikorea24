# Weekly Contrast Deep Dive — 운영 가이드

> 최종 갱신: 2026-08-28
> 파이프라인: `scripts/run_weekly_contrast.py`
> 스케줄: 매주 토요일 09:00 (launchd: `kr.aikorea24.weekly-contrast`)

---

## 아키텍처 요약

```
S0 (D1 수집) → S1 (LLM 클러스터링) → S2 (LLM 심층분석) → S3 (블로그 발행)
   93건            50건 분석              3건 작성             추천→blog/
                                                            보류→_drafts/
                                                            폐기→skip
```

- LLM: gemini-3.1-flash-lite (무료 체인)
- DB: Cloudflare D1 (briefing_items JOIN news JOIN briefings)
- 임베딩: OpenAI text-embedding-3-small (description 신뢰도 검증)

---

## 1. 토요일 첫 실행 모니터링

### 로깅 상태: ✅ 완비

`run_weekly_contrast.py`는 다음을 기록한다:

| 항목 | 기록 위치 | 형식 |
|------|----------|------|
| 시작/종료 시각 | `logs/weekly_contrast.log` | `=== S0/S1/S2/S3: ... ===` |
| 단계별 결과 | `logs/weekly_contrast.log` | `S0: 93 articles collected` |
| 에러 | `logs/weekly_contrast.log` | `S0_failed: ...`, `S1_failed: ...` |
| 품질 판단 | `logs/weekly_contrast.log` | `deep_dive_written: ... [quality: 추천/보류/폐기]` |
| 실행 시간 | `logs/weekly_contrast.log` | `=== Pipeline complete: 102.0s ===` |
| 결과 JSON | `tmp_test/weekly_contrast_result.json` | 전체 구조체 |

### 알림 경로: ⚠️ 로그 파일 확인 (1주차)

기존 `run_pipeline_with_notify.py`는 텔레그램 알림 사용 (`pipeline/infra/telegram.py`).
weekly-contrast 파이프라인에는 텔레그램 알림 미적용.

**1주차 대안**: 수동 로그 확인. 2주차부터 텔레그램 알림 추가 검토.

---

## 2. 월요일 아침 확인 체크리스트

```bash
# 1. launchd 등록 및 종료코드 확인
launchctl list | grep weekly-contrast
# 기대: '-  0  kr.aikorea24.weekly-contrast' (exit 0 = 성공)
# 실패 시: exit 코드가 0이 아님 → 로그 확인 필요

# 2. 실행 로그 확인
tail -50 /Users/twinssn/Projects/aikorea24/logs/weekly_contrast.log
# 기대: '=== Pipeline complete: xxx.xs ===' 로 끝남
# 에러 시: 'S0_failed', 'S1_failed', 'S2_failed' 검색

# 3. 실행 에러 빠른 검색
grep -E '(ERROR|FAILED|failed|exception)' /Users/twinssn/Projects/aikorea24/logs/weekly_contrast.log | tail -10

# 4. 결과 JSON 확인
cat /Users/twinssn/Projects/aikorea24/tmp_test/weekly_contrast_result.json | python3 -m json.tool
# 확인: s0_articles, s1_candidates, s2_dives, s3_posts, errors

# 5. 발행된 블로그 포스트 확인
ls -lt /Users/twinssn/Projects/aikorea24/src/content/blog/weekly-contrast-*.md 2>/dev/null | head -5
# 기대: 추천 기사가 여기에 발행됨

# 6. 보류 파일 확인 (사람 검토 대기)
ls -lt /Users/twinssn/Projects/aikorea24/src/content/blog/_drafts/weekly-contrast-*.md 2>/dev/null | head -5
# 기대: 추론 only 기사가 여기에 저장됨

# 7. 품질 판단 요약 (결과 JSON에서)
cat /Users/twinssn/Projects/aikorea24/tmp_test/weekly_contrast_result.json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"  {q['verdict']}: {q['title']}\") for q in d.get('s2_quality',[])]"

# 8. 로그 파일 크기 확인 (비정상 크기 경고)
ls -lh /Users/twinssn/Projects/aikorea24/logs/weekly_contrast.log
# 정상: 수 KB~수십 KB. 수 MB 이상이면 반복 에러 의심
```

---

## 3. 4주 관측 지표

4주 운영 후 회고 시 아래 지표를 추출한다.

### 주간 집계 (매주 월요일 기록)

| 지표 | 수집 방법 | 정상 범위 |
|------|----------|----------|
| S0 수집 기사 수 | `result.s0_articles` | 60~120건 |
| S1 대비 후보 수 | `result.s1_candidates` | 3~8건 |
| S2 작성 수 | `result.s2_dives` | 2~3건 |
| 추천 수 | `s2_quality[*].verdict == "추천"` | 1~2건 |
| 보류 수 | `s2_quality[*].verdict == "보류"` | 0~2건 |
| 폐기 수 | `s2_quality[*].verdict == "폐기"` | 0~2건 |
| 실행 시간 | `result.elapsed_seconds` | 60~180초 |

### 4주 누적 지표

| 지표 | 설명 | 목표 |
|------|------|------|
| 발행 스킵 주수 | 추천 0건인 주 수 | ≤ 1/4주 |
| 환각 인용 폐기 사례 | 누적 폐기 목록 (제목+사유) | 추세 감소 |
| 총 발행 포스트 수 | 4주간 추천 발행 합계 | ≥ 4건 |
| 보류→검토 완료율 | 사람이 보류를 검토한 비율 | 추후 측정 |
| 평균 실행 시간 | 4주 평균 | < 120초 |
| LLM 체인 실패율 | 무료 체인 실패 → DeepSeek 폴백 비율 | < 20% |

### 기록 템플릿 (매주 월요일)

```markdown
## Weekly Contrast — YYYY-MM-DD 실행 결과

- 수집: X건 → 대비 후보: Y건 → 작성: Z건
- 추천: A건 | 보류: B건 | 폐기: C건
- 실행 시간: X초
- 특이사항: (없음 / 특정 이슈)
```

### 환각 인용 사례 기록 ( 누적 )

| 주 | 제목 | 환각 인용 내용 | 원문 불일치 사유 |
|----|------|---------------|----------------|
| (첫 실행 후 기록) | | | |

---

## 트러블슈팅

### 문제: launchd가 실행 안 됨
```bash
# plist 문법 검증
plutil -lint ~/Library/LaunchAgents/kr.aikorea24.weekly-contrast.plist

# 강제 실행 (디버깅)
cd /Users/twinssn/Projects/aikorea24 && .venv/bin/python3 scripts/run_weekly_contrast.py --dry-run
```

### 문제: D1 쿼리 실패
- 원인: Cloudflare API 토큰 문제
- 확인: `env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --command "SELECT count(*) FROM news"`

### 문제: LLM 체인 전체 실패
- 원인: 무료 티어 quota 소진
- 확인: `logs/weekly_contrast.log`에서 `quota_cooldown` 검색
- 대응: 자동으로 DeepSeek(v4-flash, 유료) 폴백

### 문제: 추천 0건 반복
- 원인: 환각 필터가 너무 엄격하거나 대비 쌍 부족
- 대응: S1 max_articles 상향 검토, S2 품질 기준 완화 검토
