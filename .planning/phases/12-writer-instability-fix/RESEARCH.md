# RESEARCH.md — Phase 12: Writer Validation Instability Fix

## Problem

2026-07-05 00:00~08:37 동안 threads 발행이 전면 중단됨. 동일한 기사(38551, 호주 AI 필기)가 반복 선정되어 8시간 이상 실패.

## Log Analysis (2026-07-05 08:38~08:51)

### 1st attempt (08:39~08:44) — FAIL (Hook 403자)

```
[08:39:15] generate (temp=0.4) → 3 models sequential: MiMo→DeepSeek→GPT-4o-mini
[08:41:08] fix_cards → humanize → 6→5 count mismatch → 원본 유지
[08:41:40] fix_cards → MiMo → 8>6 segments → truncated to 6
            → Hook 403자 → VALIDATION FAIL
```

**Latency breakdown:**
- Generate: 08:39:15 → 08:41:08 = **1min 53sec** (3 models sequential × ~38sec each)
- humanize + fix_cards: 08:41:08 → 08:41:40 = **32sec**
- 2nd generate + parse: 08:41:40 → 08:43:06 = **1min 26sec**
- 2nd humanize: 08:43:06 → 08:43:29 = **23sec**
- 2nd MiMo: 08:43:29 → 08:43:36 = **7sec**
- Fallback generate: 08:43:36 → 08:44:58 = **1min 22sec** (only 2 models)

**Total wall-clock for 1 failed article: ~5min 43sec**
→ Only 1 article attempt per main_v3 retry cycle

### 2nd attempt (08:45~08:51) — SUCCESS

```
[08:45:58] generate (temp=0.4) → 3 models sequential → ~2min
[08:48:06] humanize: 2/6 cards changed (OK, count preserved!)
[08:48:24] fix_cards → 8>6 → truncated → **BUT Hook passed** (shorter hook?)
[08:48:24] ✅ VALIDATION PASS
```

## 근본 원인 (Root Causes)

### RC-1: `--- join → LLM → --- split` 패턴이 모든 변환 함수에 존재

| 함수 | 라인 | 동작 | 문제 |
|------|------|------|------|
| `humanize_cards()` | 261-362 | cards를 `---\n` join → LLM → `---` split | LLM이 `---` 구분자를 추가/삭제 → count mismatch |
| `fix_cards()` | 412-461 | cards를 `---\n` join → LLM → `---` split | LLM이 `---`를 추가 → 7-9 segments → truncation → 구조 붕괴 |
| `parse_cards()` | 464-484 | `---` split | `---` 없으면 `\n\n` fallback |

**result**: 카드 경계를 유지하는 것이 LLM의 출력 형식 준수에 전적으로 의존. LLM이 항상 실패.

### RC-2: 3-model sequential fallback이 latency의 주범

`model_router.py`에서 `chat_completion()`은:
1. MiMo 호출 (timeout ~40s) → 실패 또는 None
2. DeepSeek 호출 (~40s timeout)
3. GPT-4o-mini 호출 (~40s timeout)

실제로 MiMo가 성공 응답을 해도 fallback 체인이 순차 실행되어 1-2분 소요.
→ generate 1회에 ~2분, humanize 1회에 ~30초, 합계 ~3분.

### RC-3: write_thread 내부 2-attempt loop + fallback = 중복 구조

- 각 시도마다 generate + fix_cards 전체를 재실행
- 2회 실패 후 fallback에서 같은 과정을 temp=0.3으로 재실행
- 총 3회 generate, 3회 fix_cards (각각 내부 humanize 포함)
- **모든 시도가 동일한 pipeline을 타므로 같은 이유로 실패할 확률 높음**

### RC-4: 검증이 transform 함수 내부에 분산

- humanize: count 검증
- fix_cards: count 검증 (같음/초과/부족 각각 분기)
- generate 후 write_thread: count 검증
- 최종: validate_card_structure + validate_cards + validate_final_output

변환 함수가 자기 출력을 검증해야 하는 이유는 `--- join/split` 때문. per-card로 바꾸면 이 검증들이 전부 사라짐.

## 설계 원칙 (Redesign)

### 원칙 1: 변환 함수는 카드 구조를 절대 변경하지 않는다

```
humanize_cards(cards: list[str]) → list[str]
  - 각 카드를 개별적으로 LLM에 전달 (--- join 금지)
  - 출력 리스트 길이 == 입력 리스트 길이 (불변량)

fix_cards(cards: list[str]) → list[str]
  - 각 카드를 개별적으로 LLM에 전달 (--- join 금지)
  - 출력 리스트 길이 == 입력 리스트 길이 (불변량)
```

### 원칙 2: 검증은 2곳에서만 수행한다

```
① parse_cards 직후: count + 각 카드 기본 구조 검증
② 최종 return 직전: validate_card_structure + validate_cards
```

### 원칙 3: LLM 호출은 parallel race로 최적화한다

generate/humanize/fix_cards의 첫 LLM 호출에서 3개 모델을 동시에 실행하고 가장 먼저 오는 응답 사용.

### 원칙 4: retry 구조를 단순화한다

- write_thread 내부 2-attempt loop 제거 (1회 generation → fail 시 main_v3에서 다른 기사로 fallback)
- fallback(temperature=0.3) 제거 (동일한 파이프라인을 temperature만 바꿔서 재실행하는 것은 효과 없음)
- main_v3의 5회 retry 유지하되, 기사 배타적 lock-in 해결 (Phase 12-02 T1)

## 성공 조건
1. 모든 변환 함수가 per-card로 동작 (count 불변)
2. pipeline latency 50% 이상 감소
3. 검증은 최종 단계에서 1회만 통과하면 발행
4. 기사 실패 시 다음 기사로 즉시 이동
