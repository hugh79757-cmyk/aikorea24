OpenCode에 무료 모델을 붙이는 방법은 한 가지가 아닙니다. 이 글은 그중 **OpenRouter**를 골라, 키 발급부터 연결, 실제 응답이 오는 것까지 순서대로 확인한 기록입니다. OpenRouter는 여러 회사의 모델을 하나의 API로 중계하는 서비스이고, 2026년 10월 16일 조회 기준 카탈로그 465개 중 15개가 `:free`(무료) 모델입니다. 아래 수치는 전부 같은 날 직접 조회하거나 호출해서 확인한 값입니다.

## 1. OpenRouter로 무엇을 얻나 — 모델 하나가 아니라 목록

보통 무료 모델은 제공자마다 따로 가입해야 합니다. OpenRouter는 그 반대로, **키 하나로 여러 제공자의 모델을 골라 씁니다.** 요청 형식도 OpenAI와 같아서(`/chat/completions`), 도구 쪽에서 별도 지원이 필요하지 않습니다.

- 카탈로그: 전체 465개 모델 (2026년 10월 16일 조회)
- 그중 무료: **15개** — 모델 이름 끝에 `:free` 가 붙습니다
- 무료 모델도 유료 모델과 같은 API로 호출되고, 실제 응답까지 확인했습니다

## 2. 지금 쓸 수 있는 무료 모델 15개

`https://openrouter.ai/api/v1/models` 를 직접 조회해 뽑은 목록입니다. 뒤 숫자는 한 번에 넣을 수 있는 문맥 길이(토큰)입니다.

| 모델 | 문맥 | 성격 |
|---|---|---|
| thinkingmachines/inkling:free | 1,048,576 | 문맥 최대 |
| thinkingmachines/inkling-small:free | 1,048,576 | 문맥 최대 |
| nvidia/nemotron-3.5-super-vl:free | 1,000,000 | 범용·이미지 입력 |
| nvidia/nemotron-3.5-lightning:free | 1,000,000 | 경량·빠른 응답 |
| nvidia/nemotron-3-ultra-550b-a55b:free | 1,000,000 | 대형 |
| dots-studio/dots-3-note-preview:free | 512,000 | 문서 요약 |
| poolside/laguna-s-2.1:free | 262,144 | 코딩 |
| poolside/laguna-xs-2.1:free | 262,144 | 코딩·경량 |
| google/gemma-4-31b-it:free | 262,144 | 범용 |
| google/gemma-4-26b-a4b-it:free | 262,144 | 범용·경량 |
| nvidia/nemotron-3-super-120b-a12b:free | 262,144 | 범용 |
| cohere/north-mini-code:free | 256,000 | 코딩 |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | 256,000 | 추론 |
| nvidia/nemotron-3.5-content-safety:free | 128,000 | 유해 표현 분류 |
| liquid/lfm-2.5-2.6b:free | 65,536 | 초경량 |

목록은 [openrouter.ai/models](https://openrouter.ai/models) 에서 언제든 다시 볼 수 있습니다. 무료 모델은 제공자가 바뀌면 사라지거나 이름이 바뀌므로, **이 표는 2026년 10월 16일 기준**으로 읽어야 합니다.

## 3. 키 발급 — 5분

1. [openrouter.ai](https://openrouter.ai) 에 접속해 로그인합니다. 구글 계정으로 바로 됩니다.
2. [openrouter.ai/keys](https://openrouter.ai/keys) 에서 **Create Key** 를 누릅니다.
3. 만들어진 키를 복사합니다. `sk-or-v1-` 로 시작합니다.

무료 모델만 쓸 생각이라면 결제 정보를 넣지 않아도 됩니다. 실제로 크레딧이 없는 계정으로 무료 모델을 호출해 **응답을 받았고, 과금은 0으로 기록**됐습니다(뒤 5장에서 다시 확인합니다).

## 4. OpenCode에 연결 — 손으로 설정 파일을 고치지 않는다

OpenCode 2.0은 통합(integration)을 대화형으로 연결합니다. 설정 파일을 직접 편집하는 방법도 있지만, 일반적인 경로는 다음입니다.

1. OpenCode를 실행하고 `/connect` 를 입력합니다.
2. `Connect an integration` 목록이 뜨면 **openrouter** 를 검색해 선택합니다.
3. `API key` 를 붙여넣고 Enter를 누릅니다.

터미널에서 바로 하려면 같은 일을 명령으로 합니다.

```bash
opencode auth login
```

연결된 항목은 다음으로 확인합니다. 키 값은 표시되지 않고 이름과 상태만 나옵니다.

```bash
opencode auth list
```

```
DeepSeek          DeepSeek          stored
StepFun (Global)  StepFun (Global)  stored
```

마지막으로 모델 목록에 무료 모델이 보이는지 확인합니다. OpenCode의 모델 목록에는 OpenRouter 모델이 `openrouter/<모델명>` 형태로 들어오고, 실제로 `openrouter/nvidia/nemotron-3.5-super-vl:free` 가 사용 가능(active) 상태로 노출되는 것을 확인했습니다.

## 5. 응답이 오는지 확인 — 여기까지 해야 끝난다

키를 등록했다는 것과 모델이 답한다는 것은 다른 문제입니다. 두 번 확인합니다.

**1) 키와 한도 상태 보기**

```bash
curl -s https://openrouter.ai/api/v1/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

무료 계정에서 실제로 돌려본 응답의 핵심 부분입니다.

```json
"is_free_tier": true,
"usage": 0.0000004,
"free_model_daily_requests": { "used": 16, "limit": 50, "remaining": 34 }
```

**2) 실제로 답을 받아보기**

```bash
curl -s https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3.5-super-vl:free",
       "messages":[{"role":"user","content":"한국어로 연결 성공이라고만 답하세요."}],
       "max_tokens":400}'
```

이 요청은 실제로 `200` 응답과 함께 `연결 성공` 이라는 본문을 돌려줬고, 사용량 기록의 비용은 `0` 이었습니다.

### 여기서 두 번 걸렸습니다 — 같은 실수를 피하려면

**① 본문이 비어 보이면 `max_tokens` 를 키웁니다.** 최신 무료 모델 상당수는 답하기 전에 속으로 생각하는 **추론(reasoning)** 토큰을 씁니다. 이 토큰도 출력 한도에서 빠집니다. 처음에 `max_tokens` 를 32로 주었더니 생각하다가 한도가 끝나서 본문(`content`)이 비어 돌아왔습니다(추론 토큰 32 소모). 400으로 올리니 정상 답변이 왔습니다.

**② 무료 모델은 제공자 쪽이 붐비면 429가 옵니다.** 실측으로 `google/gemma-4-31b-it:free` 호출이 `429 — temporarily rate-limited upstream, please retry shortly` 로 거절됐습니다. 내가 한도를 넘은 게 아니라 **모델을 돌리는 쪽이 바쁜 경우**입니다. 공식 문서도 에러가 두 곳에서 온다고 설명합니다 — OpenRouter의 플랫폼 한도와, 모델 제공자의 과부하. 잠시 뒤 다시 보내거나 다른 무료 모델로 바꾸면 됩니다.

## 6. 한도 — 추측하지 말고 조회한다

무료 모델의 하루 한도는 계정의 크레딧 구매 이력에 따라 달라진다고 [공식 문서](https://openrouter.ai/docs/api-reference/limits)에 적혀 있습니다. 크레딧을 사지 않은 계정 기준으로 **하루 50건**이고, 위에서 본 것처럼 이 값은 키 조회 API가 그대로 알려줍니다: `used 16 / limit 50 / remaining 34`.

내 계정이 지금 몇 건까지 쓸 수 있는지는 추측할 필요 없이 `GET /api/v1/key` 의 `free_model_daily_requests` 를 보면 됩니다. 문서에도 이 필드가 무료 모델 요청을 막는 일일 카운터와 상한이라고 명시돼 있습니다.

또 하나, 문서는 무료 모델에 대해 “속도 제한이 낮고 보통 프로덕션 용도에 적합하지 않다”고 선을 긋습니다. 개인 학습·취미 자동화·도구 실험에는 충분하지만, 서비스에 얹을 생각이면 유료 모델을 함께 두는 편이 낫습니다.

## 주의사항

- **무료 모델 목록은 시점에 따라 달라집니다.** 표의 15개도 2026년 10월 16일 조회 결과입니다. 큰 작업을 시작하기 전에 목록을 다시 확인하세요.
- **429는 두 종류입니다.** 내 한도 초과(하루 50건)와 제공자 과부하. 앞은 시간을 두고, 뒤는 다른 무료 모델로 바꾸는 편이 빠릅니다.
- **키가 노출됐다면 즉시 삭제하고 재발급합니다.** [openrouter.ai/keys](https://openrouter.ai/keys) 에서 해당 키를 지우면 그 키로는 더 이상 요청할 수 없습니다.
- **추론 모델에는 여유 있는 `max_tokens` 를 줍니다.** 위 ①처럼 빈 응답을 받으면 모델이 고장 난 게 아닙니다.

## 마무리 — 오늘 30분 안에 끝내는 무료 모델 연결

1. **키 만들기 (5분)** — [openrouter.ai/keys](https://openrouter.ai/keys) 에서 키를 만들고 복사합니다.
2. **연결하기 (3분)** — OpenCode에서 `/connect` → openrouter → 키 붙여넣기. `opencode auth list` 로 `stored` 상태를 확인합니다.
3. **답 받기 (1분)** — 무료 모델 하나(`nvidia/nemotron-3.5-super-vl:free`)를 골라 아무 질문이나 던집니다. 답이 오면 연결은 끝난 것입니다. 빈 응답이 오면 `max_tokens` 를 400 이상으로 올려 다시 시도합니다.

OpenCode 설치부터 첫 대화까지 전체 흐름이 필요하면 [OpenCode CLI 사용 방법: 설치부터 무료 모델 실행까지](https://emdash.aikorea24.kr/posts/opencode-cli-guide) 를 먼저 보세요.
