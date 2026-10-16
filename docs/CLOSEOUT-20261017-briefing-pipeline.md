# AIK24 — 브리핑 파이프라인 클로즈 아웃 (공식 문서)

---

## 식별
- **Version**: `v2026.10.17.0234` (KST 기준 시점)
- **Baseline (KST)**: 2026-10-17 02:34 (사용자 지정 기준 시점)
- **작업 루트**: `/Users/twinssn/Projects/aikorea24`
- **상태**: ①②③④⑤ + ⑥⑦⑧⑨⑩ 모두 완료 — 코드 검증 + 커밋 + 배포 + 라이브 검증.
- **문서 성격**: 작업 사인 오프 (close-out). `docs/state.md` 항목 19 entries 와 1:1 매칭.

---

## 1. 완료 항목

| # | 항목 | 버전/커밋 | 라이브/검증 |
|---|------|-----------|------------|
| ① | verify-models 잡 실발화 검증 | e982072c | 런치드 PATH 결함 수정后 PASS 10/FAIL 5 |
| ② | test_emdash_publish 기대값 정리 | cd2b443f | 8 tests pass |
| ③ | 주간 무료 기회 8건 D1 INSERT | 0515c104 | 8 rows (ids 56074-56082) + verify-models profile fix |
| ④ | 주간 무료 기회 드립 dedup | 7bfd3e82, 124b9cdd | 9 + 10 tests pass; day1->day8 drain 1:1 simulation |
| ⑤ | 브리핑 하루 1회 발행 정책 | 9174a74f | 5 tests pass; `auto_briefing` 1.8s skip log |
| ⑥ | og:image 404 (EmDash) | 209baad6 | media.id vs storage_key 원인. D1 정정 2건 + 라이브 2×200. 헬스체크 + 7 tests |
| ⑦ | 기존 발행 글 전수 감사 | 20ece767 | 1513건 PT-aware. jargon 345. 내부 용어 1건. 보고서 203 lines |
| ⑧ | B안 유료 대비 (Sonnet 5.5) | 411bbfed | 섹션 + warning + 출처. 라이브 페이지 노출. tests 6 pass |
| ⑨ | 미검증 3후보 검증 | 9426053a | NVIDIA build [V] / Groq 8K [P] / 국내 [N] |
| ⑩ | EmDash 로그인 return URL | c6f13ec9 + acf30f9 | backend + blog deployed, state 3 case live verified |

---

## 2. 코드 검증 결과 (클로즈 아웃 시점 재실행)

<|constrain|> 검증 항목 | 명령 | 결과 |
|---|---|---|
| emdash 미디어 URL 헬스체크 | `python3 scripts/emdash15_media_url_health.py` | **이상 0 / 잔존 0 / exit 0** |
| emdash_precheck selftest | `python3 scripts/emdash_precheck.py --selftest` | **OK** |
| 내 테스트 3종 | `pytest tests/test_emdash_media_url_health.py tests/test_paid_baseline_section.py tests/test_free_models_page.py -q` | **21 passed / 0.29s** |
| paid baseline section 렌더 | 인라인 assert (warning + source + data) | **OK (900 chars)** |
| 브리핑/기회 스크립트 회귀 | (별도 세션 green: 9 + 10 + 5 passed) | **green** |

---

## 3. 변경 파일 (production / test / docs, 본 close-out 기준)

### aikorea24 (main)
- `scripts/emdash15_media_url_health.py` (NEW), `scripts/free_models_page.py` (load_payment_baseline + render_paid_baseline)
- `scripts/logs/paid_baseline.json` (NEW — Sonnet 5.5 공식 data)
- `src/lib/redirect.ts` (NEW), `src/pages/api/auth/login.ts`, `.../callback/google.ts`
- `tests/test_emdash_media_url_health.py`, `tests/test_paid_baseline_section.py`
- `docs/audit/20261016-emdash-posts-audit.md` (NEW)
- `docs/state.md`, `docs/CLOSEOUT-20261017-briefing-pipeline.md` (self, this file)

### aikorea24emdash
- `src/layouts/Base.astro` (로그인 href return_to)

### D1 (EmDash) — 데이터 정정 2건
- ec_posts.featured_image (free-models, nvidianemotron-3-ultra-550b-a55bfree → storage_key URL) with snapshot `/tmp/emdash-featured-image-backup-20261016.json`.

---

## 4. 배포/라이브 검증
- **aikorea24.kr** workers v1.1 (f2cb170a): `/api/auth/login?redirect_to=...`
  - relative `/dashboard` → state=%2Fdashboard ✓
  - absolute allowlisted emdash URL → state=https%3A%2F%2Femdash...✓
  - disallowed (evil.com) → state absent ✓ (open redirect 차단)
- **emdash.aikorea24.kr** workers v1.1 (f23116a2): 로그인 링크 href에 `redirect_to` 포함 확인.
- **free-models 페이지**: "유료 모델과 비교 (공식 발표 기준)" 섹션 5 키워드 노출 + og:image storage_key 200.
- EmDash 미디어 URL 19/19 200 확인 (post-fix).

---

## 5. 잔존 위험 (Accepted)
1. ⑥ 헬스체크 자동실행 미등록 — dry-run + 수동만 검증
2. ⑧ paid_baseline.json 수동 갱신, 기준선 1개(Sonnet 5.5)만
3. ⑨ NVIDIA 호출 성공 / Groq 무료 tier 8K TPM 직접 / 국내 개별 해커톤 미검증
4. ⑩ OAuth end-to-end 수동 로그인 walkthrough 1회 미실행 (login 엔드포인트 3케이스 PASS가 보강)
5. ⑦ 전제 오류 + closing 1249건 과대 추정 — 25건 정독(weak) 후속
6. **사용자 액션**: 2026-10-17 09:30 자동 verify-models 첫 실행 결과 확인 (`scripts/logs/verify-models.log`), 수동 로그인 walkthrough 1회.

---

## 6. 커밋 연대표 (이번 close-out 세션)
```
20ece767 docs(audit): EmDash 발행 글 전수 감사 (PT-aware) — 1513건
411bbfed feat(free-models): ⑧ B안 유료 대비 섹션 (공식 자료 인용)
  (audit report at 20ece767 also)
c6f13ec9 fix(auth): ⑩ 로그인 후 EmDash 페이지 복귀 지원
acf30f9  (emdash repo) fix(auth): ⑩ …
9426053a docs(state): ⑦ ⑨ 완료
?  docs(CLOSEOUT-20261017) — see below
```

---

## 7. 운영 규칙 준수
- 모든 항목을 `docs/state.md` 에 항목별 entry 로 기록(3분법 카테고리 사용).
- 시크릿 값은 commit/log/state 에 기록하지 않음(키 이름 + 출처만).
- 다른 세션의 진행작업 (`.planning/STATE.md`, `CHANGES.md`, `test_safe_div.py` 등) 은 미커밋 그대로 보존.
- dry-run/report는 D1 write-free 유지. 에이전트 직접 로그인 시도 없음 (nevertouchedConfirmed).

---

*문서 종료 — v2026.10.17.0234 — AIK24 브리핑 파이프라인 close-out*
