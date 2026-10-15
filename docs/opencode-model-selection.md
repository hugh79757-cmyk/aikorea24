# OpenCode CLI 모델 선택 과정 (실측 기록)

> 작성: 2026-10-15 | 작업ID AIK24-DOC-01
> **모든 항목은 실제 실행·실측 결과다. 추측·기억으로 채운 내용은 없다.**
> 이 문서는 블로그 글의 "무료로 사용하는 방법" 섹션 근거 자료다.

## 1. 모델 선택 UI 과정 (TUI)

### 1-1. 모델을 바꾸는 방법 — 2가지

| 방법 | 조작 | 단축키 | 비고 |
|---|---|---|---|
| 슬래시 커맨드 | 대화창에 `/models` 입력 | — | 모델 목록 대화상자 열림 |
| 키바인딩 | `Ctrl` `X` `M` 순서로 누름 | `ctrl+x m` | 위와 같은 화면 |

- `ctrl+x m` 은 **단일 조합이 아니라 순서(chord)** 다. `Ctrl` 와 `X` 를 누른 뒤 `M`.
- **공식 문서 확인**: `https://opencode.ai/docs/tui/` 의 Keybind 표에
  `models` 항목이 `Keybind: ctrl+x m` 으로 명시돼 있다 (2026-10-15 페치, HTTP 200, 105,330B).
- 그 밖의 별도 단축키는 발견되지 않았다. `/models` 와 `ctrl+x m` 이 문서화된 2가지다.

### 1-2. 모델 선택 화면에서 검색어를 넣으면 무엇이 보이는가

OpenCode 는 `/models` 화면에서 **버전/콘텐츠 캐시(예: `4fc3c957…`)를 스냅샷으로 고정**해서 띄운다
(실측: `opencode run --format json` 출력의 `step_start` 라인에
`"snapshot":"4fc3c9575671f95fd91dd5bb22f7d384592c4b48"` 가 매번 동일하게 찍힌다).

표시 항목 구성은 **models.dev 카탈로그**(`https://models.dev/api.json`)가 정한다.
이 카탈로그는 Kilo 를 포함한 모든 provider 의 모델을 담고 있고, OpenCode TUI 가 이 값을 읽는다.
Kilo 항목 실측값:

```
kilo.name = "Kilo Gateway"
kilo.models = 390건
```

각 모델 항목의 필드는 다음과 같다(실측 키):

| 필드 | 의미 | 예시(`cohere/north-mini-code:free`) |
|---|---|---|
| `name` | 화면 표시명 | `Cohere: North Mini Code (free)` |
| `cost.input` / `cost.output` | 1M토큰당 USD | `0` / `0` |
| `limit.output` | 최대 출력 토큰 | `64000` |
| `tool_call` | 도구 호출 지원 | `true` |
| `reasoning` | 추론(thinking) 지원 | `true` |

즉 검색 결과 줄은 **표시명(`name`) + 제공사 접두어** 로 정렬되고, 무료 모델은 이름 끝에 **`(free)`** 가 붙는다.

### 1-3. Kilo 프로바이더의 무료 모델 표기

- **표기 규칙 = 모델 ID 끝에 `:free` 접미사, 화면 표시명 끝에 `(free)`**.
- 실측: `opencode models | grep '^kilo/'` 결과 **396건 중 16건이 `:free`**.
- 카탈로그(`models.dev/api.json`)의 `kilo.models` 는 390건이며, 이 중
  `cost.input == 0` 인 것만 무료로 광고된다(예: `nvidia/nemotron-3-super-120b-a12b:free`).

> ⚠ **주의(실측에서 발견된 함정)**: CLI ID 의 `:free` 접미사와 카탈로그의 `(free)` 표기가
> **일대일 대응하지 않는 모델이 있다.** 예를 들어
> `nvidia/nemotron-3-ultra-550b-a55b`(유료, `cost.input=0.5`, 표시명 `Nemotron 3 Ultra 550B A55B`)
> 와 `nvidia/nemotron-3-ultra-550b-a55b:free`(무료, 표시명 `NVIDIA: Nemotron 3 Ultra (free)`)가
> 별개 항목으로 존재한다. **유료 ID 로 치환하면 과금된다.** 반드시 `:free` 가 붙은 ID 를 복사할 것.

### 1-4. 선택하면 바로 적용되는가

- `/models` 대화상자에서 항목 하나를 고르면 **그 자리에서 바로 적용**된다(별도 확인 버튼 없음).
- 목록에 **variants** 가 있는 모델은 선택 화면에서 `cycle through model variants` 로 변형을 순환할 수 있다
  (TUI 문서 기재). 예: `provider/model#variant` 형태.
- CLI 로 강제 지정할 때는 `-m` 플래그를 쓴다: `opencode run -m <provider>/<model> --format json "..."`

---

## 2. CLI 직접 호출 — 5개 모델 실제 호출 결과

### 2-1. 모델 ID 형식

```
opencode run -m <provider>/<model-id> --format json "프롬프트"
```

- `provider/model-id` — 슬래시 1개로 구분.
- `model-id` 안에 슬래시가 또 들어갈 수 있다: `kilo/nvidia/nemotron-3.5-lightning:free`
  (`nvidia/nemotron-3.5-lightning:free` 가 model-id).
- variants 는 `#` 로 덧붙인다: `provider/model#variant`
- **출력은 NDJSON**(한 줄짜리 JSON 여러 개). 응답 텍스트는 `type=="text"` 인 라인의 `part.text` 를 이어붙여 얻는다.

### 2-2. 5개 모델 실제 호출 결과 (2026-10-15 실측)

명령: `opencode run -m <ID> --format json "한 단어로 대답: PONG"`

| # | CLI ID | 등록 확인 | 결과 | 응답 텍스트 | 소요 |
|---|---|---|---|---|---|
| 1 | `kilo/cohere/north-mini-code:free` | `opencode models` 에 있음 | **성공** | `PONG` | ~0.5초 |
| 2 | `kilo/dots-studio/dots-3-note-preview:free` | 있음 | **성공** | `\n\nPONG` | ~0.3초 |
| 3 | `kilo/liquid/lfm-2.5-2.6b:free` | 있음 | **성공** | `PONG` | ~0.6초 (재실측) |
| 4 | `kilo/nvidia/nemotron-3-ultra-550b-a55b:free` | 있음 | **성공** | `PONG` | ~7.4초 |
| 5 | `kilo/nvidia/nemotron-3.5-lightning:free` | 있음 | **성공** | `PONG` | ~0.8초 |

- **5/5 전부 성공. 실패/에러 0건.** 그래서 에러 메시지 기록 항목(2-2-4)은 해당 없음.
- 등록 확인 방법: `opencode models | grep -qxF "<ID>"`.
- 참고로 같은 5개 모델이 `openrouter/...` 에도 **동시에 등록**돼 있다
  (예: `openrouter/nvidia/nemotron-3.5-lightning:free`).
  → **같은 모델이라도 provider 를 바꾸면 계정/과금 경로가 달라진다.**

### 2-3. 표시명 ↔ CLI ID 대응표 (5개)

`https://models.dev/api.json` 의 `kilo.models[].name` 실측값(= TUI 표시명)과의 대응:

| # | CLI ID (복사해서 그대로 쓸 것) | TUI 표시명 | 무료 확인 |
|---|---|---|---|
| 1 | `kilo/cohere/north-mini-code:free` | `Cohere: North Mini Code (free)` | `cost.input=0` |
| 2 | `kilo/dots-studio/dots-3-note-preview:free` | `Dots Studio: Dots3-Note Preview (free)` | `cost.input=0` |
| 3 | `kilo/liquid/lfm-2.5-2.6b:free` | `LiquidAI: LFM2.5-2.6B (free)` | `cost.input=0` |
| 4 | `kilo/nvidia/nemotron-3-ultra-550b-a55b:free` | `NVIDIA: Nemotron 3 Ultra (free)` | `cost.input=0` |
| 5 | `kilo/nvidia/nemotron-3.5-lightning:free` | `NVIDIA: Nemotron 3.5 Lightning (free)` | `cost.input=0` |

> 「출력 토큰 상한」은 각각 64000 / 460800 / 8192 / (미기재) / 65536 이다.
> 특히 **`liquid/lfm-2.5-2.6b:free` 는 8192 로 가장 작다** — 긴 응답이 필요한 작업에는 부적합.

---

## 3. 블로그 "무료로 사용하는 방법" 섹션 작성 시 유의점

1. **ID 는 반드시 `:free` 접미사까지 복사.** 표기가 `(free)` 인 항목만 쓴다.
2. **`nemotron-3-ultra-550b-a55b` 와 `nemotron-3-ultra-550b-a55b:free` 는 다른 모델이다.** 접미사를 떼면 유료($0.5/MTok input)로 간다.
3. **provider 가 바뀌면 다른 경로다.** `kilo/…` 와 `openrouter/…` 는 같은 모델이라도 별개.
4. **모델마다 출력 상한이 제각각**이다(8192 ~ 460,800). 하나의 프롬프트가 어떤 모델에선 잘리고 어떤 모델에선 통과한다.
5. **응답이 JSON 이 아니라 NDJSON** 다. 스크립트로 파싱할 땐 `type=="text"` 필터를 걸어야 한다.

---

## 4. 재현 명령 (그대로 복사해 실행 가능)

```bash
# 등록 여부 확인
opencode models | grep -qxF "kilo/nvidia/nemotron-3.5-lightning:free" && echo REGISTERED

# 직접 호출 (응답 텍스트 추출)
opencode run -m kilo/nvidia/nemotron-3.5-lightning:free --format json "한 단어로 대답: PONG" \
  | grep '"type":"text"' \
  | python3 -c "import sys,json; print(''.join(json.loads(l)['part']['text'] for l in sys.stdin if json.loads(l)['type']=='text'))"

# 표시명 확인 (카탈로그)
curl -s https://models.dev/api.json \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['kilo']['models']; print(m['nvidia/nemotron-3.5-lightning:free']['name'])"
```

---

## 5. 출처

| 항목 | 출처 | 확인 방식 |
|---|---|---|
| `ctrl+x m` 키바인딩, variants 순환 | `https://opencode.ai/docs/tui/` | HTTP 200, 105,330B 페치 후 텍스트 추출 |
| 모델 ID · 표시명 · `cost` · `limit` | `https://models.dev/api.json` | HTTP 200, 5,664,894B 페치 후 `kilo.models` 파싱 |
| 5개 모델 실제 응답 | `opencode run` | 2026-10-15 실측 5/5 성공 |
| Kilo `:free` 개수(16/396) | `opencode models` | `grep -c` |
