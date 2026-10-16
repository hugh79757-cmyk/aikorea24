Groq는 자체 칩에서 모델을 돌리는 추론 전용 프로바이더입니다. OpenCode에서 쓰려면 API 키 하나만 연결하면 됩니다. 이 글은 2026년 10월 16일 실제 화면과 공식 문서를 확인해 키 발급 → 등록 → 동작 확인 순서로 정리했고, 무료 티어 한도는 공식 문서 표를 그대로 옮겼습니다.

## Groq는 뭔가 — 자체 칩(LPU)으로 추론만 하는 프로바이더

공식 사이트([groq.com](https://groq.com/))는 Groq가 추론(inference)에 특화된 자체 칩 **LPU**를 만들었고, 이후 **LPX**가 NVIDIA의 차세대 GPU와 함께 동작한다고 설명합니다. 모델을 직접 학습해 배포하는 곳이 아니라, 공개된 모델(openai gpt-oss, qwen 등)을 자체 하드웨어에서 빠르게 돌려 주는 쪽입니다.

OpenCode에서는 **커스텀 프로바이더**로 연결합니다. 즉 설정 파일에 키를 넣어야 쓸 수 있는 (b) 경로이고, 모델 선택기에 기본으로 떠 있는 (a) 내장 무료 모델과는 다릅니다.

## 1. 계정 만들기 — 카드 등록 없이

[console.groq.com](https://console.groq.com) 에 접속해 Google · GitHub · 이메일 중 하나로 가입합니다. 카드 등록은 필요하지 않습니다.

## 2. API 키 발급 — 한 번만 보이는 키

[console.groq.com/keys](https://console.groq.com/keys) 로 이동합니다. 로그인 전에는 **Create API Key** 버튼이 비활성화되어 있습니다. 로그인 후 버튼을 누르고 키 이름을 정하면 `gsk_` 로 시작하는 키가 표시됩니다.

이 키는 **생성 직후 한 번만** 표시됩니다. 창을 닫으면 다시 볼 수 없고, 잃어버리면 삭제 후 재발급하는 방법밖에 없습니다.

## 3. 키 등록 — 셸 환경변수 + OpenCode 설정

먼저 셸 설정 파일에 환경변수로 넣습니다. 설정 파일에 키를 직접 쓰지 않기 위한 첫 단계입니다.

```bash
echo 'export GROQ_API_KEY="gsk_..."' >> ~/.zshrc
source ~/.zshrc
```

다음으로 OpenCode 설정 파일 `~/.config/opencode/opencode.json` 에서 키 값 대신 환경변수를 참조하게 합니다.

```json
{
  "provider": {
    "groq": {
      "options": { "apiKey": "{env:GROQ_API_KEY}" }
    }
  }
}
```

이렇게 하면 설정 파일에는 키 문자열이 남지 않습니다. 다른 프로바이더도 같은 방식입니다(`OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `CEREBRAS_API_KEY` …).

## 4. 키가 살아 있는지 확인 — curl 한 줄

설정이 "있어 보이는 것"과 실제로 유효한 것은 다릅니다. 아래 명령으로 모델 목록이 나오면 키가 살아 있습니다.

```bash
curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" | head -c 300
```

응답 헤더에는 남은 한도도 함께 옵니다. 공식 문서 기준으로 `x-ratelimit-limit-requests` 는 항상 **일일 요청 수(RPD)**, `x-ratelimit-limit-tokens` 는 항상 **분당 토큰 수(TPM)** 를 가리킵니다. 429 응답을 받으면 `retry-after` 에 표시된 초만큼 기다리면 됩니다.

## 무료 티어 한도 — 2026년 10월 16일 공식 문서 기준

출처: [console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits). 문서 표기(K)를 그대로 옮겼고, 괄호는 실제 값입니다.

| 모델 | RPM(분당 요청) | RPD(일 요청) | TPM(분당 토큰) | TPD(일 토큰) |
|---|---|---|---|---|
| openai/gpt-oss-120b | 30 | 1K (1,000) | 8K (8,000) | 200K (200,000) |
| openai/gpt-oss-20b | 30 | 1K | 8K | 200K |
| openai/gpt-oss-safeguard-20b | 3 | 1K | 2K | 200K |
| qwen/qwen3.8-27b | 30 | 1K | 8K | 200K |
| meta-llama/llama-prompt-guard-2-22m · 86m | 30 | 14.4K | 15K | 500K |
| whisper-large-v3 · turbo | 20 | 2K | — | — (시간당 음성 7.2K초 · 일 28.8K초) |
| canopylabs/orpheus (TTS) | 10 | 100 | 1.2K | 3.6K |

읽는 법 3가지:

- 한도는 **조직(계정) 단위**로 적용됩니다. 같은 키를 여러 도구에 넣어도 합산됩니다.
- **캐시로 처리된 토큰은 한도에 포함되지 않습니다.**
- RPM · TPM · RPD · TPD 중 **먼저 닿는 쪽**이 그때의 제한입니다. 예를 들어 30 RPM · 8K TPM이면 1분에 30번을 채우든 8,000 토큰을 채우든 그 시점에 막힙니다.

gpt-oss-120b 기준으로 하루 1,000 요청 · 20만 토큰이므로 개인 개발과 짧은 실험에는 충분하고, 대량 배치에는 부족합니다.

## 주의사항

- 키는 발급 때 한 번만 보입니다. 복사하기 전에 창을 닫으면 다시 볼 수 없습니다.
- 키를 코드 · 설정 파일 · 깃 저장소에 직접 쓰지 않습니다. 환경변수로 넣습니다.
- 키가 유출된 것 같으면 [콘솔의 API Keys 페이지](https://console.groq.com/keys)에서 해당 키를 삭제하고 새로 발급합니다.
- 무료 티어 한도는 바뀔 수 있습니다. 큰 작업 전에는 위 표의 출처 페이지에서 현재 값을 확인합니다.

## 마무리 — 오늘 30분 안에 끝내는 무료 API 연결

1. **키 발급 (5분)** — [console.groq.com/keys](https://console.groq.com/keys) 에서 키를 만들고 즉시 복사합니다.
2. **등록 (5분)** — `~/.zshrc` 에 `GROQ_API_KEY` 를 export 하고, `opencode.json` 에 `{env:GROQ_API_KEY}` 를 넣습니다.
3. **검증 (1분)** — 4단계의 curl 을 실행해 모델 목록이 나오는지 확인합니다. 여기까지 되면 OpenCode 모델 선택기에서 Groq 모델을 고를 수 있습니다.

설치부터 첫 대화까지 전체 흐름이 필요하면 [OpenCode CLI 사용 방법: 설치부터 무료 모델 실행까지](https://emdash.aikorea24.kr/posts/opencode-cli-guide) 글을 먼저 보세요.
