---
title: "ChatGPT 프롬프트 5가지 공식 원하는 답을 얻는 핵심 프레임워크"
description: "AI에게 원하는 답을 얻는 프롬프트 공식 5가지를 소개합니다. RISE, CREATE, TAG, RISEN, CO-STAR 프레임워크의 핵심과 실전 예시를 정리했습니다."
date: 2026-02-24T10:26:00+09:00
category: "강좌"
tags:
  - "프롬프트"
  - "ChatGPT"
  - "프롬프트공식"
  - "RISE"
  - "CREATE"
  - "CO-STAR"
  - "AI활용"
draft: false
image: "https://img.aikorea24.kr/images/chatgpt-프롬프트-5가지-공식/thumbnail.webp"
---

[OpenAI 프롬프트 엔지니어링 가이드](https://platform.openai.com/docs/guides/prompt-engineering)

ChatGPT한테 질문했는데 엉뚱한 답이 나온 적 있으시죠? 문제는 AI가 아닙니다. 프롬프트입니다. 프롬프트는 AI에게 주는 설계도예요. 설계도가 명확할수록 결과물이 좋아집니다.

프롬프트를 잘 쓰는 공식이 있습니다. RISE, CREATE, TAG, RISEN, CO-STAR 이렇게 5가지가 대표적이에요. 오늘은 이 5가지 프레임워크의 핵심과 언제 어떤 걸 써야 하는지 정리해 드리겠습니다.

## 공식 1번 RISE

[프롬프트 RISE 공식 분석과 보고서 작업에 강한 프레임워크 | AI코리아24](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-rise-%EA%B3%B5%EC%8B%9D-%EB%B6%84%EC%84%9D%EA%B3%BC/)

분석, 보고서, 복잡한 작업에 강한 프레임워크입니다. R은 Role로 역할을 정해주고, I는 Input으로 필요한 정보를 주고, S는 Steps로 단계를 알려주고, E는 Expectation으로 결과 형태를 지정합니다.

예를 들어 이력서 평가를 요청한다면 이렇게 씁니다. "당신은 10년 경력 채용 전문가입니다. 다음 이력서를 보고 첫째 핵심 기술 경험 연수 확인, 둘째 경력 공백 검토, 셋째 프로젝트 성과 평가 순서로 분석하고, 구조화된 평가 보고서로 작성해 주세요." 그냥 "이 이력서 어때?"라고 묻는 것과 결과가 완전히 다릅니다.

## 공식 2번 CREATE

[프롬프트 CREATE 공식 콘텐츠와 창작 작업에 강한 프레임워크 | AI코리아24](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-create-%EA%B3%B5%EC%8B%9D-%EC%BD%98%ED%85%90%EC%B8%A0%EC%99%80/)

콘텐츠, 광고 문구, 영상 스크립트 같은 창작 작업에 씁니다. C는 Character로 관점을 정하고, R은 Request로 요청 내용을 명확히 하고, E는 Examples로 예시를 보여주고, A는 Adjustments로 조정 사항을 주고, T는 Type of Output으로 형식을 지정하고, E는 Extras로 추가 요청을 넣습니다.

핵심은 **Examples** 입니다. 원하는 결과물의 샘플을 하나 보여주면 AI가 톤과 스타일을 바로 파악합니다. 광고 스크립트를 요청할 때 "장면1은 5초, 지하철에서 이어폰 착용하면 소음이 사라진다, 내레이션은 하루 중 가장 평화로운 순간" 이런 식으로 예시 하나만 주면 나머지 장면도 같은 톤으로 만들어줍니다.

![k2ZuWV71.webp](https://img.aikorea24.kr/images/chatgpt-프롬프트-5가지-공식/a9e5197bdb68b8086e84c048120f7bcb96f94b5e.webp)

## 공식 3번 TAG

[프롬프트 TAG 공식 가장 심플하고 빠른 프레임워크 | AI코리아24](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-tag-%EA%B3%B5%EC%8B%9D-%EA%B0%80%EC%9E%A5/)

가장 심플한 프레임워크입니다. 빠른 답이 필요할 때 씁니다. T는 Task로 작업을 정의하고, A는 Action으로 행동을 지시하고, G는 Goal로 목표를 명시합니다.

"소셜 미디어 마케팅으로 트래픽 증가시키려고 한다. 검증된 콘텐츠 전략 5가지를 제안해라. 목표는 양질의 리드 확보다." 이렇게 세 줄이면 끝입니다. 복잡한 작업에는 부족하지만, 아이디어가 급하게 필요하거나 간단한 질문에는 TAG가 제일 빠릅니다.

## 공식 4번 RISEN

[프롬프트 RISEN 공식 RISE보다 정교한 결과가 필요할 때 | AI코리아24](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-risen-%EA%B3%B5%EC%8B%9D-rise%EB%B3%B4%EB%8B%A4/)

RISE의 확장판입니다. 더 정교한 결과가 필요할 때 씁니다. R은 Role, I는 Instructions로 지시사항, S는 Steps, E는 End Goal로 최종 목표, N은 Narrowing으로 범위 좁히기입니다.

RISE와 차이점은 **Narrowing** 입니다. "1500자 이내, 전문 용어는 쉽게 풀어서, 경쟁사 언급 금지" 이런 식으로 제약 조건을 걸어주면 AI가 범위를 벗어나지 않습니다. 블로그 글, 제안서처럼 형식과 제약이 명확한 작업에 좋습니다.

## 공식 5번 CO-STAR

[프롬프트 CO-STAR 공식 마케팅과 고객 대상 글에 강한 프레임워크 | AI코리아24](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-co-star-%EA%B3%B5%EC%8B%9D/)

싱가포르 정부 AI 대회에서 1등 한 프레임워크입니다. 마케팅, 고객 대상 글에 특히 강합니다. C는 Context로 배경 상황, O는 Objective로 목표, S는 Style로 문체, T는 Tone으로 어조, A는 Audience로 청중, R은 Response로 응답 형식입니다.

핵심은 **Audience** 입니다. "직원 10명에서 50명 규모 중소기업 대표"처럼 누가 읽을지 명시하면 AI가 그 사람 눈높이에 맞춰 씁니다. 같은 내용도 대학생한테 쓰는 것과 임원한테 쓰는 건 완전히 다르잖아요. CO-STAR는 그걸 자동으로 맞춰줍니다.

## 언제 어떤 공식을 쓸까

빠른 답이 필요하면 TAG, 분석이나 보고서는 RISE나 RISEN, 창작물은 CREATE, 마케팅 글은 CO-STAR를 쓰세요. 처음엔 TAG로 시작해서 익숙해지면 나머지로 확장하는 게 좋습니다.

공식보다 중요한 건 이겁니다. 역할을 주고, 구체적으로 쓰고, 예시를 보여주고, 제약 조건을 걸어라. 이 네 가지만 기억하면 어떤 공식을 쓰든 AI가 여러분 말을 알아듣습니다.

#프롬프트 #ChatGPT #AI활용 #RISE #CREATE #TAG #RISEN #COSTAR