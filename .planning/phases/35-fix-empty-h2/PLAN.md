# Phase 35 Plan: 전체 포스트 빈 H2 감사 및 일괄 수정

## Phase Goal
restructure_posts.py(Phase 34) 적용으로 발생한 **빈 H2(내용 없는 H2 헤딩)** 문제를 820개 전체 블로그 포스트에서 감지하고 일괄 수정한다.

## Root Cause (from RESEARCH.md)
**가설 A 확정**: `restructure_posts.py`가 첫 H2 직후 첫 단락을 도입단락으로 추출하여 H2 **앞**으로 이동시키면서, 원래 첫 H2를 빈 H2로 남겨둔 버그.

---

## Task Breakdown

### Task 1: 빈 H2 감지 스크립트 작성 (20분)
**파일:** `scripts/detect_empty_h2.py`

**Acceptance Criteria:**
- [ ] `src/content/blog/*.md` 전체 순회 (glob)
- [ ] Frontmatter 이후 본문만 대상
- [ ] Pattern 1 감지: `## H2\n\n## H2` (공백 라인만)
- [ ] Pattern 2 감지: `## H2\n## H2` (공백 라인 없음)
- [ ] Pattern 3 감지: H2 다음 일반 텍스트 단락 없이 이미지/인용/코드블록만 있음
- [ ] 각 감지 시: 파일명, 빈 H2 텍스트, 다음 H2 텍스트, 주변 5라인 컨텍스트 출력
- [ ] Pattern 3은 "비-텍스트 콘텐츠 H2"로 별도 분류
- [ ] 총 감지 건수, 패턴별 건수 출력

**Output:** `.planning/phases/35-fix-empty-h2/AUDIT.md`

---

### Task 2: 감지 스크립트 실행 및 감사 문서화 (10분)
**명령:** `python3 scripts/detect_empty_h2.py > .planning/phases/35-fix-empty-h2/AUDIT.md`

**Acceptance Criteria:**
- [ ] AUDIT.md에 총 감지 건수 기록
- [ ] Pattern 1/2/3 각각 건수 기록
- [ ] 감지된 파일 목록 (파일명 + 빈 H2 + 다음 H2) 기록
- [ ] 코그니션 포스트(009) 감지 목록 포함 확인

**Verification:** `grep "009" AUDIT.md` → 결과 있어야 함

---

### Task 3: 빈 H2 수정 스크립트 작성 (20분)
**파일:** `scripts/fix_empty_h2.py`

**Acceptance Criteria:**
- [ ] Pattern 1, 2 대상: 빈 H2 라인 삭제 (라인 단위)
- [ ] Pattern 3: 리포트만 출력, 자동 수정하지 않음
- [ ] `--dry-run` 모드: 변경 사항 미리보기 (파일명, 수정 전/후 라인)
- [ ] `--apply` 모드: 실제 적용
- [ ] `rebuild_frontmatter()` 재사용으로 YAML 보존
- [ ] 각 수정 사항 로그 출력 (파일명, 빈 H2 텍스트, 액션)
- [ ] 수정 후 YAML 파싱 검증 (yaml.safe_load 성공)

**Algorithm:**
```
for each detected empty_h2 (Pattern 1, 2):
    read file lines
    delete empty_h2 line
    normalize surrounding blank lines (max 1 consecutive)
    write file
```

---

### Task 4: 수정 스크립트 시험 적용 (10분)
**대상:** 코그니션 포스트(009) - `2026-07-25-009-코그니션의-포크-인수-ai-개성이-경쟁-우위가-된-이유를-분석합니다.md`

**Steps:**
1. `python3 scripts/fix_empty_h2.py --dry-run --file 009파일명`
2. 출력 확인: 빈 H2 "기업의 배경..." 삭제 예정인지 확인
3. `python3 scripts/fix_empty_h2.py --apply --file 009파일명`
4. `cat`으로 결과 확인

**Expected Result:**
```
---
(frontmatter)
---

최근 AI 업계에서는 코그니션이 포크를 인수한 이유에 대한 분석이...

## 코그니션이 포크를 인수한 이유는 무엇일까요?

코그니션은 AI 기반 코딩 어시스턴트인 데빈을 개발한 스타트업입니다...
```

**Acceptance Criteria:**
- [ ] 빈 H2 "기업의 배경..." 제거됨
- [ ] 첫 H2가 "코그니션이 포크를 인수한 이유는..." 됨
- [ ] 도입단락 구조 유지됨
- [ ] YAML 파싱 오류 없음

---

### Task 5: 전체 820개 포스트 적용 (15분)
**명령:** `python3 scripts/fix_empty_h2.py --apply`

**Acceptance Criteria:**
- [ ] 전체 파일 처리 완료
- [ ] 재실행: `python3 scripts/detect_empty_h2.py` → **0건 감지** (Pattern 1, 2)
- [ ] Pattern 3(비텍스트 H2)만 남을 수 있음 → 별도 리포트
- [ ] YAML 파싱 오류 0건 (스크립트 출력에 "YAML 파싱 오류: 0건" 확인)

---

### Task 6: 빌드 및 배포 (5분)
**Commands:**
```
npm run build
env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler pages deploy dist --project-name aikorea24 --branch main --commit-dirty=true
```

**Acceptance Criteria:**
- [ ] `npm run build` 성공 (빌드 로그에 "Build completed" 확인)
- [ ] `wrangler pages deploy` 성공 (배포 URL 출력 확인)
- [ ] 배포 URL 기록: `https://aikorea24.kr` 또는 preview URL

---

### Task 7: 외부 검증용 증거 수집 (10분)
**대상 URL 4개:**
1. 코그니션 포스트(009) - 메인 검증
2. 알파폴드 포스트(011) - 회귀 확인
3. AUDIT.md에서 추가 감지된 포스트 2개 샘플

**검증 명령 (각 URL당):**
```bash
curl -s "https://aikorea24.kr/blog/슬러그/" | grep -A 200 "article\|main" | head -500
```

**Acceptance Criteria:**
- [ ] **코그니션(009)**: 본문 첫 1000자 인용, "## 기업의 배경" H2 **부재** 확인, 첫 H2가 "## 코그니션이 포크를 인수한 이유..." 확인
- [ ] **알파폴드(011)**: 본문 첫 500자 인용, 구조 유지 확인 (회귀 없음)
- [ ] **샘플 2개**: 빈 H2 수정 확인
- [ ] 모든 검증 텍스트를 보고서에 직접 인용

---

## Dependencies

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7
   │       │       │       │       │       │       │
   ▼       ▼       ▼       ▼       ▼       ▼       ▼
 AUDIT   AUDIT  fix.py  dry-run  apply   build   curl
 .md     .md             run     all     deploy  verify
```

---

## Verification Checkpoints

| Checkpoint | Method | Evidence Required |
|------------|--------|-------------------|
| Detection complete | Script output | AUDIT.md with counts |
| Cognition post detected | grep | `grep "009" AUDIT.md` |
| Fix dry-run correct | Script output | Preview shows correct H2 removal |
| Fix applied to 009 | `cat` file | Empty H2 gone, correct first H2 |
| Re-detection = 0 | Script output | "총 감지 건수: 0" |
| YAML valid | Script output | "YAML 파싱 오류: 0건" |
| Build success | `npm run build` log | "Build completed" |
| Deploy success | wrangler output | Deploy URL |
| Live verification | `curl` output | Rendered text quotes |

---

## Risk Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-deletion breaks structure | Medium | High | Pattern 3 excluded from auto-fix; manual review |
| YAML corruption | Low | High | Reuse `rebuild_frontmatter()`, validate after each file |
| restructure_posts.py re-run overwrites | High | High | Document execution order: fix_empty_h2.py runs LAST |
| Deploy failure | Low | Medium | Use `env -u CLOUDFLARE_API_TOKEN` for wrangler |
| False positive detection | Low | Medium | Conservative patterns, context review in AUDIT.md |

---

## Success Criteria (인수 기준)

All must be TRUE with evidence:

1. ✅ `ROOT_CAUSE.md` 작성: 가설 A 확정, 버그 메커니즘 문서화
2. ✅ `detect_empty_h2.py`로 820개 전체 감사 실행
3. ✅ `AUDIT.md`에 감지 건수, 파일 목록, 패턴별 분류 문서화
4. ✅ 코그니션 포스트(009) 감지 목록 포함 확인 (`grep` 증거)
5. ✅ `fix_empty_h2.py` 수정 후 재감사 시 Pattern 1,2 = 0건
6. ✅ YAML 파싱 오류 0건 (스크립트 출력 인용)
7. ✅ `npm run build` 성공 (빌드 로그 인용)
8. ✅ 배포 URL 명시
9. ✅ 코그니션(009) 실서비스 본문 첫 1000자 인용 + 빈 H2 부재 + 올바른 첫 H2 확인
10. ✅ 알파폴드(011) 실서비스 본문 첫 500자 인용 + 회귀 없음 확인
11. ✅ 추가 감지 포스트 2-3개 샘플 실서비스 검증 인용

---

## Files to Create/Modify

### New Files:
- `scripts/detect_empty_h2.py`
- `scripts/fix_empty_h2.py`
- `.planning/phases/35-fix-empty-h2/AUDIT.md` (generated)
- `.planning/phases/35-fix-empty-h2/ROOT_CAUSE.md` (copy from RESEARCH.md)

### Modified Files:
- 820 blog posts in `src/content/blog/*.md` (via fix_empty_h2.py --apply)

### Reference (read-only):
- `scripts/restructure_posts.py` (for understanding bug)
- `scripts/validate_blog_posts.py` (for YAML validation pattern)