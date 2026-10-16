터미널에서 AI에게 코드를 맡기는 도구가 개발 흐름의 한 축이 됐습니다. 그중 **OpenCode**는 2025년 4월 30일 공개된 오픈소스 코딩 에이전트입니다. 2026년 10월 16일 기준 GitHub 스타 21만 개(214,019)를 넘겼고, MIT 라이선스라서 회사에서도 제약 없이 쓸 수 있습니다. 저장소 주소는 최근 `sst/opencode`에서 `anomalyco/opencode`로 옮겨졌습니다.

이름만 들어보고 "AI 구독료를 따로 내야 하는 도구 아닌가" 하고 지나치는 분들이 많습니다. **결론부터 적으면 그렇지 않습니다.** 이 글을 준비하면서 한 개발자 환경의 OpenCode 세션 623건을 직접 집계했는데, 그중 **564건(90.5%)이 무료 모델로 실행**됐습니다. 유료 모델을 쓴 세션은 59건이었습니다.

이 글은 설치 → 무료 API 키 발급 → 첫 실행과 모델 선택 → 무료 모델로 충분한지에 대한 실측 → 자주 쓰는 명령 → 비용 확인 순서로 정리했습니다. 30분이면 무료 세팅을 끝낼 수 있습니다.

## 1. 설치 — 3분이면 끝납니다

터미널 한 줄이면 설치가 끝납니다.

```bash
curl -fsSL https://opencode.ai/v2/install | bash
```

주의할 점이 하나 있습니다. OpenCode는 **V1과 V2 두 계열이 병행**되고 있고 설치 주소가 다릅니다.

| 설치 주소 | 설치되는 계열 | 비고 |
| --- | --- | --- |
| `https://opencode.ai/install` | V1 계열 (1.x) | 문서 대부분이 이 계열 기준 |
| `https://opencode.ai/v2/install` | V2 계열 (2.x) | 현재 개발이 진행되는 라인 |

설치 후 버전을 확인하고, 업데이트는 내장 명령으로 합니다.

```bash
opencode --version
opencode upgrade
```

npm으로도 설치할 수 있지만 **패키지 이름이 `opencode-ai`** 입니다. `npm install -g opencode`는 존재하지 않는 패키지라 실패합니다. 또 npm 쪽은 V1 계열(레지스트리 기준 최신 1.19.2)이므로, 최신 라인을 쓰려면 위의 curl 설치가 낫습니다.

## 2. 무료 API 키 — 어디서 받고 어디에 넣나

OpenCode 자체는 무료이고, 비용은 **어떤 모델을 연결하느냐**에서만 발생합니다. 무료로 시작하는 경로는 두 갈래입니다.

**(1) 설치 직후 바로 — 내장 무료 모델.** OpenCode에는 공식 게이트웨이(OpenCode Zen)가 내장돼 있어서, 모델 선택기에서 이름이 `-free`로 끝나는 모델을 고르면 별도 키 설정 없이 바로 대화가 됩니다. 실측 환경도 이 경로로 117개 세션을 돌렸습니다. 유료 모델까지 쓰려면 Zen 계정에 잔액을 충전하는 별도 절차가 있습니다.

**(2) 무료 티어가 있는 외부 제공자.** 아래 페이지에서 계정을 만들고 API 키를 발급받습니다.

| 제공자 | 무료로 받는 것 | 키 발급 페이지 | 환경변수 이름 |
| --- | --- | --- | --- |
| OpenRouter | `:free` 접미사 모델 다수 | https://openrouter.ai/keys | `OPENROUTER_API_KEY` |
| Groq | 무료 티어 (빠른 추론) | https://console.groq.com/keys | `GROQ_API_KEY` |
| NVIDIA NIM | 무료 크레딧 | https://build.nvidia.com/ | `NVIDIA_API_KEY` |
| Cerebras | 무료 티어 · 프로모 크레딧 | https://cloud.cerebras.ai/ | `CEREBRAS_API_KEY` |

발급받은 키는 셸에 넣어둡니다.

```bash
echo 'export OPENROUTER_API_KEY="발급받은키"' >> ~/.zshrc
source ~/.zshrc
```

그리고 OpenCode 설정 파일(`~/.config/opencode/opencode.json`)에서 **키 값이 아니라 환경변수를 참조**하게 씁니다.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {
      "options": { "apiKey": "{env:OPENROUTER_API_KEY}" }
    }
  }
}
```

이렇게 하면 설정 파일에 키가 남지 않습니다. 키를 설정 파일이나 코드에 직접 적어두면 실수로 커밋했을 때 그대로 유출됩니다. 여러 제공자를 쓰더라도 방식은 같습니다 — 발급 페이지에서 키를 받고, 환경변수로 넣고, 설정에서는 `{env:...}`로 참조합니다.

## 3. 첫 실행과 모델 선택

```bash
opencode
```

터미널 전체 화면(TUI)으로 열립니다. 모델을 바꾸는 방법은 세 가지입니다.

- **모델 선택 화면**: `ctrl+x`를 누른 뒤 `m` (기본 리더 키 조합)
- **프롬프트에서**: `/model` 입력
- **최근 모델로 빠르게 전환**: `F2`

지금 쓸 수 있는 모델 전체 목록은 터미널에서 확인합니다.

```bash
opencode models
```

**무료 표기가 제공자마다 다르다는 점**이 실수하기 쉬운 지점입니다. OpenCode 내장(Zen) 계열은 `space-bunny-free`처럼 `-free`가 붙고, OpenRouter·Kilo 계열은 `step-5-preview-free:free`처럼 `:free`가 붙습니다. 목록에서 `free`가 들어간 이름을 고르면 됩니다.

## 4. 무료 모델만으로 개발이 되나 — 623세션 실측

결론은 "된다"입니다. 한 개발자 환경의 세션 623건을 집계한 결과입니다.

| 순위 | 모델 | 세션 수 | 비중 |
| --- | --- | --- | --- |
| 1 | `space-bunny-free` | 117 | 19% |
| 2 | `mimo-v2.6-flash-free` | 41 | 7% |
| 3 | `step-5-preview-free` | 31 | 5% |
| — | 무료 모델 합계 | **564** | **90.5%** |
| — | 유료 모델 합계 | 59 | 9.5% |

제공자별로도 무료 경로가 얼마나 쓰이는지가 그대로 드러납니다.

| 제공자 | 세션 수 |
| --- | --- |
| OpenCode Zen (내장) | 272 |
| Kilo | 179 |
| OpenRouter | 95 |
| Upstage | 26 |
| NVIDIA NIM | 26 |
| DeepSeek | 12 |
| Groq | 10 |
| Google AI | 3 |

무료 모델은 실제로 코드 작성·수정·질의응답 루틴을 돌릴 수 있는 수준입니다. 다만 한계도 분명합니다. 무료 티어는 **응답 속도, 요청 수 제한(레이트리밋), 컨텍스트 길이**가 유료보다 좁습니다. 큰 리팩터링이나 긴 파일 여러 개를 한 번에 다루는 작업은 무료 모델에서 끊기거나 느려질 수 있습니다. 그래서 실무에서는 무료 모델로 평소 작업을 돌리고, 어려운 작업만 유료 모델로 올리는 방식이 현실적입니다.

## 5. 자주 쓰는 명령어

| 명령 | 하는 일 |
| --- | --- |
| `opencode` | 터미널 UI로 대화 시작 (가장 많이 쓰는 형태) |
| `opencode run "질문"` | 화면 없이 한 번만 실행하고 결과만 받기 (스크립트·자동화에 유용) |
| `opencode mini` | 최소 인터페이스로 실행 |
| `opencode models` | 사용 가능한 모델 전체 목록 |
| `opencode stats --models` | 모델별 사용량 통계 |
| `opencode session` | 세션 목록·관리 |
| `opencode auth` | 인증 정보 관리 |
| `opencode upgrade` | 최신 버전으로 업데이트 |
| `opencode mcp` | MCP 서버 연결 관리 |
| `opencode plugin` | 플러그인 관리 |

이전 세션을 이어서 쓰는 플래그도 자주 씁니다.

```bash
opencode --continue          # 마지막 세션 이어서
opencode --session <세션ID>  # 특정 세션 이어서
```

## 6. 비용이 새지 않는지 확인하는 습관

무료 모델만 쓴다고 생각했는데 유료 모델이 섞여 들어가면 요금이 나갑니다. OpenCode는 이걸 확인하는 통계 명령을 내장하고 있습니다.

```bash
opencode stats --days 0        # 오늘 사용량
opencode stats --days 7        # 최근 7일
opencode stats --models        # 모델별 사용량
opencode stats --all           # 전체 기간
```

주 단위로 한 번씩 `opencode stats --models`를 보면 무료 모델 비중이 유지되는지 확인할 수 있습니다.

## 7. 이것만은 주의하세요

- **무료 범위는 언제든 바뀝니다.** 제공자가 무료 티어를 조정하면 이름에 `free`가 붙어 있어도 한도가 달라질 수 있습니다. 큰 작업 전에는 제공자 페이지에서 현재 조건을 확인하세요.
- **V1·V2 설치 주소를 섞지 마세요.** 문서와 설치 주소 계열이 다르면 명령이 안 맞을 수 있습니다.
- **npm 패키지 이름은 `opencode-ai`입니다.** `opencode`로 설치하면 실패합니다.
- **키는 절대 설정 파일·코드에 직접 쓰지 마세요.** 환경변수로 넣고 `{env:...}`로 참조하세요.
- **민감한 코드는 모델별 데이터 정책을 확인하세요.** 무료 티어는 입력 데이터를 학습에 쓰는 경우가 있습니다. 사내 코드·고객 정보를 다룰 때는 데이터 정책이 명확한 모델이나 로컬 실행 모델을 고르는 편이 안전합니다.

## 마무리 — 오늘 30분 안에 끝내는 무료 세팅

1. **설치** — `curl -fsSL https://opencode.ai/v2/install | bash` 후 `opencode --version`으로 확인
2. **키 하나 만들기** — https://openrouter.ai/keys 에서 키를 발급해 `~/.zshrc`에 `OPENROUTER_API_KEY`로 export
3. **무료 모델로 첫 대화** — `opencode` 실행 → `ctrl+x` `m`으로 모델 선택 → 이름에 `free`가 붙은 모델 선택 → 바로 질문

여기까지 하면 비용은 0원입니다. 일주일 써보고 손에 맞으면 유료 모델을 하나씩 얹으면 되고, 그 전에 `opencode stats --models`로 무료 비중을 확인하는 습관만 들이면 예상 밖 요금은 거의 나지 않습니다.
