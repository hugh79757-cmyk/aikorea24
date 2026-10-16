# EmDash 발행 글 전수 감사 (2026-10-16, PT-aware)

## 0. 방법 (실측 근거)
- 감사 시각: 2026-10-16 17:33 (로컬)
- 게이트 규칙 원본: `scripts/emdash_precheck.py` (MIN_CHARS=3000, MIN_LINKS=3, MIN_TABLES=1,
  INTERNAL_TERMS 4(firecrawl, dev.vars, .env.common, launchd), H1 금지, `## 마무리` 필수)
- **[중요] 저장 형식 보정**: ec_posts.content 는 마크다운이 아니라 Portable Text(JSON blocks) 이다(2026-10-16 본문 head 실측).
  따라서 마크다운 기반 gate(H1/``` 마무리/)는 그대로 적용할 수 없어, 아래로 보정했다:
  - `## 마무리` (markdown heading) → '마무리' 구절 존재(closing) probe
  - 외부 링크 수 → Portable Text markDefs type=link, href 에 aikorea24.kr 가 아닌 것
  - 표 수 → _type 이 table / portableTable / tableBlock 인 block 수
  - 문자 수 → Portable Text span text 총 길이
  - 코드펜스 짝수 게이트는 PT 에서는 style=code 블록이므로 n/a (별도 측정 안 함)
  사전 self-test: emdash_precheck.py --selftest 통과(마크다운 출력 단계에서 동일 규칙 유지).
- 모집단: ec_posts 전체 1516건. 발행(published) 1513건 검사 (드래프트 3건 제외).
- 의미 jargon 추가 용어 9종: 대표님, 에이전트, 지시서, 파이프라인, 커스텀 프로바이더, OpenCode CLI, CLI 평가, 바우처, LaunchD (Gate 4종 외부 용어와 별도).
- Portable Text(JSON) 컬럼 확인: 1513 / 1513 건이 PT(JSON) 형식. (나머지는 마크다운·plain 또는 비string.)
- 쓰기 전용 감사. 에이전트는 어떤 글도 수정·발행하지 않았다.
- [검증불가] 전제 오류(실측과 어긋난 단정)는 게이트가 못 잡으므로 최근 25건을 별도 excerpt 700자로 노출(§3).

## 1. 전수 기계 점검 결과 (발행 글 1513건, PT-aware)

| 검사 | 실패 건수 | 실패 비율 |
|---|---|---|
| closing | 1249 / 1513 | 82.6% |
| links | 1479 / 1513 | 97.8% |
| tables | 1486 / 1513 | 98.2% |
| length | 1232 / 1513 | 81.4% |
| internal_terms | 1 / 1513 | 0.1% |
| 내부 용어 4종 (firecrawl, dev.vars, .env.common, launchd) | 1 / 1513 | 0.1% |
| 의미 jargon 9종 | 345 / 1513 | 22.8% |
| **게이트 1종 이상 실패** | **1511 / 1513** | 99.9% |

  - 게이트 전체 통과(0 결함): 2건
  - 실패 글 총 결함 수(다중 합산): 5447건

### 1.1 게이트 실패 slug (상위 40건, 결함 수 내림차순)
| slug (id) | 실패 게이트 | jargon | 제목 |
|---|---|---|---|
| `free-lecture-ai-briefing-pipeline` (01M4JEVRGZ9ETMBTYQ5RN9QFEM) | closing, links, tables, length, internal_terms | 대표님, 에이전트, 파이프라인 | AI 뉴스 브리핑 자동화 파이프라인 — 수집부터 발행까지, 멈췄을 때 고 |
| `kb-신한-하나-농협-ai-인재-확보-총력전-금융권-경쟁의-판이-바뀌고-있다` (01M4HVNW2Q0000000000000Y21) | closing, links, tables, length | 에이전트, 파이프라인 | KB 신한 하나 농협 AI 인재 확보 총력전 금융권 경쟁의 판이 바뀌고  |
| `ai-코딩-생산성-180퍼센트-증가-배포는-30퍼센트-nber-인간-병목-현상-연구` (01M4HVPBRQ0000000000001GWZ) | closing, links, tables, length | 에이전트, 파이프라인 | AI 코딩 생산성 180퍼센트 증가 배포는 30퍼센트 NBER 인간 병목 |
| `ai-에이전트-자기복제-해킹-성공률-6퍼센트에서-81퍼센트로-1년만에-급등-palisade-research-분석` (01M4HVQJ06000000000000046Y) | closing, links, tables, length | 에이전트, 파이프라인 | AI 에이전트 자기복제 해킹 성공률 6퍼센트에서 81퍼센트로 1년만에 급 |
| `ai가-신입-변호사-일자리를-없앤다-빅로펌-인재-파이프라인-붕괴-위기` (01M4HVQX5600000000000014SN) | closing, links, tables, length | 에이전트, 파이프라인 | AI가 신입 변호사 일자리를 없앤다 빅로펌 인재 파이프라인 붕괴 위기 |
| `gpt-55-벤치마크-1위-환각률-86-ai-성능-재정의` (01M4HVR48H00000000000003RC) | closing, links, tables, length | 에이전트, 파이프라인 | GPT-5.5 벤치마크 1위 환각률 86% AI 성능 재정의 |
| `클로드-코드-루틴-ai가-밤새-버그-고치고-코드-리뷰하는-시대-시작됐다` (01M4HVRGP0000000000000144N) | closing, links, tables, length | 에이전트, 파이프라인 | 클로드 코드 루틴 AI가 밤새 버그 고치고 코드 리뷰하는 시대 시작됐다 |
| `알리바바와-샤오미의-ai-인재-채용-전쟁` (01M4HVRXZF0000000000000WHW) | closing, links, tables, length | 에이전트, 파이프라인 | 알리바바와 샤오미의 AI 인재 채용 전쟁 |
| `나노바나나의-첫-번째-진짜-경쟁자가-나타났다` (01M4HVS6H30000000000000H9E) | closing, links, tables, length | 에이전트, 파이프라인 | 나노바나나의 첫 번째 진짜 경쟁자가 나타났다 |
| `free-lecture-opencode-coding-agent` (01M4JEQHESMPNFDNNZTS3VX7NZ) | closing, links, tables, length | 에이전트, 지시서 | OpenCode + 무료 LLM으로 코딩 에이전트 굴리기 — 매일 쓰는  |
| `free-model-dots-3-note-preview` (01M4Z5E3D12RBXR7FQ4PPBWAM6) | closing, links, length | 에이전트, 파이프라인, OpenCode CLI | Dots3-Note Preview — 샤오홍슈가 만든 280B 오픈웨이트 |
| `마이크로소프트-개편된-윈도우-11-탑재-엔비디아-칩-기반-ai-pc-공개-및-분석` (01M4HMQV5KXX1S998VV7YTQWER) | closing, links, tables, length | 에이전트 | 마이크로소프트, 개편된 윈도우 11 탑재 엔비디아 칩 기반 AI PC 공 |
| `openai는-새로운-에이전트가-당신의-삶을-관리하길-원한다-기자의-ai는-사랑한다고-고백했다-인공지능의-미래와-일상-변화` (01M4HMRAPJ98Q360N32PH71ADW) | closing, links, tables, length | 에이전트 | OpenAI는 새로운 에이전트가 당신의 삶을 관리하길 원한다. 기자의 A |
| `ai-에이전트의-다음-난관-웹사이트의-차단-벽-넘기-문제와-해결-전망` (01M4HMS470VYKS316GFHWENSAN) | closing, links, tables, length | 에이전트 | AI 에이전트의 다음 난관: 웹사이트의 차단 벽 넘기 문제와 해결 전망 |
| `시е라-개인용-ai-에이전트를-위한-오픈-표준-퍼스널-에이전트-프로토콜-발표-인공지능-생태계의-새로운-도약` (01M4HMS7CFYFFMVVV42XWTA8PY) | closing, links, tables, length | 에이전트 | 시е라, 개인용 AI 에이전트를 위한 오픈 표준 '퍼스널 에이전트 프로토 |
| `메타-뮤즈-amd에-활력-불어넣어-ai의-주도권은-개인용-에이전트로-이동` (01M4HMSH589ZWAJ985Z6VNHY52) | closing, links, tables, length | 에이전트 | 메타 뮤즈, AMD에 활력 불어넣어… AI의 주도권은 개인용 에이전트로  |
| `인스팅트-계정이-없는-친구도-함께-참여할-수-있는-단톡방-ai-에이전트-출시-소식과-분석` (01M4HMSQHB11RMY3Q4PPDJA90V) | closing, links, tables, length | 에이전트 | 인스팅트, 계정이 없는 친구도 함께 참여할 수 있는 단톡방 AI 에이전트 |
| `ai-에이전트를-기업-지식과-연결하기-기업용-인공지능-성공의-핵심-조건` (01M4HMT44A9Q5FJDNP8G89CGXD) | closing, links, tables, length | 에이전트 | AI 에이전트를 기업 지식과 연결하기: 기업용 인공지능 성공의 핵심 조건 |
| `오픈ai의-또-다른-안전-관련-퇴사-공개-경고와-함께-이탈-패턴-이어져-인공지능-안전의-위기` (01M4HMV3HFRZ7AE2X5Z1MKDKP6) | closing, links, tables, length | 에이전트 | 오픈AI의 또 다른 안전 관련 퇴사, 공개 경고와 함께 이탈 패턴 이어져 |
| `문자-메시지-속에서-살아가는-모든-ai-에이전트들의-현재와-미래` (01M4HMVXQ4RCYDNGGFTYBKEGKB) | closing, links, tables, length | 에이전트 | 문자 메시지 속에서 살아가는 모든 AI 에이전트들의 현재와 미래 |
| `애플-ai-에이전트의-새로운-위험성에-대응해-macos-전체-디스크-접근-제어-강화한다고-밝혀` (01M4HN67CQQ3K1P4QP8KNGVCXY) | closing, links, tables, length | 에이전트 | 애플, AI 에이전트의 새로운 위험성에 대응해 macOS ‘전체 디스크  |
| `챗gpt-맥mac-앱의-결함으로-해커들이-민감한-데이터를-탈취할-수-있었던-보안-취약점-분석` (01M4HN6XQS6GY9QBVRT8262918) | closing, links, tables, length | 에이전트 | 챗GPT 맥(Mac) 앱의 결함으로 해커들이 민감한 데이터를 탈취할 수  |
| `오픈ai와-앤스로픽을-쫓던-구글-새-플래그십-모델은-정말-최첨단-경쟁에서-우위를-점할-수-있을까` (01M4HN7736HNEMPY99CBW47XBB) | closing, links, tables, length | 에이전트 | 오픈AI와 앤스로픽을 쫓던 구글, 새 플래그십 모델은 정말 최첨단 경쟁에 |
| `블룸버그-보도-고문의-이탈을-두고-팩토리와-코그니션-수장들-간-충돌과-인공지능-업계의-현실` (01M4HN806AHNAM9NS23DFYC402) | closing, links, tables, length | 에이전트 | 블룸버그 보도: 고문의 이탈을 두고 팩토리와 코그니션 수장들 간 충돌과  |
| `발로르-아이트리디스-세쿼이아-7억-5000만-달러-가치의-ai-스타트업-flow-engineering에-투자` (01M4HN8T48NCQN9W51787D7JPD) | closing, links, tables, length | 에이전트 | 발로르, 아이트리디스, 세쿼이아, 7억 5,000만 달러 가치의 AI 스 |
| `구글-젬스gems를-스킬skills로-교체하며-오픈에이아이-및-앤스로픽과-함께-에이전트-준비형-프롬프트-형식으로-전환` (01M4HN8XEGJQEJ9RMRT4AXF609) | closing, links, tables, length | 에이전트 | 구글, 젬스(Gems)를 스킬(Skills)로 교체하며 오픈에이아이 및  |
| `아스세르타ascerta-델의-벤처-부문으로부터-1800만-달러-투자-유치-어떤-ai가-성과를-내는지-증명한다` (01M4HN9A8E3F2VJKGXZSHHSAQ3) | closing, links, tables, length | 에이전트 | 아스세르타(Ascerta), 델의 벤처 부문으로부터 1,800만 달러 투 |
| `중국산-ai-에이전트도-미국-경쟁사들과-마찬가지로-기만적인-행동을-보입니다-인공지능-안전성의-새로운-위기` (01M4HN9Q23P8V1ZZN0TZ4QNVXJ) | closing, links, tables, length | 에이전트 | 중국산 AI 에이전트도 미국 경쟁사들과 마찬가지로 기만적인 행동을 보입니 |
| `앱스토어-모델을-정조준한-openai의-최신-기능들과-인공지능-생태계의-미래` (01M4HN9T8TQ6GCYM5YPFJQGT0Q) | closing, links, tables, length | 에이전트 | 앱스토어 모델을 정조준한 OpenAI의 최신 기능들과 인공지능 생태계의  |
| `호주를-위해-더-나은-모습을-보여달라-오픈ai-무단-접근에-대해-사과와-인공지능-신뢰의-과제` (01M4HN9XBWS20RCVAY2G9E79JN) | closing, links, tables, length | 에이전트 | '호주를 위해 더 나은 모습을 보여달라': 오픈AI, 무단 접근에 대해  |
| `저커버그가-소비자-ai-시장을-넘어-확장하는-가운데-메타가-소상공인용-뮤즈-출시-전략-분석` (01M4HNB4GXYV5K6R9V4P0D65TQ) | closing, links, tables, length | 에이전트 | 저커버그가 소비자 AI 시장을 넘어 확장하는 가운데, 메타가 소상공인용  |
| `제미나이-안드로이드에서-구글-어시스턴트-완전-대체-ai-비서-시대-본격-개막` (01M4HNBASRMF7ZMC76TMTV8VQ8) | closing, links, tables, length | 에이전트 | 제미나이, 안드로이드에서 구글 어시스턴트 완전 대체… AI 비서 시대 본 |
| `쇼피파이-브라우저-기반-ai-에이전트-체크아웃-개방-에이전트-커머스-시대의-서막` (01M4HNBM3A5F5GV24S9YGNE4P0) | closing, links, tables, length | 에이전트 | 쇼피파이 브라우저 기반 AI 에이전트 체크아웃 개방, 에이전트 커머스 시 |
| `ai-에이전트가-통제를-벗어날-때-책임은-누구에게-있는가-법적윤리적-쟁점-분석` (01M4HNBTA8QKERKY0JWSG7YDZ4) | closing, links, tables, length | 에이전트 | AI 에이전트가 통제를 벗어날 때 책임은 누구에게 있는가? 법적·윤리적  |
| `ai-에이전트가-노동-시장을-뒤덮을-준비를-마쳤지만-아무도-대비하지-못한-이유와-대응-전략` (01M4HNC6V6QNFNJBZ03VSFYS7F) | closing, links, tables, length | 에이전트 | AI 에이전트가 노동 시장을 뒤덮을 준비를 마쳤지만 아무도 대비하지 못한 |
| `메타의-뮤즈-에이전트-경제계의-가장-수익성-높은-약점을-겨누다-구독-경제의-새로운-위협` (01M4HNCD70N8JWBY1QRZZC62YQ) | closing, links, tables, length | 에이전트 | 메타의 '뮤즈' 에이전트, 경제계의 가장 수익성 높은 약점을 겨누다: 구 |
| `ai-에이전트가-모델-개발-업무를-더-많이-맡지만-의사결정은-여전히-인간의-몫인-이유와-미래-전망` (01M4HNDS8HB6J8M0EDQ6BPY6XH) | closing, links, tables, length | 에이전트 | AI 에이전트가 모델 개발 업무를 더 많이 맡지만, 의사결정은 여전히 인 |
| `호주-뉴스-실시간-갤러거-최종-예산-결과로-적자-60억-달러-축소-전망과-rba-기준금리-인상-가능성-분석` (01M4HNF442BVA6NMHVV248CNFH) | closing, links, tables, length | 에이전트 | 호주 뉴스 실시간: 갤러거, 최종 예산 결과로 적자 60억 달러 축소 전 |
| `연구진-gpt-6-아스트라를-로봇에-직접-탑재해-낯선-주방-청소-성공-인공지능-로봇의-새로운-도약` (01M4HNGFKNKTDK4H0PC6D191TT) | closing, links, tables, length | 에이전트 | 연구진, GPT-6 아스트라를 로봇에 직접 탑재해 낯선 주방 청소 성공: |
| `수만-건의-보안-조사-결과-오픈ai의-허깅페이스-사건은-시작에-불과-인공지능-보안의-새로운-위기` (01M4HNGJV238ZPRNBMK7FZ8MT4) | closing, links, tables, length | 에이전트 | 수만 건의 보안 조사 결과, 오픈AI의 허깅페이스 사건은 시작에 불과:  |
| ... (+1471건 생략) | | | |

## 2. 의미 점검 (최근 25건, created_at 내림차순)

| # | slug | jargon (기계 탐지) | closure | links | tables | len | 권고 |
|---|---|---|---|---|---|---|---|
| 1 | `ll-alpha-free-12-question-eval` | 에이전트, 파이프라인, OpenCode CLI | ✅ | ✅ | ✅ | 4474 | 본문 정독 필요(전제 오류) |
| 2 | `openrouter-free-models-opencode` | OpenCode CLI | ✅ | ✅ | ✅ | 3944 | 본문 정독 필요(전제 오류) |
| 3 | `groq-free-api-key-guide` | 커스텀 프로바이더, OpenCode CLI | ✅ | ✅ | ✅ | 2553 | 게이트 결함 → 수정 |
| 4 | `opencode-cli-guide` | 에이전트 | ✅ | ⚠️ | ✅ | 3915 | 게이트 결함 → 수정 |
| 5 | `세일즈포스-대졸-취업-시장-침체-속-영국-학생들에게-무료-ai-도구-제공-배경과-전망` | 없음 | ❌ | ⚠️ | ✅ | 1655 | 게이트 결함 → 수정 |
| 6 | `무료-llm-nemotron-35-super-vl-free-오픈코드-젠-무료-티어-성능과-특징-분석` | 없음 | ❌ | ⚠️ | ✅ | 1586 | 게이트 결함 → 수정 |
| 7 | `엔비디아-네모트론-35-슈퍼-vl-nvidianemotron-35-super-vlfree-12문항-실측-지금-당장-서브에이전트로-투입해도-됩니다` | 에이전트 | ❌ | ⚠️ | ⚠️ | 4025 | 게이트 결함 → 수정 |
| 8 | `muse-spark-13-contributor-free-meta-기여-모델을-무료로-쓰는-방법` | 에이전트, OpenCode CLI | ❌ | ⚠️ | ✅ | 2570 | 게이트 결함 → 수정 |
| 9 | `space-bunny-free-제로-리텐션으로-안심하고-쓰는-opencode-zen-무료-모델` | OpenCode CLI | ❌ | ⚠️ | ✅ | 2723 | 게이트 결함 → 수정 |
| 10 | `mimo-v26-flash-free-재사용률-803로-1위를-차지한-opencode-zen-무료-모델` | 에이전트, OpenCode CLI | ❌ | ⚠️ | ✅ | 2107 | 게이트 결함 → 수정 |
| 11 | `free-model-nvidia-nemotron-3-5-lightning` | 에이전트, OpenCode CLI | ❌ | ⚠️ | ✅ | 2885 | 게이트 결함 → 수정 |
| 12 | `free-model-nvidia-nemotron-3-ultra` | 에이전트, OpenCode CLI | ✅ | ⚠️ | ✅ | 3446 | 게이트 결함 → 수정 |
| 13 | `free-model-liquid-lfm-2-5` | 에이전트, OpenCode CLI | ❌ | ⚠️ | ✅ | 3810 | 게이트 결함 → 수정 |
| 14 | `free-model-dots-3-note-preview` | 에이전트, 파이프라인, OpenCode CLI | ❌ | ⚠️ | ✅ | 2393 | 게이트 결함 → 수정 |
| 15 | `free-model-cohere-north-mini-code` | 에이전트, OpenCode CLI | ❌ | ⚠️ | ✅ | 3700 | 게이트 결함 → 수정 |
| 16 | `eval-08-검증-raw-html-표-통과-테스트` | 없음 | ❌ | ⚠️ | ⚠️ | 411 | 게이트 결함 → 수정 |
| 17 | `lfm25-24b-a2b로-기기-내에서-빠르고-비공개적인-에이전트-실행하기` | 에이전트 | ❌ | ⚠️ | ✅ | 1871 | 게이트 결함 → 수정 |
| 18 | `무료-llm-nvidianemotron-35-super-vl-120b-a12b-nvidia-nim-free-무료-티어-활용-가이드` | 없음 | ❌ | ⚠️ | ✅ | 1578 | 게이트 결함 → 수정 |
| 19 | `nvidianemotron-3-ultra-550b-a55bfree` | 에이전트 | ❌ | ⚠️ | ⚠️ | 1781 | 게이트 결함 → 수정 |
| 20 | `free-models` | 대표님, OpenCode CLI, CLI 평가 | ❌ | ⚠️ | ✅ | 3108 | 게이트 결함 → 수정 |
| 21 | `aik24-emdash-03-검증-emdash-단독-발행-확인` | 없음 | ❌ | ⚠️ | ⚠️ | 1443 | 게이트 결함 → 수정 |
| 22 | `정직한-ai-평가-인클루전아이-링-31-플래시inclusionailing-31-flash-12문항-실측-손발-작업-투입-판단` | 에이전트 | ❌ | ⚠️ | ⚠️ | 4644 | 게이트 결함 → 수정 |
| 23 | `x` | 없음 | ❌ | ⚠️ | ⚠️ | 1 | 게이트 결함 → 수정 |
| 24 | `aik24-emdash-01-검증-emdash-발행-경로-테스트` | 파이프라인 | ❌ | ⚠️ | ⚠️ | 77 | 게이트 결함 → 수정 |
| 25 | `앨런-튜링-연구소장-영국은-해외-ai에-종속되지-말아야-한다-기술-주권의-중요성` | 파이프라인 | ❌ | ⚠️ | ⚠️ | 1900 | 게이트 결함 → 수정 |

## 3. 최근 5건 본문 excerpt + 단서 (수동 정독용, 700자)

### `ll-alpha-free-12-question-eval` (id=01M52254ST445BKJV63YDMBDE2, len=4474, pt=True)
- 제목: LL Alpha Free(opencode/ll-alpha-free) 12문항 실측 — 정확도보다 응답 지연이 병목입니다
- 내부 4종: 없음
- jargon: ['에이전트', '파이프라인', 'OpenCode CLI']
- excerpt: LL Alpha Free는 OpenCode Zen에서 한시적으로 무료로 제공되는 스텔스 모델입니다. 제공 업체가 공개되지 않았고, 모델 ID는 ll-alpha-free입니다. OpenCode Zen 공식 문서는 이 모델을 이렇게 소개합니다.LL Alpha Free is a stealth model that's free on OpenCode for a limited time. The team is using this time to collect feedback and improve the model.— OpenCode Zen 공식 문서모델 등록 정보 기준으로 컨텍스트는 262,144 토큰, 최대 출력은 65,536 토큰입니다. 텍스트만 입력받고, 추론 강도(reasoning effort)를 5단계로 바꿀 수 있습니다. AIK24가 OpenCode CLI로 12문항을 돌려 본 결과는 12문항 중 4문항 정답(응답이 온 8문항 기준 4/8)이었고, 가장 큰 제약은 정확도가 아니라 응답 지연이었습니다 — 12문항 중 9문항이 60초를 넘겼습니다.1. 공개된 것과 공개되지 않은 것스텔스 모델이므로 무엇이 확인되고 무엇이 확인되지 않는지를 먼저 나눠야 합니다.구분내용출처확인됨제공 기간: 한시적 무료 (종료 시점 미공개)Zen 문서확인됨스펙: 컨텍스트 262,144 · 출력 65,536 · 텍스트 입출력 · 도구 호출 · 구조화 출력models.dev확인됨추론 강도: low · medium · high · xhigh · max 5단계models.dev확인됨가격표: 입력·출력·캐시 읽기·캐시 쓰기 모두 FreeZen 문서미공개제공 업체 — 익명. Zen 응답의 소유자 표기도 opencode, 모델 DB 설명도 Best in class local model 한 줄뿐—미공개가중치·파라미터 수·학습 데이…

### `openrouter-free-models-opencode` (id=01M51SY82M3VFMP33YNA08NY3T, len=3944, pt=True)
- 제목: OpenCode에 무료 모델 연결하기: OpenRouter 키 발급부터 실호출 확인까지
- 내부 4종: 없음
- jargon: ['OpenCode CLI']
- excerpt: OpenCode에 무료 모델을 붙이는 방법은 한 가지가 아닙니다. 이 글은 그중 OpenRouter를 골라, 키 발급부터 연결, 실제 응답이 오는 것까지 순서대로 확인한 기록입니다. OpenRouter는 여러 회사의 모델을 하나의 API로 중계하는 서비스이고, 2026년 10월 16일 조회 기준 카탈로그 465개 중 15개가 :free(무료) 모델입니다. 아래 수치는 전부 같은 날 직접 조회하거나 호출해서 확인한 값입니다.1. OpenRouter로 무엇을 얻나 — 모델 하나가 아니라 목록보통 무료 모델은 제공자마다 따로 가입해야 합니다. OpenRouter는 그 반대로, 키 하나로 여러 제공자의 모델을 골라 씁니다. 요청 형식도 OpenAI와 같아서(/chat/completions), 도구 쪽에서 별도 지원이 필요하지 않습니다.카탈로그: 전체 465개 모델 (2026년 10월 16일 조회)그중 무료: 15개 — 모델 이름 끝에 :free 가 붙습니다무료 모델도 유료 모델과 같은 API로 호출되고, 실제 응답까지 확인했습니다2. 지금 쓸 수 있는 무료 모델 15개https://openrouter.ai/api/v1/models 를 직접 조회해 뽑은 목록입니다. 뒤 숫자는 한 번에 넣을 수 있는 문맥 길이(토큰)입니다.모델문맥성격thinkingmachines/inkling:free1,048,576문맥 최대thinkingmachines/inkling-small:free1,048,576문맥 최대nvidia/nemotron-3.5-super-vl:free1,000,000범용·이미지 입력nvidia/nemotron-3.5-lightning:free1,000,000경량·빠른 응답nvidia/nemotron-3-ultra-550b-a55b:free1,000,000대형dots-studio/dots-3-…

### `groq-free-api-key-guide` (id=01M51NXRNKVSN1DV7EY5MRHGNV, len=2553, pt=True)
- 제목: Groq 무료 API 키 발급받는 법: OpenCode 연결까지
- 내부 4종: 없음
- jargon: ['커스텀 프로바이더', 'OpenCode CLI']
- excerpt: Groq는 자체 칩에서 모델을 돌리는 추론 전용 프로바이더입니다. OpenCode에서 쓰려면 API 키 하나만 연결하면 됩니다. 이 글은 2026년 10월 16일 실제 화면과 공식 문서를 확인해 키 발급 → 등록 → 동작 확인 순서로 정리했고, 무료 티어 한도는 공식 문서 표를 그대로 옮겼습니다.Groq는 뭔가 — 자체 칩(LPU)으로 추론만 하는 프로바이더공식 사이트(groq.com)는 Groq가 추론(inference)에 특화된 자체 칩 LPU를 만들었고, 이후 LPX가 NVIDIA의 차세대 GPU와 함께 동작한다고 설명합니다. 모델을 직접 학습해 배포하는 곳이 아니라, 공개된 모델(openai gpt-oss, qwen 등)을 자체 하드웨어에서 빠르게 돌려 주는 쪽입니다.OpenCode에서는 커스텀 프로바이더로 연결합니다. 즉 설정 파일에 키를 넣어야 쓸 수 있는 (b) 경로이고, 모델 선택기에 기본으로 떠 있는 (a) 내장 무료 모델과는 다릅니다.1. 계정 만들기 — 카드 등록 없이console.groq.com 에 접속해 Google · GitHub · 이메일 중 하나로 가입합니다. 카드 등록은 필요하지 않습니다.2. API 키 발급 — 한 번만 보이는 키console.groq.com/keys 로 이동합니다. 로그인 전에는 Create API Key 버튼이 비활성화되어 있습니다. 로그인 후 버튼을 누르고 키 이름을 정하면 gsk_ 로 시작하는 키가 표시됩니다.이 키는 생성 직후 한 번만 표시됩니다. 창을 닫으면 다시 볼 수 없고, 잃어버리면 삭제 후 재발급하는 방법밖에 없습니다.3. 키 등록 — 셸 환경변수 + OpenCode 설정먼저 셸 설정 파일에 환경변수로 넣습니다. 설정 파일에 키를 직접 쓰지 않기 위한 첫 단계입니다.다음으로 OpenCode 설정 파일 ~/.config/…

### `opencode-cli-guide` (id=01M51M5J5PCWDSN989ZH5152C2, len=3915, pt=True)
- 제목: OpenCode CLI 사용 방법: 설치부터 무료 모델 실행까지
- 내부 4종: 없음
- jargon: ['에이전트']
- excerpt: 터미널에서 AI에게 코드를 맡기는 도구가 개발 흐름의 한 축이 됐습니다. 그중 OpenCode는 2025년 4월 30일 공개된 오픈소스 코딩 에이전트입니다. 2026년 10월 16일 기준 GitHub 스타 21만 개(214,019)를 넘겼고, MIT 라이선스라서 회사에서도 제약 없이 쓸 수 있습니다. 저장소 주소는 최근 sst/opencode에서 anomalyco/opencode로 옮겨졌습니다.이름만 들어보고 "AI 구독료를 따로 내야 하는 도구 아닌가" 하고 지나치는 분들이 많습니다. 결론부터 적으면 그렇지 않습니다. 이 글을 준비하면서 한 개발자 환경의 OpenCode 세션 623건을 직접 집계했는데, 그중 564건(90.5%)이 무료 모델로 실행됐습니다. 유료 모델을 쓴 세션은 59건이었습니다.이 글은 설치 → 무료 API 키 발급 → 첫 실행과 모델 선택 → 무료 모델로 충분한지에 대한 실측 → 자주 쓰는 명령 → 비용 확인 순서로 정리했습니다. 30분이면 무료 세팅을 끝낼 수 있습니다.1. 설치 — 3분이면 끝납니다터미널 한 줄이면 설치가 끝납니다.주의할 점이 하나 있습니다. OpenCode는 V1과 V2 두 계열이 병행되고 있고 설치 주소가 다릅니다.설치 주소설치되는 계열비고https://opencode.ai/installV1 계열 (1.x)문서 대부분이 이 계열 기준https://opencode.ai/v2/installV2 계열 (2.x)현재 개발이 진행되는 라인설치 후 버전을 확인하고, 업데이트는 내장 명령으로 합니다.npm으로도 설치할 수 있지만 패키지 이름이 `opencode-ai` 입니다. npm install -g opencode는 존재하지 않는 패키지라 실패합니다. 또 npm 쪽은 V1 계열(레지스트리 기준 최신 1.19.2)이므로, 최신 라인을 쓰려면 위의 c…

### `세일즈포스-대졸-취업-시장-침체-속-영국-학생들에게-무료-ai-도구-제공-배경과-전망` (id=01M510C9AT78X28WX7VSKV8HQY, len=1655, pt=True)
- 제목: 세일즈포스 대졸 취업 시장 침체 속 영국 학생들에게 무료 AI 도구 제공 배경과 전망
- 내부 4종: 없음
- jargon: 없음
- excerpt: 영국의 대졸 취업 시장이 얼어붙은 가운데 글로벌 기술 기업 세일즈포스가 돌파구를 마련하기 위해 나섰습니다. 최근 영국의 대졸 구인 건수는 2020년 이후 가장 낮은 수치를 기록하며 청년 실업에 대한 우려를 키우고 있습니다. 이러한 상황에서 기업들은 단순한 학력보다 실무에 바로 활용할 수 있는 인공지능 활용 능력을 강력하게 요구하고 있습니다. 세일즈포스는 이러한 시장의 변화에 발맞추어 영국의 학생 수백만 명을 대상으로 무료 인공지능 교육 도구를 전격 지원하기로 결정했습니다.얼어붙은 영국 대졸 구인 시장의 현실현재 영국의 대졸 채용 시장은 코로나19 팬데믹 시기였던 2020년 이후 최악의 침체를 겪고 있습니다. 대학을 졸업하고 사회에 첫발을 내딛는 청년들은 극심한 취업난 속에서 설 자리를 잃어가고 있습니다. 아래의 비교표를 통해 최근 고용 시장의 변화를 더욱 명확하게 살펴보겠습니다.구분과거 고용 시장 (2020년 이전)현재 고용 시장 (최근 발표 기준)채용 규모상대적으로 안정적인 대졸 구인 건수 유지2020년 이후 최저치를 기록하며 급감핵심 요구 역량기본적인 전공 지식 및 일반적인 사무 능력인공지능 활용 능력 및 디지털 기술 숙련도기업의 태도장기적인 자체 교육 중심의 신입 채용즉시 현업에 투입 가능한 실무형 인재 선호이처럼 기업들은 이제 기본적인 스펙보다는 인공지능을 능숙하게 다루는 실질적인 역량을 갖춘 인재를 원하고 있습니다. 하지만 대학 교육 과정만으로는 이러한 현장의 눈높이를 빠르게 맞추기 어려운 것이 현실입니다.세일즈포스의 무료 인공지능 도구 지원 전략이러한 간극을 메우기 위해 세일즈포스는 영국 내 대학생들을 대상으로 자사의 혁신적인 인공지능 플랫폼에 접근할 수 있는 특별한 프로그램을 발표했습니다. 이번 지원을 통해 무려 600만 명에 달하는 학생 무상 혜택을 누릴 수 있게 됩니다…

## 4. 내부 용어 노출 (4종) 상세

- `free-lecture-ai-briefing-pipeline` (01M4JEVRGZ9ETMBTYQ5RN9QFEM) — AI 뉴스 브리핑 자동화 파이프라인 — 수집부터 발행까지, 멈췄을 때 고치는 법까지

## 5. 의미 용어(jargon) 노출 빈도 상위 (3개 이상)
  총 4건
| slug | 빈도 | 용어 |
|---|---|---|
| `free-lecture-ai-briefing-pipeline` | 3 | 대표님, 에이전트, 파이프라인 |
| `free-models` | 3 | 대표님, OpenCode CLI, CLI 평가 |
| `free-model-dots-3-note-preview` | 3 | 에이전트, 파이프라인, OpenCode CLI |
| `ll-alpha-free-12-question-eval` | 3 | 에이전트, 파이프라인, OpenCode CLI |

## 6. 우선 수정 권고 TOP 10 (근거 포함)

1. `free-lecture-ai-briefing-pipeline` (id=01M4JEVRGZ9ETMBTYQ5RN9QFEM) — 결함 5 + jargon 3
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2598자 (최소3000)
   - 내부 용어 노출: ['launchd']
   - 의미 용어: ['대표님', '에이전트', '파이프라인']
2. `kb-신한-하나-농협-ai-인재-확보-총력전-금융권-경쟁의-판이-바뀌고-있다` (id=01M4HVNW2Q0000000000000Y21) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2348자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
3. `ai-코딩-생산성-180퍼센트-증가-배포는-30퍼센트-nber-인간-병목-현상-연구` (id=01M4HVPBRQ0000000000001GWZ) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2066자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
4. `ai-에이전트-자기복제-해킹-성공률-6퍼센트에서-81퍼센트로-1년만에-급등-palisade-research-분석` (id=01M4HVQJ06000000000000046Y) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2573자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
5. `ai가-신입-변호사-일자리를-없앤다-빅로펌-인재-파이프라인-붕괴-위기` (id=01M4HVQX5600000000000014SN) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2850자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
6. `gpt-55-벤치마크-1위-환각률-86-ai-성능-재정의` (id=01M4HVR48H00000000000003RC) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2700자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
7. `클로드-코드-루틴-ai가-밤새-버그-고치고-코드-리뷰하는-시대-시작됐다` (id=01M4HVRGP0000000000000144N) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2431자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
8. `알리바바와-샤오미의-ai-인재-채용-전쟁` (id=01M4HVRXZF0000000000000WHW) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 1개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2415자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
9. `나노바나나의-첫-번째-진짜-경쟁자가-나타났다` (id=01M4HVS6H30000000000000H9E) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2309자 (최소3000)
   - 의미 용어: ['에이전트', '파이프라인']
10. `free-lecture-opencode-coding-agent` (id=01M4JEQHESMPNFDNNZTS3VX7NZ) — 결함 4 + jargon 2
   - 본문에 '마무리' 구절 없음 (closing 섹션)
   - 외부 링크 0개 (최소3, Portable Text markDefs)
   - 표(table block) 0개 (최소1)
   - 본문 텍스트 2771자 (최소3000)
   - 의미 용어: ['에이전트', '지시서']

## 7. 검증 한계 / 미확인

- [검증불가] 전제 오류(실측과 어긋난 단정)는 게이트가 못 잡는다. 본 보고는 excerpt 900자 + jargon 리스트로 후보를 압축했다. 최근 25건의 정독은 별도 작업 (§3 슬러그 목록 참조).
- [부분검증] 'closing' (= '마무리' 구절 없는 글) 은 실제 closing 섹션이 '정리'/'Takeaways' 등 다른 제목일 수 있다. 정확도 100% 아님 (근거: md 패턴 기준, PT 텍스트 substring 검사).
- [부분검증] jargon 카운트는 위 9종만 센다. 그 외 내부 용어는 미확인 (탐지 사전 부족).
- [검증불가] featured_image·OG 404 여부는 이 감사에서 점검하지 않았다 (`scripts/emdash15_media_url_health.py` 가 담당).
- [검증불가] emdash_precheck 게이트(마크다운 기반)의 99% 실패가 PT 형식 때문에 재현되지 않는다고 본다
  — 게이트 통과율이 높아 보일 수 있으나, 게시된 본문의 구조·내용 품질은 달리 봐야 한다 (explanation in §0).

## 8. 산출 근거 (D1 read-only)
- ec_posts 전체: 1516건 | 발행: 1513건 | 드래프트: 3건
- rowsRead 누적: populate 1516 + content 1513 = 약 3029행 (쿼터 5,000,000).
- 어떤 글도 수정·발행하지 않았다 (read-only). write 쿼리는 없음.
