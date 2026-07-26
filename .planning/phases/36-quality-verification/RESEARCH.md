# Phase 36 Research: 품질 검증 3종 및 SEO Description 개선 방향 수립

> **Phase**: 36-quality-verification
> **일시**: 2026-07-26
> **상태**: 연구 완료
> **Phase 35 연계**: 빈 H2 문제 수정(820개 포스트) 후, 외부 검증에서 추가 발견된 3가지 문제를Phase 36에서 해결

---

## 1. 컨텍스트: Phase 35 결과 + 외부 검증 발견

### 1.1 Phase 35 결과 재확인

```
$ python3 scripts/detect_empty_h2.py --all
총 감지 건수: 0건 (Pattern 1=0, Pattern 2=0, Pattern 3=0)
```

### 1.2 외부 검증에서 새로 발견된 3가지 문제

#### 발견 1: 도입단락이 `* * *` 수평선으로 시작하는 포스트 다수 존재

스탠포드, 클로드 오퍼스 4.7 등 샘플 포스트에서 frontmatter → `* * *` → 도입단락 구조 확인. `restructure_posts.py`가 도입단락 삽입 시 수평선을 남기는 부작용 또는 Pattern 3 미처리 잔해일 가능성.

#### 발견 2: 메타 description이 본문 첫 단락 첫 문장이 아닌 다른 단락에서 추출

스탠포드 포스트 예시:
- 본문 첫 단락 첫 문장: "스탠포드대학교 인간 중심 AI 연구소(HAI)가 2026년 AI 인덱스 보고서를 공개했습니다."
- 현재 description: "스탠포드 HAI는 2017년부터 매년 AI 분야의 기술 역량, 연구 성과, 사회적 영향, 대중 인식 등을 종합 measurement한 보고서를 발간합니다"

→ Phase 32 "description = 본문 첫 문장" 정책이 일관되지 않게 적용되고 있음.

#### 발견 3: "기사 원문은 이 링크를 통해..." 메타 도입문 잔존

클로드 오퍼스 4.7 포스트 도입단락 첫 문장이 Phase 33 26개 패턴에 없는 신규 유형임.

### 1.3 SEO Description 문제 진단

**Google Search Central 인용**:
- "Google uses the meta description to create snippets when we believe it gives users a more accurate description than what we could extract from the page content"
- Best Practice: "Summarize the page content accurately... Don't just repeat the first sentence"

**현재 방식**: `extract_first_sentence(intro_paragraph, 300)` → 본문 첫 문장 그대로 추출
**문제**: 첫 문장을 그대로 사용 → "페이지 전체 요약"이 아님 → Google이 자동 추출 스니펫을 대신 사용할 가능성 높음

---

## 2. Phase 36 4대 과제 정의

### 과제 1: `* * *` 수평선 도입단락 전수 조사 및 수정 (P1)

**감지 패턴**:
- frontmatter 다음 첫 요소가 수평선인 경우
- 도입단락과 첫 H2 사이에 수평선이 있는 경우
- 도입단락 내부에 수평선이 있는 경우
- H2 사이에 `* * *` 또는 `---` 수평선만 있고 일반 텍스트가 없는 경우 (Pattern 3과 유사하나 수평선 자체가 문제)

**기대 검출 건수**: 50~150건 (전체 820개 중 6~18%로 추정)

**기반 기존 스크립트**:
- `scripts/detect_empty_h2.py`의 패턴 탐지 로직 재사용
- `scripts/restructure_posts.py`의 frontmatter 파싱 로직 재사용

---

### 과제 2: description 추출 일관성 전수 조사 (P1)

**목적**: description이 어떤 단락에서 추출되는지인지 확인. Phase 32 정책("첫 단락 첫 문장")과 실제 추출 결과를 비교.

**감지 방법**:
1. 각 포스트에서 frontmatter description 추출
2. 본문 첫 단락 첫 문장 추출 (수평선/메타 도입문 제거 후)
3. 두 값의 일치 여부 비교 (정확 일치 / 유사도 0.9 이상)
4. 불일치하는 경우: description이 본문 어느 단락에서 왔는지 추정

**유형 분류**:
- (a) description이 두 번째 단락에서 추출
- (b) description이 세 번째 이후 단락에서 추출
- (c) description이 어디서 왔는지 불명 (수동 생성 가능성)

**_extract_first_sentence() 재검토**:
- 왜 첫 단락 첫 문장이 아닌 다른 단락에서 추출되는지 원인 추적 필요
- `restructure_posts.py:222-267` `extract_first_paragraph_after_h2()` 로직 검토

---

### 과제 3: 메타 도입문 감지 패턴 3차 확장 (P2)

**Phase 33 기존 26개 패턴에 8개 추가**:

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

**전체 820개 재감사 후 수정 → 재감사 0건 확인** 필요

---

### 과제 4: SEO Description 개선 방향 수립 (P3)

**분석 항목**:
1. 820개 description 길이 분포 (평균, 최소, 최대, 140-160자 범위 비율)
2. 샘플 100개 수동 분류: "페이지 전체 요약" vs "일부 단락 발쵀"
3. Google Best Practice 부합 여부 평가

**두 옵션 비교**:

| 옵션 | 설명 | 장점 | 단점 | 비용 |
|------|------|------|------|------|
| **A. 현행 유지** | description = 본문 첫 문장 (또는 임의 단락) | 자동화 용이 | SEO 관점에서 Bad 패턴, 일관성 부족 | ₩0 |
| **B. SEO 최적화** | description = LLM 생성 전체 요약 | Google Best Practice 부합, CTR 개선 | LLM 비용, 파이프라인 변경 | ₩16K~49K (일회성) |

**권장**: Phase 37 이후 하이브리드 모드 도입 검토

---

## 3. 산출물 요약

| 파일 | 역할 | 기반 |
|------|------|------|
| `scripts/detect_horizontal_rule_intro.py` | 수평선 감지 | `detect_empty_h2.py` 재사용 |
| `scripts/fix_horizontal_rule_intro.py` | 수평선 제거 | `fix_empty_h2.py` 재사용 |
| `scripts/audit_description_consistency.py` | description 일관성 감사 | `restructure_posts.py` 로직 재사용 |
| `scripts/check_meta_intro_v3.py` | 메타 도입문 3차 확장 감지 | Phase 33 패턴 + 8개 신규 |
| `scripts/analyze_descriptions.py` | description 품질 통계 | 신규 작성 |
| `.planning/phases/36-quality-verification/HR_AUDIT.md` | 수평선 감사 결과 | 스크립트 출력 |
| `.planning/phases/36-quality-verification/DESC_CONSISTENCY_AUDIT.md` | description 일관성 감사 | 스크립트 출력 |
| `.planning/phases/36-quality-verification/META_INTRO_AUDIT_V3.md` | 메타 도입문 3차 감사 | 스크립트 출력 |
| `.planning/phases/36-quality-verification/SEO_ANALYSIS.md` | SEO 분석 + 권장안 | 연구 기반 |
| `.planning/phases/36-quality-verification/SUMMARY.md` | 종합 보고서 | 4개 Task 통합 |

---

## 4. 검증 기준

| Task | 인수 기준 |
|------|----------|
| Task 1 | `HR_AUDIT.md` 감지 건수/파일 목록 + fix 적용 후 재감지 0건 + 샘플 2개 curl 확인 |
| Task 2 | `DESC_CONSISTENCY_AUDIT.md` 일치/불일치 통계 + 로직 분석 + 불일치 건수 0 아닌 경우 수정 방안 제안 |
| Task 3 | `META_INTRO_AUDIT_V3.md` 확장 패턴 감사 결과 + 재감사 0건 + 클로드 오퍼스 4.7 포스트 "기사 원문은..." 부재 curl 확인 |
| Task 4 | `SEO_ANALYSIS.md` 820개 통계 + 100개 분류 + 두 옵션 분석 + 명확한 권장안 + Google 가이드 인용 |

---

*End of RESEARCH.md — Phase 36 research complete. Ready for plan-phase.*
