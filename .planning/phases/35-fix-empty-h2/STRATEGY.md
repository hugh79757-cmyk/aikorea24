# Phase 35: 수정 전략 선택 및 근거

## 원본 구조 분석 결과 (Task 1 완료)

### 분석 대상: 5개 포스트 (git commit 779b8b7 기준)

| 포스트 | 파일명 | 원본 구조 |
|--------|--------|-----------|
| 1 | 2026-07-21-001 (CVPR 자율주행) | (a) frontmatter → H2 → 본문 |
| 2 | 2026-07-22-002 (연준 앤트로픽) | (a) frontmatter → H2 → 본문 |
| 3 | 2026-07-22-009 (일본 AI 붐) | (a) frontmatter → H2 → 본문 |
| 4 | 2026-07-25-009 (코그니션 포크) | (a) frontmatter → H2 → 본문 |
| 5 | 2026-07-25-011 (알파폴드) | (a) frontmatter → H2 → 본문 |

### 비율 집계
- **구조 (a): 5/5 (100%)** — frontmatter 다음에 바로 첫 H2가 오고, 그 직후에 본문 단락이 있는 구조
- **구조 (b): 0/5 (0%)** — frontmatter 다음에 도입단락(일반 단락)이 있고 그 다음 H2가 오는 구조

---

## 전략 선택

### ✅ 선택: 전략 X (첫 H2 제거 + 첫 단락 도입단락화)

**선택 근거:**
1. **원본 구조 (a)가 100%** — 모든 분석 대상 포스트가 frontmatter 직후 첫 H2로 시작함
2. **버그 메커니즘 일치** — `restructure_posts.py`가 첫 H2 직후 첫 단락을 추출해 H2 **앞**으로 이동시키면서, 첫 H2를 빈 껍데기로 남김
3. **Strategy X가 정답** — 빈 H2를 제거하면 두 번째 H2가 새로운 첫 H2가 되어 구조가 자연스러워짐
4. **Strategy Z 불필요** — 구조 (b) 케이스가 0건이므로 "하이브리드" 접근의 복잡성만 추가됨

### ❌ 배제: 전략 Y (첫 단락 복제 + 첫 H2 유지)
- **이유**: 원래 문제 3(도입단락과 첫 H2 본문 첫 단락이 똑같이 나옴)을 재발시킴
- Phase 33에서 이미 이 문제로 인해 수정했음

### ⚠️ 배제: 전략 Z (하이브리드: 기존 도입단락 있으면 사용, 없으면 전략 X)
- **이유**: 구조 (b) 케이스가 0건이라 불필요한 복잡성만 증가

---

## 수정 알고리즘 (전략 X 적용)

### restructure_posts.py 수정 지점: `process_file()` 함수

**현재 버그 로직 (lines 350-369):**
```python
# H2 위치 재계산 후 도입단락을 H2 앞에 삽입
new_h2_pos = find_first_h2(new_body)
before_h2 = new_body[:new_h2_start].rstrip('\n')
after_h2 = new_body[new_h2_start:]

if before_h2.strip():
    new_body = before_h2 + '\n\n' + intro_paragraph + '\n\n' + after_h2
else:
    new_body = intro_paragraph + '\n\n' + after_h2
```

**수정 후 로직 (전략 X):**
```python
# H2 위치 재계산
new_h2_pos = find_first_h2(new_body)
if not new_h2_pos:
    return {'file': filename, 'status': 'error', 'reason': 'H2 헤딩 손실'}

new_h2_start, new_h2_end = new_h2_pos

# 핵심 수정: 첫 H2가 빈 H2인지 확인 (본문 내용 없음)
# 빈 H2라면 → 첫 H2 라인 자체를 제거하고, 도입단락을 그 위치에 배치
h2_text = new_body[new_h2_start:new_h2_end].strip()

# H2 직후 다음 H2 또는 본문 끝까지의 내용 확인
after_h2 = new_body[new_h2_end:].lstrip('\n')
next_h2_pos = find_first_h2(after_h2)  # 다음 H2 찾기

if next_h2_pos:
    # 다음 H2 전까지의 내용이 실질적 텍스트인지 확인
    content_between = after_h2[:next_h2_pos[0]].strip()
    is_empty_h2 = not content_between or len(content_between) < 10
else:
    # 마지막 H2인 경우
    is_empty_h2 = not after_h2.strip() or len(after_h2.strip()) < 10

if is_empty_h2:
    # 전략 X: 빈 H2 제거, 도입단락을 그 자리에 배치
    before_h2 = new_body[:new_h2_start].rstrip('\n')
    after_empty_h2 = new_body[new_h2_end:].lstrip('\n')
    
    if before_h2.strip():
        new_body = before_h2 + '\n\n' + intro_paragraph + '\n\n' + after_empty_h2
    else:
        new_body = intro_paragraph + '\n\n' + after_empty_h2
else:
    # 빈 H2가 아니면 기존 로직 유지 (도입단락 H2 앞 삽입)
    before_h2 = new_body[:new_h2_start].rstrip('\n')
    after_h2 = new_body[new_h2_start:]
    
    if before_h2.strip():
        new_body = before_h2 + '\n\n' + intro_paragraph + '\n\n' + after_h2
    else:
        new_body = intro_paragraph + '\n\n' + after_h2
```

---

## 예상 결과 (코그니션 포스트 009 기준)

### 수정 전 (현재 버그 상태):
```markdown
---
title: 코그니션의 포크 인수...
description: '기업의 배경: 코그니션과 포크는 어떤 곳인가요'
---
최근 AI 업계에서는 코그니션이 포크를 인수한 이유에 대한 분석이...

## 기업의 배경: 코그니션과 포크는 어떤 곳인가요?  ← 빈 H2!

## 코그니션이 포크를 인수한 이유는 무엇일까요?
코그니션은 AI 기반 코딩 어시스턴트인 데빈을 개발한 스타트업입니다...
```

### 수정 후 (전략 X 적용):
```markdown
---
title: 코그니션의 포크 인수...
description: 최근 AI 업계에서는 코그니션이 포크를 인수한 이유에 대한 분석이...
---
최근 AI 업계에서는 코그니션이 포크를 인수한 이유에 대한 분석이...

## 코그니션이 포크를 인수한 이유는 무엇일까요?
코그니션은 AI 기반 코딩 어시스턴트인 데빈을 개발한 스타트업입니다...
```

---

## 검증 계획

1. **dry-run**으로 009 포스트 테스트 → 빈 H2 "기업의 배경..." 제거 확인
2. **cat**으로 .md 파일 직접 확인 → 첫 H2가 "코그니션이 포크를..." 인지 확인
3. **detect_empty_h2.py** 재실행 → Pattern 1, 2가 0건인지 확인