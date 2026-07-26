# Phase 36 Plan: 품질 검증 3종 및 SEO Description 개선 방향 수립

> Phase 35에서 빈 H2 문제(218건) 자동 수정 완료 → Phase 36은 **외부 검증에서 발견된 추가 이슈 3건을 전수 조사·수정·분석**하는 단계

---

## Phase Goal

1. **도입단락의 `* * *` / `---` 수평선 전수 조사 및 수정**
2. **meta description 추출 일관성 감사**
3. **메타 도입문 3차 확장 패턴 감지 및 수정**
4. **SEO description 품질 분석 및 개선 방향 정립**

---

## 규칙 요약 (보고/수정/검증)

- "확인됨" 표현을 사용하지 않고 `cat`/`curl` 출력을 직접 인용한다
- 증거와 산출이 빠진 보고를 허용하지 않는다
- 기존 스크립트의 책임 범위를 변경하지 않고, Phase 36의 신규/확장 코드는 `scripts/` 아래에 독립 파일로 둔다

---

## Task Breakdown

---

### Task 1 — `scripts/detect_horizontal_rule_intro.py` + `scripts/fix_horizontal_rule_intro.py`

#### TASK1.1 감지 스크립트

**파일**: `scripts/detect_horizontal_rule_intro.py`
**감지 패턴**:
- frontmatter 다음 첫 요소가 수평선인 경우
- 도입단락과 첫 H2 사이에 수평선이 있는 경우
- 도입단락 내부에 수평선이 있는 경우
- H2 사이에 일반 텍스트가 없고 수평선만 있는 경우

출력:
```text
[HR] src/content/blog/<slug>.md
type=after-fm / between-intro-h2 / inside-intro / h2-only
lines=...
```

#### TASK1.2 감사 문서화

**파일**: `.planning/phases/36-quality-verification/HR_AUDIT.md`
내용:
- 검사 일시
- 감지 건수
- 감지 파일 목록 + 위치 분류
- 각 파일의 원본 `head -30` 인용

#### TASK1.3 수정 스크립트

**파일**: `scripts/fix_horizontal_rule_intro.py`
- 패턴에 따라 수평선 삭제
- yaml 파싱 후 frontmatter 보존 (`yaml.dump(allow_unicode=True)` 재사용)
- `--dry-run` / `--apply` 지원

#### TASK1.4 재검증 및 실서비스 확인

- `detect_horizontal_rule_intro.py` 재실행 → 0건
- 샘플 2개(스탠포드, 클로드 오퍼스 4.7) curl로 렌더링 확인
- 수평선이 존재하지 않음을 **텍스트 인용**으로 증명

**Acceptance Criteria**:
- `HR_AUDIT.md` 존재
- `fix_horizontal_rule_intro.py --dry-run` / `--apply` 로직 동작
- 재감지 0건 출력
- 샘플 2개 이상 curl 인용 포함

---

### Task 2 — `scripts/audit_description_consistency.py`

#### TASK2.1 일관성 감사 스크립트

**파일**: `scripts/audit_description_consistency.py`
각 포스트마다 다음을 비교:
1. frontmatter `description` 값
2. 본문 첫 단락 첫 문장 (수평선/메타 도입문 제거 후)

일치/불일치 분류:
- **(a) description이 두 번째 단락에서 추출**
- **(b) description이 세 번째 이후 단락에서 추출**
- **(c) 출처 불명 (수동 생성 가능성)**

#### TASK2.2 감사 결과 문서화

**파일**: `.planning/phases/36-quality-verification/DESC_CONSISTENCY_AUDIT.md`
내용:
- 전체 건수 / 일치 건수 / 불일치 건수
- 불일치 패턴 분포 표
- 불일치 사례 10건 인용

#### TASK2.3 로직 분석

- `_extract_first_sentence()` 실행 경로 확인
- `restructure_posts.py` 내에서 `new_description = extract_first_sentence(intro_paragraph, 300)` 위치 확인
- 불일치 원인 가설(여러 단락이 intro로 간주되는지, RE 순서 문제 등) 기록

**Acceptance Criteria**:
- `DESC_CONSISTENCY_AUDIT.md` 작성
- 불일치 건수 명시 (0건이 아님을 전제로 카운트)
- `_extract_first_sentence()` 문제점 분석 포함

---

### Task 3 — 메타 도입문 3차 확장 감지 및 수정

#### TASK3.1 감지 스크립트

**파일**: `scripts/check_meta_intro_v3.py`
- Phase 33 기존 26개 패턴
- Task 1와 중복되지 않는 선에서 신규 8개 패턴 추가:
```python
ADDITIONAL_META_INTRO_PATTERNS = [
    r"기사 원문은.*확인.*수 있습니다",
    r"기사 원문은.*링크.*를 통해",
    r"원문은.*링크.*를 통해",
    r"자세한 내용은.*링크.*를 통해",
    r"자세한 내용은.*확인.*수 있습니다",
    r"관련 기사는.*확인.*수 있습니다",
    r"이 링크.*를 통해.*확인",
    r"브리핑.*에서.*확인",
]
```

#### TASK3.2 수정 스크립트

- 기존 `remove_meta_intro()` 로직을 재사용하거나, Phase 33 스크립트의 제거 규칙을 그대로 적용
- 수정은 `restructure_posts.py`에 통합하지 않고, 별도 처리 스크립트로 둔다

#### TASK3.3 재검증 및 확인

- `META_INTRO_AUDIT_V3.md` 작성
- 수정 후 재감사 0건 확인
- 클로드 오퍼스 4.7 포스트(`2026-04-20-005` 계열 추정) curl 텍스트 인용으로 "기사 원문은 이 링크를 통해..." 부재 증명

**Acceptance Criteria**:
- 3차 감사 문서화
- 수정 후 재감지 0건
- 샘플 1건 이상 curl 인용

---

### Task 4 — SEO Description 분석 및 개선 방향 수립

#### TASK4.1 품질 통계

**파일**: `scripts/analyze_descriptions.py`
항목:
- description 길이 분포 (평균, 최소, 최대)
- 140~160자 권장 범위 비율
- 종결어미 만족 비율
- 중복 description 건수

출력:
- `SEO_ANALYSIS.md` 기반 데이터

#### TASK4.2 샘플 분류

- 100개 샘플을 수동 분류 (페이지 전체 요약 O/X)
- 분류 기준 문서화

#### TASK4.3 권장안 작성

`SEO_ANALYSIS.md` 포함 내용:
- 현황 통계
- 두 옵션 비교:
  - **A. 현행 유지**: 자동화 용이, SEO 관점에서 중간~낮은 퀄리티
  - **B. SEO 최적화**: LLM 생성 전체 요약, ROI 분석 포함
- Google Search Central 가이드 인용
- 비용 추정 (LLM 호출 수, 예상 토큰, 단가)
- 명확한 권장안 + 근거

**Acceptance Criteria**:
- `SEO_ANALYSIS.md` 작성
- 100개 샘플 분류 비율 포함
- 옵션 A/B 비교 + 권장안 + Google 인용

---

### Task 5 — 종합 보고서

**파일**: `.planning/phases/36-quality-verification/SUMMARY.md`

내용:
- Task 1~4 결과 요약
- 발견된 문제 3가지 요약
- 후속 Phase 제안 (Task 2 불일치 패턴 수정 우선순위 등)
- 전체 감사 결과 핵심 지표 표

---

## 의존성

```
Task 1 ──┐
         ├── Task 5 (SUMMARY)
Task 2 ──┤
         ├── Task 4 (SEO 분석 참고)
Task 3 ──┘
```

- Task 1은 가장 빠르게 실행 가능 (기존 검출 로직 재사용)
- Task 2, 3은 병렬 가능
- Task 4는 Task 2 결과(description 일관성 불일치 패턴)를 참고

---

## Checklist

### Task 1
- [ ] `scripts/detect_horizontal_rule_intro.py` 작성
- [ ] `HR_AUDIT.md` 작성: 감지 건수 + 파일 목록 + 원본 인용
- [ ] `scripts/fix_horizontal_rule_intro.py` 작성: dry-run / apply
- [ ] 전체 적용 후 재감지 0건
- [ ] 스탠포드, 클로드 오퍼스 4.7 curl 인용

### Task 2
- [ ] `scripts/audit_description_consistency.py` 작성
- [ ] `DESC_CONSISTENCY_AUDIT.md` 작성
- [ ] `_extract_first_sentence()` 로직 분석 포함

### Task 3
- [ ] `scripts/check_meta_intro_v3.py` 작성 (26 + 8 패턴)
- [ ] `META_INTRO_AUDIT_V3.md` 작성
- [ ] 수정 후 재감사 0건
- [ ] 클로드 오퍼스 4.7 "기사 원문은..." 부재 curl 인용

### Task 4
- [ ] `scripts/analyze_descriptions.py` 작성
- [ ] `SEO_ANALYSIS.md` 작성
- [ ] 100개 샘플 분류
- [ ] 두 옵션 비교 + 권장안 + Google 인용

### Task 5
- [ ] `SUMMARY.md` 작성
- [ ] 후속 Phase 제안

---

## 관련 리스크

- `restructure_posts.py` 재실행 시 수평선/메타 도입문이 재삽입될 가능성 있음 → 이후 배치 실행 시 수정 스크립트를 재실행하도록 문서화 필요
- 100개 수동 분류는 시간 소요가 크며, Phase 37로 미루어도 허용하나 Phase 36에서 최소 10개 샘플은 분류하여 방향성을 확정해야 함
- 작업 로그 `/Users/twinssn/Desktop/메모 Hugh/logs/YYYYMMDD.md`에 반드시 append 한다
