---
title: "Anthropic OpenClaw 창시자 계정 정지 사건 AI 플랫폼 오픈소스 생태계 갈등의 전말"
description: "Anthropic이 OpenClaw 창시자 Steinberger의 계정을 일시 정지했다. 오픈소스 도구 차단과 자사 제품 강화가 맞물린 이 사건이 AI 플랫폼 생태계 신뢰에 던지는 질문을 분석한다"
date: 2026-04-11T14:21:23+09:00
category: "뉴스"
tags:
  - "Anthropic"
  - "OpenClaw"
  - "Steinberger"
  - "Claude"
  - "오픈소스AI"
  - "AI플랫폼"
  - "OpenAI"
draft: false
image: "https://img.aikorea24.kr/images/anthropic-openclaw-창시자-계정/thumbnail.webp"
---

---

Anthropic이 오픈소스 AI 도구 OpenClaw의 창시자 Peter Steinberger의 계정을 "의심스러운 활동"을 이유로 일시 정지했습니다. 정지는 몇 시간 만에 해제됐지만, 이 사건은 단순한 오탐(False Positive·오류 감지)으로 마무리되지 않습니다. Anthropic이 서드파티 도구 정책을 바꾸고 자체 에이전트 기능을 강화하는 흐름 속에서 발생했기 때문입니다.

기사 원문은 이곳에서 확인할 수 있습니다: [AI코리아24 브리핑](https://aikorea24.kr/briefing/2026-04-11/#item-2)

## OpenClaw란 무엇이고 이번 사건의 경위는

**OpenClaw** 는 Claude, ChatGPT 등 다양한 AI 모델을 연결해 복잡한 자동화 작업을 수행할 수 있게 해주는 오픈소스 AI 프레임워크입니다. **에이전트 AI 하네스(Agentic AI Harness)** 라고도 불리며, 개발자들이 AI를 활용한 자동화 워크플로를 구축하는 데 널리 사용됩니다.

Steinberger는 이 도구를 만들었고, 현재는 Anthropic의 경쟁사 OpenAI에 재직 중입니다. 그가 Claude를 테스트 목적으로 사용하다 계정이 정지됐고, 이를 X(트위터)에 공개하자 수백 개의 댓글이 달리며 빠르게 바이럴됐습니다. 몇 시간 후 계정은 복구됐고 Anthropic 엔지니어가 직접 "OpenClaw 사용 때문에 차단한 적 없다"고 댓글을 남겼습니다.

## 사건을 이해하는 두 가지 맥락

이 사건은 단독으로 보면 단순한 오탐 사고입니다. 그러나 직전 3주의 흐름을 함께 보면 구조가 보입니다.

첫 번째 맥락은 **Anthropic의 OpenClaw 과금 정책 변경** 입니다. Anthropic은 불과 며칠 전, Claude 구독 요금제에서 OpenClaw 같은 서드파티 도구 사용을 제외하고 별도 API 과금으로 전환했습니다. 공식 이유는 "에이전트 워크플로가 일반 사용보다 훨씬 많은 컴퓨팅을 소비한다"는 것이었습니다.

두 번째 맥락은 **Anthropic 자체 에이전트 도구 강화** 입니다. Anthropic은 이 정책 변경 직전, 자사 에이전트 도구 Cowork에 원격 에이전트 제어 기능인 Claude Dispatch를 추가했습니다. Steinberger는 이 타이밍을 직접 지목하며 "기능을 따라 만들고, 오픈소스를 잠근다"고 비판했습니다.

## 모바일 앱 생태계에서 반복된 역사

이 패턴은 낯설지 않습니다. 2010년대 Apple이 App Store에서 서드파티 기능을 제한하면서 자체 앱(Apple Maps, Apple Music 등)을 강화했던 방식, Facebook이 API를 오픈해 외부 개발자 생태계를 키우다가 정책을 바꿔 핵심 기능을 자체화했던 방식과 구조가 유사합니다.

플랫폼 기업이 생태계를 먼저 외부 개발자로 채운 뒤, 가장 인기 있는 기능을 자체화하고 접근 조건을 바꾸는 이 흐름을 업계에서는 **플랫폼 배신(Platform Betrayal)** 이라고 부르기도 합니다.

![K7AJY2Ud.webp](https://img.aikorea24.kr/images/anthropic-openclaw-창시자-계정/da590cc1a4552ae9efb07577188cd8f7d1140a06.webp)

Anthropic이 이 비판을 의도한 것인지, 단순한 비즈니스 구조 조정인지는 현재로서는 판단하기 어렵습니다. 그러나 오픈소스 개발자 커뮤니티가 이 신호를 어떻게 읽느냐는 Claude 생태계 전체의 신뢰에 영향을 미칩니다.

## 개발자와 사용자에게 미치는 영향

OpenClaw 기반으로 Claude를 연동해서 사용하던 개발자와 기업에게 이번 과금 정책 변경은 즉각적인 비용 상승을 의미합니다. 구독 요금제 안에 포함되던 사용량이 이제 소비량 기준 API 과금으로 전환됩니다.

에이전트 워크플로는 단순 질의응답보다 API 호출 횟수가 수십 배 많습니다. 자동화 루프를 돌리거나 멀티스텝 작업을 처리하는 경우 예상치 못한 비용이 발생할 수 있습니다. OpenClaw 사용자라면 현재 워크플로의 API 사용량을 먼저 측정하고 비용을 다시 계산해볼 필요가 있습니다.

한국 개발자 커뮤니티에서도 Claude API를 활용한 자동화 프로젝트를 진행 중이라면, 이번 정책 변경의 약관을 구체적으로 확인해야 합니다.

## AI 플랫폼 생태계의 신뢰 문제

이번 사건에서 가장 주목할 지점은 Steinberger의 한 마디입니다. Anthropic 입사 제안을 받지 않고 OpenAI로 간 이유를 묻는 댓글에 그는 "하나는 나를 환영했고, 다른 하나는 법적 위협을 보냈다"고 답했습니다.

사실 여부를 확인할 방법은 없습니다. 그러나 이 한 문장이 수백 개의 댓글 중 가장 많이 공유됐다는 사실 자체가 AI 개발자 커뮤니티의 정서를 반영합니다. AI 플랫폼이 오픈소스 생태계와 어떤 관계를 맺는지가 장기적으로 해당 플랫폼의 경쟁력을 결정하는 요소 중 하나입니다. 기술력만큼 신뢰가 중요한 시장입니다.

#Anthropic #OpenClaw #Claude #오픈소스AI #AI플랫폼 #Steinberger #에이전트AI