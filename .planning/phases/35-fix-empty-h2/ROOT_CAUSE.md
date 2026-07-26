# Phase 35 Research: 빈 H2 원인 분석 및 수정 전략

## Root Cause Analysis: 가설 A 확정 (restructure_posts.py 버그)

### 검증된 사실 (Git History 근거)

**원본 상태 (commit 779b8b7):**
```
## 코그니션이 포크를 인수한 이유는 무엇일까요?
최근 AI 업계에서는... (첫 단락 - 본문 시작)

## 기업의 배경: 코그니션과 포크는 어떤 곳인가요?
코그니션은 AI 기반... (두 번째 H2의 첫 단락)
```

**restructure_posts.py 적용 후 (현재 파일):**
```
description: "기업의 배경: 코그니션과 포크는 어떤 곳인가요"  ← 첫 H2 제목이 description이 됨!

최근 AI 업계에서는... (도입단락 - 첫 H2의 첫 단락이 여기로 이동)

## 기업의 배경: 코그니션과 포크는 어떤 곳인가요?  ← 빈 H2! (본문이 도입단락으로 이동됨)

## 코그니션이 포크를 인수한 이유는 무엇일까요?
코그니션은 AI 기반... (원래 두 번째 H2의 내용이 여기로)
```

### 버그 메커니즘 (restructure_posts.py 분석)

`process_file()` 함수 흐름:
1. `find_first_h2(body)` → 첫 번째 H2 찾음 ("기업의 배경...")
2. `extract_first_paragraph_after_h2(body, h2_end)` → **첫 H2 직후 첫 단락 추출** ("코그니션은 AI 기반...")
3. `remove_meta_intro()` → 메타 도입문 제거 시도
4. `new_body = body[:intro_start] + body[intro_end:]` → **본문에서 해당 단락 제거**
5. `find_first_h2(new_body)` → H2 위치 재계산 (이제 첫 H2가 빈 상태)
6. `before_h2 = new_body[:new_h2_start]` → H2 이전 부분
7. `new_body = before_h2 + '\n\n' + intro_paragraph + '\n\n' + after_h2` → **도입단락을 H2 앞에 삽입**

**결과:** 첫 H2("기업의 배경...") 아래 본문이 사라지고, 도입단락이 H2 **앞**으로 이동 → 빈 H2 생성

### 가설 B, C 배제 근거

- **가설 B (원본에 빈 H2 존재):** Git history로 원본에 첫 H2 아래 본문 있었음 확인
- **가설 C (이미지/인용 등 비텍스트 요소):** 원본 첫 H2 직후 일반 텍스트 단락이었음 확인

---

## Detection Algorithm: 3가지 빈 H2 패턴

### Pattern 1: 연속 H2 (공백 라인만 있음)
```
## Heading A

## Heading B
```
- H2 라인 다음에 `\n\n`만 있고 다음 H2가 나오는 경우

### Pattern 2: 연속 H2 (공백 라인 없음)
```
## Heading A
## Heading B
```
- H2 라인 바로 다음에 다음 H2가 오는 경우

### Pattern 3: H2 다음에 비텍스트 요소만 있음
```
## Heading A
![image](...)

## Heading B
```
또는
```
## Heading A
> 인용문

## Heading B
```
- H2 다음에 일반 텍스트 단락(한글/영문/숫자)이 없고 이미지/인용/코드블록만 있는 경우
- 분류: "비-텍스트 콘텐츠 H2"로 별도 카테고리

---

## Fix Strategy: 전략 1 (가설 A 해당)

### 수정 원칙
빈 H2를 **제거**하고, 다음 H2를 유지. 원래 첫 H2의 본문이 도입단락으로 이동되었으므로, 빈 H2는 더 이상 의미 없음.

### 알고리즘
1. `detect_empty_h2.py`로 전체 820개 포스트 감사
2. 각 빈 H2 케이스에 대해:
   - 빈 H2 텍스트 기록
   - 다음 H2 텍스트 기록
   - 빈 H2 라인 삭제 (라인 단위)
   - 주변 불필요한 공백 정규화 (최대 1개 빈 줄)
3. YAML frontmatter 보존 (기존 `rebuild_frontmatter()` 재사용)
4. `--dry-run` / `--apply` 모드 지원

### Edge Cases 처리
- **파일 첫 H2가 빈 경우:** 첫 H2 제거, 두 번째 H2가 첫 H2가 됨
- **연속 3개 이상 빈 H2:** 모두 제거, 첫 번째 비어있지 않은 H2 유지
- **마지막 H2가 빈 경우:** 제거 (다음 H2 없음)

---

## Risk Assessment

| 위험도 | 항목 | 완화 방안 |
|--------|------|-----------|
| High | 과도한 H2 제거로 구조 손상 | Pattern 3(비텍스트 H2)은 별도 분류하여 수동 검토 후 처리 |
| Medium | YAML 파싱 오류 | `rebuild_frontmatter()` 재사용, 적용 후 `validate_blog_posts.py` 실행 |
| Low | 이미 수정된 파일 재수정 | 감지 스크립트로 현황 확인 후 수정 적용 |
| High | `restructure_posts.py` 재실행 시 덮어쓰기 | 실행 순서 문서화: fix_empty_h2.py **최종 단계**에서 실행 |

---

## Implementation Plan

### Task 1: detect_empty_h2.py (20분)
- Pattern 1, 2, 3 감지 로직 구현
- 출력: 파일명, 빈 H2 텍스트, 다음 H2 텍스트, 컨텍스트 5라인
- 결과 AUDIT.md 저장

### Task 2: 감사 실행 및 문서화 (10분)
- `python3 scripts/detect_empty_h2.py > AUDIT.md`
- 코그니션 포스트(009) 포함 확인

### Task 3: fix_empty_h2.py (20분)
- Pattern 1, 2 대상 자동 수정 (빈 H2 라인 삭제)
- Pattern 3은 리포트만, 수동 처리
- `--dry-run` / `--apply` 모드

### Task 4: 시험 적용 (10분)
- 009 포스트 dry-run → apply → 검증

### Task 5: 전체 적용 (15분)
- 820개 전체 apply → 재감사로 0건 확인

### Task 6: 빌드/배포 (5분)
- `npm run build` → `wrangler pages deploy`

### Task 7: 외부 검증 (10분)
- 실서비스 렌더링 확인 (curl + 텍스트 인용)

---

## Success Criteria

1. ✅ `ROOT_CAUSE.md` 작성: 가설 A 확정, 버그 메커니즘 문서화
2. ✅ `detect_empty_h2.py`로 820개 전체 감사 실행
3. ✅ `AUDIT.md`에 감지 건수, 파일 목록, 패턴별 분류 문서화
4. ✅ 코그니션 포스트(009) 감지 목록 포함 확인
5. ✅ `fix_empty_h2.py` 수정 후 재감사 0건
6. ✅ YAML 파싱 오류 0건 (스크립트 출력 증거)
7. ✅ `npm run build` 성공 (빌드 로그)
8. ✅ 배포 URL 명시
9. ✅ 실서비스 본문 인용: 빈 H2 부재, 첫 H2가 올바른 것 확인
10. ✅ 알파폴드(011) 회귀 없음 확인
11. ✅ 추가 감지 포스트 2-3개 샘플 검증