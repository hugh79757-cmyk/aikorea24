# Phase 6: Prompt Leakage & Truncation Fix

**목표:** Threads 발행글 hook/narrative에 프롬프트 라벨(`상식(A):`)이 누출되고, 30/50자 강제 트렁케이션으로 문장이 중간에 잘리는 문제 수정

## 진단

### 문제 A — 무식한 글자수 자르기

| 위치 | 파일 | 줄 | 코드 | 영향 |
|------|------|-----|------|------|
| A1 | `pipeline/threads/pitch.py` | 255 | `pitch.get('hook', '')[:30]` | posted.json hook 30자 강제 절단 |
| A2 | `pipeline/threads/pitch.py` | 256 | `pitch.get('narrative', '')[:50]` | posted.json narrative 50자 강제 절단 |
| A3 | `pipeline/threads/pitch.py` | 177-178 | `[:15]`/`[:30]` | is_duplicate_pitch 비교도 동일 절단 |

사례: `"...비율이 2.5%에"`, `"...AI가 스마트워치와 이어"` — 문장 중간에서 잘림

### 문제 B — 시스템 프롬프트 누출

| 위치 | 파일 | 줄 | 내용 |
|------|------|-----|------|
| B1 | `pipeline/threads/pitch.py` | 39, 52-53 | `"상식적으로 A였어야 하는데 실제로는 B인 상황"` |
| B2 | `pipeline/threads/pitch.py` | 470 | `_regenerate_pitch_from_crawl`에도 동일 패턴 |

LLM이 이 지시문을 그대로 출력: `"상식(A): ... vs 실제(B): ..."` 형태로 narrative에 박힘

## 액션 플랜

### Step 1: clean_leaked_prompt() 헬퍼 추가
- `pipeline/threads/pitch.py`에 `LEAKED_PROMPT_PATTERNS` 리스트 + `clean_leaked_prompt(text)` 함수 신규
- 리스트 기반 관리 (추가 누출 패턴 발견 시 1줄 추가)
- 대상 패턴: `상식(A):`, `실제(B):`, `vs` 구분자
- 단위 테스트 추가 (`tests/test_pitch.py`)

### Step 2: 프롬프트 수정 (근본 해결)
- `pipeline/threads/pitch.py:39,52-53`: "상식(A) vs 실제(B)" 템플릿 → 자연어 지시문으로 교체
- `pipeline/threads/pitch.py:470`: 동일
- 핵심: "출력에 라벨/태그를 절대 포함하지 말 것" 명시

### Step 3: save_pitch_to_history() 방어막 추가
- 저장 전 `clean_leaked_prompt()` 통과
- `[:30]`/`[:50]` 트렁케이션 제거 → 전체 저장

### Step 4: posted.json 기존 오염 항목 cleanup (선행!)
- `"상식(A):"` 또는 `"실제(B):"` 포함된 entry 정리
- 이미 발행된 Threads 자체는 수정 불가 (API 미지원), posted.json 기록만 정리하여 재발행 방지

### Step 5: is_duplicate_pitch() 트렁케이션 완화
- `[:15]`/`[:30]` → 충분히 큰 값 (80/120) 또는 전체 비교
- Step 4 선행 필수: 긴 버전 vs 짧은 posted.json 기록의 비교 일관성 확보

## 검증
- 기존 테스트 전부 통과 (`pytest`)
- `posted.json`에 더 이상 `상식(A):` 패턴 없음
- 저장된 hook/narrative가 문장 중간에서 안 잘림
