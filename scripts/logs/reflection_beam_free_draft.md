Beam Free는 Reflection이 공개한 코딩·에이전트용 추론 모델의 무료판입니다. 2026년 10월 17일 기준으로 Kilo 게이트웨이와 OpenCode Zen 두 곳의 모델 목록에 올라와 있고, 두 목록 모두 가격이 0으로 표기됩니다. 컨텍스트 길이는 1,048,576 토큰(약 100만), 한 번에 생성하는 최대 길이는 131,072 토큰입니다. 다만 목록 설명에 프롬프트와 생성 결과가 제공자 쪽에 보관되어 서비스 개선에 쓰일 수 있다고 적혀 있습니다. 사내 코드나 고객 데이터에는 권하지 않습니다.

이 글은 무료인지 직접 확인하는 방법, 설치, 두 경로로 붙이는 방법, 무료 조건과 한계, 실측 결과 순서로 정리했습니다. 아래 수치는 전부 2026년 10월 17일에 목록 API와 실제 호출로 확인한 값입니다.

## 1. 무료인지 먼저 확인합니다 — 목록 API 두 곳

무료라고 알려진 모델은 목록에서 직접 보는 편이 가장 빠릅니다. [Kilo 게이트웨이 모델 목록](https://api.kilo.ai/api/gateway/models)은 인증 키 없이 조회됩니다.

```bash
curl -s https://api.kilo.ai/api/gateway/models | python3 -c "
import json, sys
for r in json.load(sys.stdin)['data']:
    if r['id'] == 'reflection/beam-free':
        print(r['context_length'], r['pricing'])"
```

입력·출력 단가가 `0.000000000000` 으로 나오면 무료 경로입니다. 같은 모델이 [OpenCode Zen 모델 목록](https://opencode.ai/zen/v1/models)에는 `beam-free` 이름으로 있습니다.

```bash
curl -s https://opencode.ai/zen/v1/models | python3 -c "
import json, sys
print([r['id'] for r in json.load(sys.stdin)['data'] if 'beam' in r['id']])"
```

| 확인 항목 | Kilo 게이트웨이 | OpenCode Zen |
| --- | --- | --- |
| 모델 id | `reflection/beam-free` | `beam-free` |
| 목록 등록 시각 | 2025-08-26 (게이트웨이 기준) | 2026-10-17 10:32 UTC |
| 가격 | 입력·출력 0 | 가격 필드 없음 — id 끝 `-free` 로 무료 표기 |
| 컨텍스트 | 1,048,576 토큰 | 목록에 미표기 |
| 한 번 생성 최대 | 131,072 토큰 | 목록에 미표기 |

Zen 목록은 가격 필드를 주지 않고 모델 id 끝에 `-free` 를 붙여 무료 모델을 구분합니다. 실제로 Zen 목록의 무료 모델은 `space-bunny-free`, `mimo-v2.6-flash-free`, `longcat-2.5-preview-free` 처럼 모두 같은 규칙을 씁니다.

## 2. 설치 — 한 줄입니다

[공식 설치 스크립트](https://opencode.ai/v2/install)를 쓰면 터미널 한 줄로 끝납니다.

```bash
curl -fsSL https://opencode.ai/v2/install | bash
```

OpenCode는 V1과 V2 두 계열이 병행되고 설치 주소가 다릅니다. 최신 라인을 쓰려면 위의 v2 주소를 쓰면 됩니다. 설치 후에는 버전을 확인합니다.

```bash
opencode --version
opencode upgrade
```

npm으로 설치할 때 패키지 이름은 `opencode-ai` 입니다. `npm install -g opencode` 는 존재하지 않는 패키지라 실패합니다.

## 3. 두 경로로 붙입니다 — Kilo 와 Zen

명령줄에서 모델을 지정해 한 번씩 호출해 봤습니다.

```bash
opencode run -m kilo/reflection/beam-free "1+1의 답만 숫자로 출력하세요."
opencode run -m opencode/beam-free "1+1의 답만 숫자로 출력하세요."
```

모델 id 앞의 `kilo/` 와 `opencode/` 는 제공자 접두사입니다. Kilo 경로는 게이트웨이 주소를 한 번 등록하면 목록이 잡히고, Zen 경로는 설치 직후 기본으로 들어 있습니다. 대화형으로 쓰려면 터미널 UI에서 `/models` 를 입력해 이름에 `-free` 가 붙은 모델을 고르면 됩니다. Zen 쪽 모델 구성을 확인하려면 [Zen 모델 문서](https://opencode.ai/v2/docs/console/models/)를 보면 됩니다.

## 4. 무료 조건과 한계

| 항목 | 값 (2026-10-17 목록 기준) |
| --- | --- |
| 가격 | 입력·출력 모두 0 |
| 컨텍스트 | 1,048,576 토큰 |
| 한 번 생성 최대 | 131,072 토큰 |
| 입력 형식 | 텍스트만 |
| 지원 파라미터 | `max_tokens`, `temperature`, `tools`, `reasoning` |
| 데이터 보관 | 프롬프트·생성이 보관되어 학습에 쓰일 수 있음 |

가장 눈여겨볼 항목은 마지막 줄입니다. 목록 설명에 "프롬프트와 생성 결과가 보관되어 제공자의 서비스 개선과 학습에 사용될 수 있다"고 적혀 있고, 제로 리텐션(Zero Data Retention)은 제공되지 않는다고 명시돼 있습니다. 공개 저장소 코드나 학습용 예제에는 문제가 없지만, 사내 코드·고객 데이터·개인정보는 넣지 않는 편이 맞습니다. 같은 설명에 이 모델이 [Vercel AI Gateway](https://vercel.com/ai-gateway)를 통해 무료로 제공된다고 적혀 있습니다.

## 5. `-free` 표기를 떼면 유료 모델입니다

같은 이름의 유료판이 따로 있습니다. `reflection/beam-1.0-501b-a23b` 는 컨텍스트는 같지만 가격이 붙습니다.

| 모델 id | 입력 100만 토큰 | 출력 100만 토큰 | 비고 |
| --- | --- | --- | --- |
| `reflection/beam-free` | 0 | 0 | 무료판 |
| `reflection/beam-1.0-501b-a23b` | $0.25 | $1.00 | 501B 총 파라미터·23B 활성 MoE |

가격은 목록의 토큰당 단가(입력 0.00000025, 출력 0.000001)를 100만 토큰 기준으로 환산한 값입니다. 무료 경로를 `:free` 접미사로 구분하는 모델도 많습니다. 같은 목록의 `poolside/laguna-s-2.1:free` 는 접미사를 떼면 다른 라우트를 가리키므로, 무료로 쓰려면 접미사까지 그대로 적어야 합니다. 유료판 쪽 모델 정보는 [OpenRouter 모델 페이지](https://openrouter.ai/reflection/beam-1.0-501b-a23b)에 정리돼 있고, 무료 경로 전체 목록은 [kilo.ai](https://kilo.ai/)에서 확인할 수 있습니다.

## 6. AIK24 실측 결과

검증일은 2026년 10월 17일이고, 방법은 응답 확인용 짧은 프롬프트를 실제 명령줄로 한 번씩 호출하는 방식입니다.

| 호출 | 응답 | 지연 | 판정 |
| --- | --- | --- | --- |
| `kilo/reflection/beam-free` | `2` | 2.7초 | 정상 |
| `opencode/beam-free` | `2` | 1.0초 | 정상 |

프롬프트는 "1+1의 답만 숫자로 출력하세요." 였고 두 경로 모두 정답을 반환했습니다. 같은 날 무료 모델 목록을 다시 수집한 결과 39개 중 신규 3건·제거 2건이 있었고, Beam 무료판은 Kilo 목록에서 신규로 잡혔습니다.

아직 하지 않은 검증도 적어둡니다. 코드 작성과 수정 능력을 재는 내부 12문항 평가에는 이 모델이 아직 포함되지 않았습니다. 품질 판단은 다음 평가 차례에 몰아서 하려고 합니다. 지금 단계에서 말할 수 있는 것은 "무료로 호출되고 정상 응답한다"까지입니다.

## 마무리 — 오늘 30분 안에 할 3단계

1. 무료 확인: [Kilo 모델 목록](https://api.kilo.ai/api/gateway/models)에서 `reflection/beam-free` 의 입력·출력 단가가 0인지 봅니다.
2. 한 번 호출: `opencode run -m kilo/reflection/beam-free "1+1의 답만 숫자로 출력하세요."` 를 실행해 응답이 오는지 확인합니다.
3. 보낼 것과 보내지 않을 것 정하기: 공개 코드와 학습 예제는 괜찮고, 사내 코드·고객 데이터·개인정보는 넣지 않습니다. 계속 쓸 모델이라면 Zen 경로(`opencode/beam-free`)도 같은 프롬프트로 호출해 지연을 비교합니다.
