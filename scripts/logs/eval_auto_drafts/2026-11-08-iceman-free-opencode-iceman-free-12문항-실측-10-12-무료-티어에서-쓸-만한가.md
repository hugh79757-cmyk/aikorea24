TITLE: iceman-free(opencode/iceman-free) 12문항 실측 — 10/12 무료 티어에서 쓸 만한가

한 줄 요약: **iceman-free**는 OpenCode CLI에서 `opencode/iceman-free`로 호출되는 모델입니다. AIK24가 12문항으로 실측한 결과는 **10/12**였습니다. 12문항 기준 상위권입니다. 실무 파일럿에 바로 넣어 볼 수 있는 수준입니다.

## 1. iceman-free이란 — 확인된 것과 확인되지 않은 것

아래 값은 공개 카탈로그(models.dev)와 `opencode models` 출력에서 그대로 옮긴 것입니다.

| 구분 | 내용 | 출처 |
| --- | --- | --- |
| 모델명 | Iceman Free | models.dev |
| 설명 | Stealth model, free for a limited time | models.dev |
| 공칭 컨텍스트 | 262,144 토큰 | models.dev |
| 공칭 최대 출력 | 131,072 토큰 | models.dev |
| 가격(입력/출력) | 무료 (0/0) | models.dev |
| 지원 기능 | 추론 · 도구 호출 | models.dev |
| 공개일 | 2026-11-06 | models.dev |
| 가중치 공개 | 비공개 | models.dev |
| 모델 ID / CLI ID | `iceman-free` / `opencode/iceman-free` | `opencode models` 실측 |

확인되지 않은 항목: 학습 데이터·가중치·파라미터 수는 공개되지 않았습니다 / 제작사가 공개되지 않은 스텔스 모델로 표기돼 있습니다.

## 2. OpenCode에서 사용하는 방법

1. 터미널에서 `opencode models | grep iceman-free` 를 실행해 목록에 `opencode/iceman-free` 가 있는지 확인합니다.
2. `opencode run -m opencode/iceman-free "한 단어로 대답: PONG"` 으로 한 번 호출해 응답이 오는지 봅니다.
3. OpenCode 모델 선택 창에서 `opencode/iceman-free` 를 검색해 고릅니다. 같은 모델이 목록에 없으면 그 프로바이더에 로그인돼 있지 않은 것입니다.

무료 티어는 호출 한도가 걸려 있을 수 있습니다. 같은 모델을 반복 호출하다 응답이 끊기면 한도 소진을 먼저 의심하고, 모델 성능 문제로 단정하지 마십시오.

## 3. 12문항 실측 — 축별 결과

2026년 11월 08일 OpenCode CLI로 12문항을 호출하고, 문항별 결정적 채점 함수와 샌드박스 실행으로 0/1을 판정했습니다. 판관(LLM 심판)은 쓰지 않았습니다.

| 축 | 정답 | 문항수 |
| --- | --- | --- |
| 지시 이행 | 1 | 2 |
| 코딩 실무 | 4 | 4 |
| 맥락 유지 | 2 | 2 |
| 에이전트(계획·도구·복구·판단) | 3 | 4 |

문항별 결과와 모델이 실제로 출력한 답변 앞부분입니다.

- Q1 [지시 이행] 오답 — 답변: 이 코드는 `add`라는 함수를 정의합니다. - 함수는 두 개의 매개변수 `a`와 `b`를 받습니다. - `return a + b`를 통해 두 값을 더한 결과를 반환합니다. 즉, 전달된 두 인자의 합을 계산해 돌려주는 함수입니다. ---끝---
- Q2 [지시 이행] 정답 — 답변: {"이름":"김민수","나이":31,"취미":["등산","독서"]}
- Q3 [코딩 실무] 정답 — 답변: **수정 코드:** ```python from datetime import datetime, timedelta def get_expired_tokens(tokens, now): return [t for t in tokens if datetime.fromisoformat(t['expires_at']) < now] ``` *…
- Q4 [코딩 실무] 정답 — 답변: ## `tests/test_safe_div.py` (pytest) 아래는 `safe_div(a, b)`를 검증하는 pytest 테스트입니다. **정상 입력, 0으로 나누기, 음수, 경계값**을 모두 다룹니다. (이 저장소에는 동일 목적의 `tests/test_safe_div.py`와 구현 `scripts/safe_div.…
- Q5 [코딩 실무] 정답 — 답변: ```python def _select_user_fields(user): return {'id': user['id'], 'name': user['name'], 'email': user['email']} def _filter_users(users, predicate): out = [] for u in users: if pr…
- Q6 [코딩 실무] 정답 — 답변: import re from datetime import datetime def parse_log_line(s): if not isinstance(s, str): raise TypeError("s must be a str") if not s.strip(): raise ValueError("empty line") parts …
- Q7 [맥락 유지] 정답 — 답변: normalize_ledger_entries
- Q8 [맥락 유지] 정답 — 답변: 대화에서 요청하신 작업 3가지는 다음과 같습니다. 1. **파이썬 시작 방법 안내**: “파이썬을 처음 시작하려면 뭘부터 해야 해?” — 파이썬을 처음 시작할 때 무엇부터 해야 하는지 요청. 2. **변수 이름 규칙 3개**: “변수 이름 지을 때 규칙 3개만 알려줘.” — 변수 이름을 지을 때의 규칙 3가지를 요청. 3…
- Q9 [에이전트(계획·도구·복구·판단)] 정답 — 답변: ["undefined `total` variable/scope causing runtime error","breaking behavior change removing tax calculation","database side effect and transaction/error handling for `db.insert`",…
- Q10 [에이전트(계획·도구·복구·판단)] 정답 — 답변: Root cause: `fetch` 함수에 상대 경로(`/api/users`)가 그대로 전달되어 `requests.get`이 완전한 절대 URL로 요청하지 못해 연결/재시도 후 타임아ウト이 발생한다. ```diff --- a/app.py +++ b/app.py @@ -1,4 +1,5 @@ import requests +B…
- Q11 [에이전트(계획·도구·복구·판단)] 오답 — 답변: [ { "step": 1, "title": "HTML 골격 및 정적 화면 구조 작성", "dom_screens": [ "index.html 단일 파일에 <!DOCTYPE html>, <head>(meta charset, viewport, title, 기본 style), <body> 구성", "<main id=\"app\"…
- Q12 [에이전트(계획·도구·복구·판단)] 정답 — 답변: ## 지금 바로 처리해야 하는 것 | 항목 | 이유 (판단 근거) | |---|---| | **장애 후속 조치로 고객 메일 발송 대기 중** | 장애 이후 커뮤니케이션은 신뢰 회복의 핵심입니다. 발송이 지연되면 고객 불확실성·문의 증가·추가 불만으로 이어질 수 있습니다. 메일 내용 자체가 길어도, **상황 공유/원인 파악…

## 4. 이런 분께 추천합니다

- 맥락유지 축 2/2 — 앞선 지시를 오래 기억해야 하는 대화에 쓸 만합니다.
- 코딩실무 축 4/4 — 코드 작성·수정 요청에 쓸 만합니다.
- 에이전트 축 3/4 — 여러 단계를 스스로 나누는 작업에 쓸 만합니다.

## 5. 솔직한 한계

- 이 결과는 1회 실측입니다. 같은 모델을 다시 돌리면 점수가 달라질 수 있습니다.
- CLI 경유라 토큰 사용량이 측정되지 않습니다. 비용 계산은 이 글에 넣지 않았습니다.
- 12문항은 지시이행·코딩실무·맥락유지·에이전트 4개 축만 봅니다. 긴 문서 요약 품질, 다국어 정확도, 이미지 입력은 이 평가에 없습니다.
- 0점 2문항의 성격은 아래에서 따로 정리했습니다. 채점기 해석 차이일 수 있어 단정하지 않았습니다.

## AIK24 실측 결과 (2026-11-08)

| 항목 | 값 |
| --- | --- |
| 실측일 | 2026-11-08 |
| 검증 방법 | OpenCode CLI `opencode run -m opencode/iceman-free --format json` · 문항별 결정적 채점 · 코드 문항은 샌드박스 실행 |
| 모델 ID | `iceman-free` |
| 결과 | 10/12 |
| 토큰 사용량 | CLI 경유로 측정되지 않음 (미측정) |
| 니들 컨텍스트 실측 하한 | 133,120 토큰 |

## 0점 문항 2개의 성격

0점 문항을 답안 원문으로 확인해 아래와 같이 구분했습니다. 채점기 기준 점수는 그대로 두고, 해석만 덧붙였습니다.

- Q1 [지시 이행] 채점기 오탐 — 답변은 한국어 설명과 마지막 줄 `---끝---` 조건을 모두 지켰습니다. 0점 원인은 채점기가 인라인 백틱 안의 코드 식별자(`add`·`a`·`b`)를 "영문 3자 이상"으로 세는 규칙입니다. 질문 자체가 코드를 설명하라고 요구하므로 식별자를 영문으로 쓰는 것은 불가피합니다.
- Q11 [에이전트(계획·도구·복구·판단)] 실제 실패(형식) — 4단계 계획은 만들었지만 최상위 구조가 4개짜리 배열이 아니라 {"steps": [...]} 래핑이었습니다. 채점기는 최상위 4원소를 요구합니다. 내용은 있으나 형식 지시를 지키지 못한 경우입니다. 다만 JSON 래핑은 흔한 해석이라 질문-채점기 불일치 성격도 일부 있습니다.

## 참고 자료

- [OpenCode Zen 모델 목록](https://opencode.ai/docs/zen/)
- [models.dev 모델 카탈로그](https://models.dev/)

## 마무리 — 오늘 바로 할지 결정하는 3단계

1. `opencode models | grep iceman-free` 로 이 모델이 지금도 목록에 있는지 확인합니다(무료 목록은 자주 바뀝니다).
2. 이 글의 12문항 중 실패한 문항을 같은 형식으로 한 번 직접 던져 봅니다. 재현되면 그 용도에는 쓰지 않습니다.
3. 무료 한도가 붙은 모델이므로, 반복 호출이 필요한 작업은 한도 소진 시점을 함께 기록해 둡니다.

이 순위는 리더보드에 새 모델이 들어오면 바뀔 수 있습니다.
