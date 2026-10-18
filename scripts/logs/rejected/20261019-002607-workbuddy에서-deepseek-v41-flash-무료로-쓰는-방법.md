---
title: "WorkBuddy에서 DeepSeek V4.1 Flash 무료로 쓰는 방법"
description: "테스트"
draft: false
---

DeepSeek가 2026년 10월 17일 공개한 [DeepSeek-V4.1-Flash-1017](https://api-docs.deepseek.com/news/news261017)은 공식 릴리스 노트에서 "이전 버전보다 벤치마크 성능이 좋아지고, 작업 완료가 빨라지고, 출력이 짧아졌다"고 소개된 모델입니다. 공식 API 문서 기준으로 컨텍스트 **1M 토큰**, 최대 출력 **384K 토큰**, 이미지 입력을 지원하고, 모델 가중치까지 공개돼 있습니다([Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017) · [ModelScope](https://modelscope.cn/models/deepseek-ai/DeepSeek-V4.1-Flash-1017)).

문제는 이 모델을 API로 직접 부르면 유료라는 점입니다. 100만 토큰당 입력 $0.15, 출력 $0.60(오프피크 기준)이 붙습니다. 결제 수단을 넣지 않고 먼저 써 보고 싶을 때 지금 쓸 수 있는 경로가 텐센트 **WorkBuddy 글로벌 버전**입니다. WorkBuddy Intl은 2026년 10월 17일 공식 계정에 "새 DeepSeek이 나왔고 WorkBuddy Intl도 최신으로 올라갔으며 **10월 31일까지 무료**"라고 알렸습니다([@WorkBuddy_AI](https://x.com/WorkBuddy_AI)).

이 글은 ① 무료와 유료의 경계, ② 설치·로그인·모델 선택까지의 실제 클릭 순서, ③ 실제로 걸리는 한도, ④ 10월 31일 이후를 위한 API 단가표와 직접 연결 방법 순서로 정리했습니다. 기준 시각은 2026년 10월 18일입니다.

## 1. 무엇이 무료인가 — 무료는 "앱 안의 호출"까지입니다

무료라고 뭉뚱그리면 안 되는 지점이 하나 있습니다. 무료인 것은 **WorkBuddy 글로벌 버전 앱 안에서 이 모델로 작업을 돌리는 것**이고, API 키로 호출하는 경로는 프로모션과 무관하게 요금이 붙습니다.

| 구분 | 요금 | 근거 |
| --- | --- | --- |
| WorkBuddy 글로벌 버전에서 DeepSeek V4.1 Flash 선택 | 프로모션 기간 **크레딧 차감 0** | [WorkBuddy Intl 공지](https://x.com/WorkBuddy_AI) · 프로모션 안내 |
| WorkBuddy에 내 API 키로 연결 | DeepSeek API 단가 그대로 | [DeepSeek 공식 연동 문서](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy) |
| DeepSeek API 직접 호출 | 100만 토큰당 입력 $0.15 · 출력 $0.60 (오프피크) | [DeepSeek 공식 요금표](https://api-docs.deepseek.com/quick_start/pricing) |

앱 안에서 쓰는 만큼은 API 키 발급도, 제공자 등록도, 결제 정보 입력도 필요하지 않습니다. 공식 릴리스 노트는 이 모델이 DeepSeek 자체 웹사이트·앱·API에 함께 올라갔다고 밝히고 있지만, 이 글에서 확인한 무료 조건은 WorkBuddy 글로벌 버전 기준입니다.

한 가지 더: 프로모션은 **글로벌 버전에만** 적용됩니다. 중국 버전 클라이언트는 별도 규칙을 씁니다.

## 2. 설치 — macOS 12 이상, Windows 10 1809 이상

[공식 사이트](https://www.workbuddy.ai/)는 "Mac 또는 Windows용을 내려받아 무료로 시작하고, 작업을 한 문장으로 설명하면 완성된 보고서·발표자료·스프레드시트를 돌려받는다"고 제품을 소개합니다. 공식 문서가 밝힌 요구 사항은 다음과 같습니다.

| 항목 | macOS | Windows |
| --- | --- | --- |
| OS | macOS 12 (Monterey) 이상 | Windows 10 (1809 이상) 또는 Windows 11, 64비트(x64·ARM64) |
| CPU | Apple Silicon · Intel 모두 | x64 · ARM64 |
| 메모리 | 4GB 이상 (8GB 권장) | 4GB 이상 (8GB 권장) |
| 디스크 | 500MB 이상 여유 | 500MB 이상 여유 |

설치 순서는 짧습니다.

1. 공식 사이트에서 자기 OS용 설치 파일을 받습니다. macOS는 `.dmg`, Windows는 `.exe`입니다.
2. macOS는 디스크 이미지를 열어 WorkBuddy 아이콘을 응용 프로그램 폴더로 끌어다 놓고, Windows는 설치 마법사를 따라갑니다.
3. 첫 실행 때 보안 경고가 뜨면 macOS는 **시스템 설정 → 개인정보 보호 및 보안 → 확인 없이 열기**, Windows는 SmartScreen의 **추가 정보 → 실행**을 누릅니다. 공식 문서가 안내하는 정상 절차입니다.

로그인은 **Google 또는 GitHub OAuth**로 합니다([Mac 설치 문서](https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Installation-Mac-Guide) · [Windows 설치 문서](https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Installation-Win-Guide)). 가입 절차가 따로 없고, 로컬 파일 작업을 시키려면 처음에 접근을 허용할 폴더를 지정하게 됩니다.

## 3. 모델 선택 — 첫 대화를 한 번 보낸 뒤 입력창의 모델명을 클릭

WorkBuddy는 [공식 문서](https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model)에서 "작업을 한 문장으로 설명하면 동료처럼 스스로 계획하고 실행해 검증 가능한 결과물을 내놓는 데스크톱 AI 에이전트"로 설명됩니다. 모델은 **설정 → 모델** 페이지에서 관리하고, 대화창에서는 입력창의 모델 이름을 클릭해 바꿉니다.

1. 새 작업을 만들어 **첫 메시지를 한 번 보냅니다.** 모델 선택 패널은 첫 메시지를 보낸 뒤에 나타납니다.
2. 입력창에 표시된 모델 이름(예: `Kimi-K3 ▾`)을 클릭해 모델 목록을 엽니다.
3. 목록에서 **DeepSeek V4.1 Flash**를 고릅니다.
4. 패널에 **무료 또는 0 크레딧**으로 표시되는지 확인하고 그대로 대화를 시작합니다.

잔액과 소모 내역은 **우측 상단 아바타 → Profile → Usage**에서 확인합니다([크레딧 문서](https://www.workbuddy.ai/docs/workbuddy/credits)). 크레딧은 모델 등급·작업 복잡도·컨텍스트 길이에 따라 다르게 차감되는 통합 단위이고, 프로모션 기간에는 이 모델의 차감률이 0입니다. 무료 플랜도 매월 100 크레딧이 지급되며, Pro는 월 $10(신규 첫 달 $7)에 기본 1,000 + 보너스 1,000으로 월 2,000 크레딧입니다([요금 문서](https://www.workbuddy.ai/docs/workbuddy/pricing)).

## 4. 실제로 걸리는 한도 — 앱 300K, API 1M, 무료 구간은 계정당 약 2억 토큰

프로모션 무료 사용에는 상한이 있습니다. 계정당 **약 2억 토큰(캐시 포함)**을 쓰면 모델이 일시 정지되고, 안내에 표시된 리셋 시각까지 기다려야 합니다. 이 수치는 WorkBuddy 공식 문서가 아니라 프로모션을 정리한 [안내 페이지](https://www.aipromonow.com/en/promos/workbuddy-hy4-deepseek-flash-free-sep)에서 확인한 값이므로, 실제로는 앱의 모델 패널에 뜨는 표시가 최종 기준입니다.

| 항목 | 값 | 출처 |
| --- | --- | --- |
| 앱(글로벌 버전)에서의 컨텍스트 | 약 300K 토큰 | 프로모션 안내 페이지 |
| DeepSeek API 컨텍스트 | **1M 토큰** | [공식 API 문서](https://api-docs.deepseek.com/quick_start/pricing) |
| DeepSeek API 최대 출력 | **384K 토큰** | 공식 API 문서 |
| 무료 사용 상한 | 계정당 약 2억 토큰(캐시 포함) 후 일시 정지 | 프로모션 안내 페이지 |
| 프로모션 종료 | 2026년 10월 31일 (시각·시간대는 미공지) | WorkBuddy Intl 공지 · 안내 페이지 |
| API 동시성 한도 | 2,500 | 공식 API 문서 |

즉 앱에서 무료로 쓰는 동안은 같은 모델을 API로 부를 때보다 컨텍스트가 좁습니다. 긴 문서 여러 개를 한 번에 물리는 작업은 앱보다 API 쪽이 유리하고, 짧은 실험과 반복 작업은 앱 쪽이 유리합니다.

## 5. 10월 31일 이후 — API 단가표와 시간대

프로모션이 끝나면 같은 모델을 API로 부르는 경로가 남습니다. 공식 요금표를 그대로 옮기면 다음과 같습니다(100만 토큰당).

| 구분 | 오프피크 | 피크 |
| --- | --- | --- |
| 입력 (캐시 히트) | $0.003 | $0.006 |
| 입력 (캐시 미스) | $0.15 | $0.30 |
| 출력 | $0.60 | $1.20 |

읽는 법은 세 가지입니다.

- **피크는 UTC 기준 01:00–04:00과 06:00–10:00**(월–금, 중국 공휴일 제외)이고, 그 외 전 시간과 주말·공휴일은 전부 오프피크입니다. 오프피크는 피크의 절반 가격입니다. 한국 시간(UTC+9)으로 환산하면 평일 10:00–13:00과 15:00–19:00이 피크입니다.
- **캐시 히트는 캐시 미스보다 50배 쌉니다**($0.15 ÷ $0.003). 같은 문서를 반복해서 물리는 작업은 캐시가 붙어 비용이 급감합니다.
- 예를 들어 캐시 미스 입력 100만 토큰 + 출력 10만 토큰이면 오프피크 **$0.21**, 피크 **$0.42**입니다. 프로모션 무료 한도인 2억 토큰을 입력 캐시 미스로만 계산하면 오프피크 기준 약 **$30**어치입니다.

기존 이름 `deepseek-v4-flash`와 `deepseek-v4-flash-vision-exp`는 아직 호출이 받아들여지지만, 해당 모델은 은퇴했고 요청은 V4.1-Flash-1017로 처리되며 Flash 요금으로 청구됩니다. API 키는 [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)에서 발급합니다.

## 6. API 키로 WorkBuddy에 직접 붙이는 방법

프로모션이 끝난 뒤에도 같은 앱에서 계속 쓰고 싶다면, 공식 문서가 두 가지 경로를 안내합니다.

**UI 경로(권장).** **설정 → 모델**에서 모델을 추가합니다. 제공자 프리셋에서 DeepSeek을 고르면 URL과 모델 목록, 기능 플래그(툴 호출·이미지 입력·추론 모드)가 자동으로 채워지고, API 키만 붙여넣고 저장하면 끝입니다. 예전에 `~/.codebuddy/models.json` 파일로 등록해 둔 모델도 UI에서 그대로 관리할 수 있습니다.

**파일 경로.** [DeepSeek 공식 연동 문서](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy)는 사용자 단위 `C:\Users\<사용자>\.codebuddy\models.json` 또는 프로젝트 단위 `<프로젝트>\.codebuddy\models.json`을 안내합니다.

```json
{
  "models": [
    {
      "id": "deepseek-flash",
      "name": "DeepSeek Flash",
      "vendor": "DeepSeek",
      "url": "https://api.deepseek.com/v1/chat/completions",
      "apiKey": "${DEEPSEEK_API_KEY}",
      "maxInputTokens": 128000,
      "maxOutputTokens": 8192,
      "supportsToolCall": true,
      "supportsImages": true
    }
  ],
  "availableModels": ["deepseek-flash"]
}
```

파일은 **UTF-8(BOM 없이)**로 저장하고 앱을 완전히 종료했다가 다시 열면, 모델 선택기에 `DeepSeek Flash`가 나타납니다. 안 될 때 공식 문서가 짚는 원인은 세 가지입니다 — 401은 키 값 오류, 404는 모델 id가 `deepseek-flash`가 아닌 경우, "로컬 모델 구성 파일을 읽지 못함"은 파일이 BOM으로 저장된 경우입니다. 예시의 토큰 값(128000/8192)은 보수적으로 잡힌 값이라, 공식 API 기준 1M·384K까지 여유가 있습니다.

## 7. 주의할 점

- **글로벌 버전 한정입니다.** 중국 버전 클라이언트에는 이 무료 프로모션이 없습니다.
- **종료 시각이 공지되지 않았습니다.** 10월 31일이라는 날짜만 안내돼 있어, 그날 언제까지인지는 앱 안내로 확인해야 합니다.
- **크레딧이 0이 되면 무료 모델도 멈춘다고 안내돼 있습니다.** 프로모션 안내 페이지는 잔액이 바닥나면 무료 모델 호출도 막히므로 소액 잔액을 유지하라고 적고 있습니다.
- **캡에 닿으면 다른 모델로 갈아타거나 리셋을 기다려야 합니다.** 무료 구간에서 막혔을 때 앱이 멈추는 게 아니라 해당 모델만 일시 정지됩니다.
- **모델 목록은 고정이 아닙니다.** 공식 문서는 사용 가능한 내장 모델이 제품 버전·계정 유형·서비스 상황에 따라 달라질 수 있다고 밝히고 있습니다.
- **사내 코드나 고객 정보처럼 외부로 나가면 곤란한 자료**는 공식 문서가 안내하는 로컬 배포 경로(예: Ollama, 로컬 11434 포트)를 쓰는 편이 안전합니다.

## 마무리 — 오늘 30분 안에 끝내는 무료 체험

1. **설치 (5분)** — [workbuddy.ai](https://www.workbuddy.ai/)에서 글로벌 버전을 받아 로그인합니다. macOS 12 이상 또는 Windows 10 1809 이상이면 됩니다.
2. **모델 선택 (5분)** — 새 작업에서 첫 메시지를 한 번 보낸 뒤 입력창의 모델명을 클릭하고 **DeepSeek V4.1 Flash**를 고릅니다. 무료 또는 0 크레딧 표시를 확인합니다.
3. **한도 확인 (2분)** — 우측 상단 아바타 → Profile → Usage에서 잔액과 소모 내역을 봅니다. 잔액이 0이면 무료 모델도 멈춘다는 안내를 기억해 둡니다.
4. **10월 31일 대비 (선택)** — [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)에서 키를 발급해 **설정 → 모델**에 등록해 둡니다. 급한 작업이 아니라면 평일 낮 시간대(UTC 피크)를 피해 호출하면 같은 모델을 절반 가격에 씁니다.

무료 구간은 앱에서, 본격적인 대량 작업은 API에서 — 이렇게 나눠 쓰면 10월 31일 이후에도 같은 모델을 이어서 쓸 수 있습니다. 무료 모델 목록과 다른 경로가 궁금하면 [무료 모델](/posts/free-models) 페이지와 [OpenCode CLI 사용 방법](https://emdash.aikorea24.kr/posts/opencode-cli-guide), [OpenCode에 무료 모델 연결하기](https://emdash.aikorea24.kr/posts/openrouter-free-models-opencode) 글을 함께 보세요.
