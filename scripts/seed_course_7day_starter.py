#!/usr/bin/env python3
"""7일 AI 입문 강좌 시드 데이터 생성기.
post에 콘텐츠를 저장하고 course_lessons에 매핑 + 티저를 저장.

사용법:
  python3 scripts/seed_course_7day_starter.py        # wrangler d1 execute로 삽입
  python3 scripts/seed_course_7day_starter.py --dry   # SQL만 출력
"""
import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── 7일 커리큘럼 정의 ───────────────────────────────────────────────

COURSE_SLUG = "7day-starter"
COURSE_TITLE = "7일 AI 입문 — ChatGPT부터 시작하는 AI 활용법"
COURSE_DESC = (
    "매일 저녁 5분, 7일 동안 AI 기초를 완성합니다. "
    "ChatGPT 사용법부터 프롬프트 작성, 이미지 생성, 업무 활용까지. "
    "완전 무료, 커뮤니티에서 질문하며 학습하세요."
)

LESSONS = [
    {
        "day": 1,
        "title": "ChatGPT, 처음 시작하기",
        "content": textwrap.dedent("""\
            ## ChatGPT, 처음 시작하기

            AI 활용의 첫걸음은 ChatGPT를 직접 써보는 것입니다. 이 글에서는 계정 생성부터 첫 대화까지를 안내합니다.

            ### 1. 계정 만들기

            1. [chat.openai.com](https://chat.openai.com)에 접속합니다.
            2. Google 계정 또는 이메일로 회원가입합니다.
            3. 이메일 인증을 완료하면 바로 사용할 수 있습니다.

            ### 2. 첫 대화

            로그인하면 나타나는 입력창에 다음과 같이 물어보세요:

            > "AI에 대해 초보자도 이해하기 쉽게 설명해줘"

            ChatGPT가 친절하게 답변할 것입니다. 여기서 중요한 건 **완벽한 질문을 하려고 애쓰지 않는 것**입니다. 일단 입력하고, 답변을 보고, 다시 질문을 다듬으면 됩니다.

            ### 3. 기본 인터페이스

            - **입력창**: 화면 하단의 텍스트 박스
            - **새 채팅**: 왼쪽 상단의 'New Chat' 버튼
            - **채팅 내역**: 왼쪽 사이드바에서 이전 대화 확인

            ### 4. TIP: 질문을 구체적으로

            나쁜 질문: "AI에 대해 알려줘"
            좋은 질문: "AI가 최근 1년 사이에 가장 크게 발전한 분야 3가지를 초보자에게 설명하듯 알려줘"

            ### 오늘의 미션

            ChatGPT에 가입하고 다음 중 하나를 질문해보세요:
            - "오늘 AI 뉴스 중 가장 중요한 것 요약해줘"
            - "내 직무(예: 마케팅)에서 AI를 어떻게 활용할 수 있을까?"
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            AI 활용의 첫걸음은 막상 어렵지 않습니다. <strong>ChatGPT 계정을 만들고 한 줄을 입력하는 것</strong>이 전부입니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 ChatGPT 인터페이스를 탐색하고, AI와의 첫 대화를 나눠보세요. 
            완벽한 질문은 없습니다. 일단 시작하는 것이 중요합니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: ChatGPT에 가입하고 첫 질문을 던져보세요.
            </p>
        """),
    },
    {
        "day": 2,
        "title": "프롬프트, 명확하게 물어보기",
        "content": textwrap.dedent("""\
            ## 프롬프트, 명확하게 물어보기

            AI에게 원하는 결과를 얻으려면 **명확한 프롬프트**가 핵심입니다. 프롬프트는 AI에게 내리는 지시문입니다.

            ### 프롬프트 5원칙

            1. **역할 부여**: "전문가로서 답변해줘" → AI의 출력 품질이 달라집니다
            2. **맥락 제공**: 배경 정보를 먼저 알려주세요
            3. **형식 지정**: "목록으로", "표로", "3문장으로" 등
            4. **예시 포함**: 원하는 답변의 예시를 하나 보여주세요
            5. **반복 & 다듬기**: 한 번에 완벽할 필요 없습니다

            ### 좋은 프롬프트 vs 나쁜 프롬프트

            ❌ "마케팅 전략 알려줘"
            ✅ "나는 1인 스타트업 창업자야. 예산이 없는 상황에서 AI 툴을 활용한 마케팅 전략 5가지를 알려줘. 각 전략마다 구체적인 실행 단계와 예상 비용을 포함해줘."

            ❌ "이메일 작성해줘"
            ✅ "나는 AI 교육 강사야. 수강생들에게 보낼 7일 강좌 홍보 이메일을 작성해줘. 전문적이면서도 친근한 톤으로, 강좌의 혜택 3가지를 강조해줘."

            ### 상황별 프롬프트 템플릿

            **요약할 때**: "다음 글을 3문장으로 요약해줘. 핵심 키워드를 굵게 표시해줘."
            **비교할 때**: "A와 B의 차이점을 표로 비교해줘. 장단점을 각각 포함해줘."
            **작성할 때**: "전문가 톤으로, 300자 내외로 작성해줘."

            ### 오늘의 미션

            어제 썼던 질문을 프롬프트 5원칙을 적용해서 다시 작성해보고, 결과가 어떻게 달라졌는지 비교해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            AI에게 원하는 결과를 얻는 비결은 <strong>명확한 프롬프트</strong>입니다. 같은 질문도 어떻게 던지느냐에 따라 답변 품질이 완전히 달라집니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 프롬프트 5원칙을 배우고, 어제의 질문을 한 단계 업그레이드해보세요. 
            생각보다 훨씬 큰 차이를 체감할 수 있습니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 프롬프트 5원칙을 적용해서 질문을 다시 작성해보세요.
            </p>
        """),
    },
    {
        "day": 3,
        "title": "이미지 생성, 한 장으로 시작",
        "content": textwrap.dedent("""\
            ## 이미지 생성, 한 장으로 시작

            텍스트만으로 이미지를 생성하는 시대입니다. DALL-E, Midjourney, 그리고 다양한 무료 도구가 있습니다.

            ### 🎨 주요 이미지 생성 도구

            | 도구 | 가격 | 특징 |
            |------|------|------|
            | **DALL-E 3** (ChatGPT 내장) | ChatGPT 유료 | 가장 접근성 좋음, 텍스트 표현 우수 |
            | **Midjourney** | 월 $10~ | 예술적 품질 최고, 디스코드 기반 |
            | **Stable Diffusion** | 무료 (로컬) | 커스터마이징 최강, GPU 필요 |
            | **Gemini** | 부분 무료 | 구글 생태계, 한글 프롬프트 강점 |

            ### 이미지 생성 프롬프트 팁

            1. **주제 + 스타일 + 분위기** 순서로 작성
            2. 스타일: "3D 렌더링", "수채화", "픽셀 아트", "사진 사실적"
            3. 분위기: "밝고 따뜻한", "어둡고 신비로운", "미니멀한"
            4. 구도: "클로즈업", "전신 샷", "드론 뷰"

            예시:
            > "고양이가 책상 위 노트북 앞에서 커피를 마시는 모습, 3D 렌더링 스타일, 따뜻한 조명, 클로즈업"

            ### 무료로 시작하기

            - **Bing Image Creator**: Microsoft 계정만 있으면 무료 (DALL-E 기반)
            - **Canva AI**: 무료 크레딧 제공, 템플릿과 연동
            - **Ideogram**: 무료, 텍스트 표현에 강함

            ### 오늘의 미션

            Bing Image Creator나 Canva AI에서 한 번 이미지를 생성해보세요. "자신이 잘하는 분야를 표현하는 이미지"를 주제로 도전해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            텍스트만으로 이미지를 만드는 시대입니다. <strong>원하는 이미지를 설명하는 것</strong>만으로 전문가 수준의 그림이 완성됩니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 DALL-E와 Midjourney의 차이, 그리고 무료로 시작하는 방법을 알려드립니다. 
            주제 + 스타일 + 분위기만 기억하세요.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: '자신의 분야'를 표현하는 이미지를 AI로 생성해보세요.
            </p>
        """),
    },
    {
        "day": 4,
        "title": "업무에 AI 끼얹기",
        "content": textwrap.dedent("""\
            ## 업무에 AI 끼얹기

            AI는 특정 직무에 국한된 도구가 아닙니다. 누구나 자신의 업무에 AI를 활용할 수 있습니다.

            ### 직무별 AI 활용법

            **📝 마케터**
            - SNS 카피 10가지 변형 생성 (프롬프트: "3가지 다른 톤으로 작성해줘")
            - 블로그 초안 작성 → AI로 1차 검토
            - 광고 문구 A/B 테스트용 변형 생성

            **💻 개발자**
            - 코드 리뷰: "이 코드의 보안 취약점을 찾아줘"
            - 버그 분석: 에러 메시지를 복붙하고 원인 추론
            - 리팩토링: "이 함수를 더 간결하게 바꿔줘"

            **🎨 디자이너**
            - 디자인 시스템 문서화
            - 색상 팔레트 추천: "모던하고 전문적인 느낌의 팔레트 3개"
            - UX 라이팅: 버튼 텍스트, 에러 메시지 다듬기

            **📊 기획자/PM**
            - 회의록 요약 및 액션 아이템 추출
            - 리스크 매트릭스 초안 생성
            - 사용자 스토리 작성 보조

            **🏪 자영업자**
            - 고객 응대 스크립트 준비
            - 상품 설명문 작성
            - SNS 홍보 문구 생성

            ### 실전 워크플로우 예시

            ```
            나쁜 예: AI에게 일을 시킨다 → 결과를 그대로 쓴다
            좋은 예: AI에게 초안을 시킨다 → 내가 검토한다 → 수정한다 → 완성한다
            ```

            AI는 **동료**이지 **대체자**가 아닙니다. AI가 만든 결과물은 항상 검토가 필요합니다.

            ### 오늘의 미션

            자신의 업무 중 하나를 AI에게 시켜보세요. "이 업무를 AI가 도와줄 수 있는 방법"을 먼저 AI에게 물어보고 실행해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            AI는 마케터, 개발자, 디자이너, 자영업자 누구에게나 유용합니다. <strong>"이걸 AI에게 시킬 수 없을까?"</strong>라는 질문이 중요합니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 직무별 실전 AI 활용법을 알려드립니다. AI를 '도구'가 아닌 '동료'처럼 활용하는 mindset이 핵심입니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 오늘 하던 업무 하나를 AI에게 시켜보세요.
            </p>
        """),
    },
    {
        "day": 5,
        "title": "AI 도구, 나에게 맞는 것 찾기",
        "content": textwrap.dedent("""\
            ## AI 도구, 나에게 맞는 것 찾기

            AI 도구는 매일 쏟아집니다. AI코리아24의 AI 도구 디렉토리(119개 등록)를 활용해 자신에게 맞는 도구를 찾는 방법을 알려드립니다.

            ### 도구 고르는 3단계

            1. **내 문제 정의하기**: "무엇을 해결하려는가?" → 도구는 수단입니다
            2. **비교군 좁히기**: 카테고리별 필터링 (글쓰기, 이미지, 코딩, 영상)
            3. **직접 써보기**: 무료 체험 → 유료 전환

            ### 분야별 추천 도구

            **✍️ 글쓰기/카피**
            - **Jasper**: 마케팅 카피 특화, 템플릿 다양함
            - **Writesonic**: 블로그, 광고, 랜딩 페이지
            - **Copy.ai**: 짧은 카피, A/B 테스트

            **🖼️ 이미지/디자인**
            - **Canva AI**: 올인원, 접근성 최고
            - **Adobe Firefly**: 포토샵 연동, 상업용 안전
            - **Leonardo.ai**: 게임 에셋 생성에 강함

            **💻 코딩**
            - **GitHub Copilot**: IDE 내장, 실시간 제안
            - **Cursor**: AI-first IDE
            - **Claude**: 복잡한 코드 구조화

            ### AI코리아24 도구 디렉토리 활용법

            [aikorea24.kr/tools/](https://aikorea24.kr/tools/)에서는:
            - 난이도별 필터링 (초급/중급/고급)
            - 가격대별 검색
            - 한국어 지원 여부 확인
            - 실제 사용자 리뷰

            ### 오늘의 미션

            AI코리아24 도구 디렉토리에서 자신의 업무와 관련된 도구 3개를 찾아보고, 가장 유용해 보이는 것 하나를 직접 사용해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            AI 도구는 매일 쏟아집니다. 모든 도구를 알 필요는 없습니다. <strong>내 문제를 해결하는 도구 하나</strong>를 찾는 것이 중요합니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 AI코리아24 도구 디렉토리(119개)를 활용한 도구 검색법과 분야별 추천을 알려드립니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 내 업무에 맞는 AI 도구 1개를 찾아 직접 사용해보세요.
            </p>
        """),
    },
    {
        "day": 6,
        "title": "AI 용어, 더 이상 어렵지 않게",
        "content": textwrap.dedent("""\
            ## AI 용어, 더 이상 어렵지 않게

            AI 뉴스를 읽다 보면 낯선 용어들이 등장합니다. 이 글에서는 꼭 알아야 할 용어 20선을 정리했습니다.

            ### 필수 용어 TOP 10

            | 용어 | 뜻 | 비유 |
            |------|-----|------|
            | **LLM** (Large Language Model) | 대규모 언어 모델, 글을 생성하는 AI | 초거대 두뇌 |
            | **GPT** (Generative Pre-trained Transformer) | OpenAI의 LLM | AI 비서 |
            | **파인튜닝(Fine-tuning)** | 기존 모델을 특정 용도로 추가 학습 | 전공 공부시키기 |
            | **토큰(Token)** | AI가 처리하는 글자 단위 | 1토큰 ≈ 한글 1자 |
            | **임베딩(Embedding)** | 글을 숫자로 변환해 AI가 이해하게 | 의미를 숫자로 압축 |
            | **RAG** (Retrieval-Augmented Generation) | 검색 + 생성 결합 기술 | AI가 책을 찾아보며 답변 |
            | **프롬프트(Prompt)** | AI에게 주는 지시문 | 명령어 |
            | **할루시네이션(Hallucination)** | AI가 사실처럼 거짓을 말하는 현상 | 거짓말 주의 |
            | **온도(Temperature)** | 창의성 조절 값 (0~1) | 0=보수적, 1=창의적 |
            | **멀티모달(Multimodal)** | 글+이미지+소리 동시 처리 | 오감 AI |

            ### 자주 듣는 용어 추가 10선

            **어텐션(Attention)** — AI가 문장에서 중요한 단어에 집중하는 메커니즘
            **트랜스포머(Transformer)** — 현대 AI의 기반 구조 (2017 Google 논문)
            **SLM(Small Language Model)** — 작고 가벼운 언어 모델 (온디바이스용)
            **에이전트(Agent)** — 스스로 판단하고 행동하는 AI
            **CoT(Chain of Thought)** — AI가 단계별로 추론하게 하는 기술
            **MoE(Mixture of Experts)** — 여러 전문가 모델을 상황에 따라 선택
            **양자화(Quantization)** — 모델을 가볍게 만드는 압축 기술
            **API** — 다른 프로그램이 AI를 호출하는 창구
            **오픈소스** — 누구나 사용/수정할 수 있는 공개 모델
            **클로즈드소스** — 기업이 독점하는 비공개 모델

            ### 용어 암기보다 중요한 것

            용어를 다 외울 필요는 없습니다. AI코리아24의 [AI 용어사전](https://aikorea24.kr/glossary/)을 북마크해두고, 모르는 용어가 나올 때마다 찾아보세요.

            ### 오늘의 미션

            오늘 배운 용어 중 3개를 골라, 자신의 말로 설명해보세요. (ChatGPT에게 "이해했는지 확인해줘"라고 물어보는 것도 좋은 방법입니다.)
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            LLM, RAG, 파인튜닝… 뉴스에 나오는 AI 용어가 어렵게 느껴진다면? <strong>핵심 20개만 알면 AI 뉴스가 읽힙니다.</strong>
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 필수 AI 용어를 쉬운 비유와 함께 정리했습니다. AI코리아24 용어사전과 함께 보면 더 좋습니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 배운 용어 3개를 자신의 말로 설명해보세요.
            </p>
        """),
    },
    {
        "day": 7,
        "title": "다음 단계로",
        "content": textwrap.dedent("""\
            ## 다음 단계로

            축하합니다. 7일 강좌를 완주하셨습니다! 🎉

            ### 7일간 배운 것

            1. ChatGPT 계정 만들고 첫 대화
            2. 프롬프트 5원칙으로 질문 업그레이드
            3. 이미지 생성 도구 이해
            4. 업무별 AI 활용법
            5. AI 도구 선택 가이드
            6. AI 용어 20선
            7. 그리고 여기, 다음 단계

            ### 이제 무엇을 하면 좋을까?

            **1. AI코리아24 커뮤니티에 참여하세요**
            [aikorea24.kr/community/](https://aikorea24.kr/community/)
            다른 수강생들과 경험을 공유하고, 질문하고, 답변하세요. 가르치는 것이 가장 좋은 학습입니다.

            **2. 매일 아침 AI 브리핑 구독**
            AI코리아24는 매일 아침 국내외 AI 소식을 큐레이션해서 보내드립니다.
            [구독하기](https://aikorea24.kr/)

            **3. 심층 분석 리포트 읽기**
            단순 뉴스 요약을 넘어, AI 업계의 흐름을 분석한 심층 리포트를 확인하세요.
            [브리핑 아카이브](https://aikorea24.kr/briefing/)

            **4. AI 도구 직접 써보기**
            119개의 AI 도구 중 아직 안 써본 것이 있다면 오늘이 시작하기 좋은 날입니다.
            [도구 디렉토리](https://aikorea24.kr/tools/)

            ### 학습은 계속됩니다

            AI 분야는 하루가 다르게 변합니다. 완강이 끝이 아니라, 이제부터가 시작입니다.
            AI코리아24는 앞으로도 계속해서 양질의 정보를 전달하겠습니다.

            궁금한 점이 있다면 커뮤니티에 언제든 질문해주세요. 💪
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            축하합니다! 7일 강좌의 마지막 날입니다. 🎉 <strong>끝까지 따라와 주셔서 감사합니다.</strong>
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 지난 6일간 배운 내용을 정리하고, 앞으로의 학습 로드맵을 알려드립니다. 
            AI코리아24 커뮤니티에서 계속 함께해요.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 커뮤니티에 완강 인증글을 남겨보세요!
            </p>
        """),
    },
]


# ─── SQL 생성 ────────────────────────────────────────────────────────

def build_sql(dry: bool = False) -> str:
    """전체 시드 SQL을 생성. dry=True면 콘솔 출력만."""
    stmts = []
    kst = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. 강좌 정보 INSERT
    stmts.append(f"""-- 1. courses
INSERT OR IGNORE INTO courses (slug, title, description, default_send_hour, total_days)
VALUES (
  '{COURSE_SLUG}',
  '{COURSE_TITLE}',
  '{COURSE_DESC}',
  18,
  7
);
""")

    # 2~. 각 레슨: post INSERT → course_lessons INSERT
    for lesson in LESSONS:
        day = lesson["day"]
        title = lesson["title"].replace("'", "''")
        content = lesson["content"].replace("'", "''")
        teaser = lesson["teaser"].replace("'", "''")

        stmts.append(f"""-- 2.{day}. post (visibility='members')
INSERT OR IGNORE INTO posts (user_id, title, content, category, visibility, author_email, author_name, created_at)
VALUES (
  1,
  '{title}',
  '{content}',
  'free',
  'members',
  'system@aikorea24.kr',
  'AI코리아24',
  '{kst}'
);
""")

    stmts.append("-- 3. course_lessons 매핑\n")
    for lesson in LESSONS:
        day = lesson["day"]
        title = lesson["title"].replace("'", "''")
        teaser = lesson["teaser"].replace("'", "''")

        # post_id는 subquery로 조회
        stmts.append(f"""INSERT OR IGNORE INTO course_lessons (course_slug, day_number, community_post_id, teaser_html)
SELECT '{COURSE_SLUG}', {day}, id, '{teaser}'
FROM posts
WHERE title = '{title}' AND visibility = 'members'
AND NOT EXISTS (
  SELECT 1 FROM course_lessons
  WHERE course_slug = '{COURSE_SLUG}' AND day_number = {day}
);
""")

    return "\n".join(stmts)


def run_wrangler(sql: str) -> bool:
    """wrangler d1 execute --remote로 SQL 실행"""
    try:
        result = subprocess.run(
            ["npx", "wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql],
            capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR,
        )
        if result.returncode != 0:
            print(f"❌ wrangler 실패: {result.stderr[:500]}")
            return False
        print(f"✅ wrangler 성공")
        return True
    except subprocess.TimeoutExpired:
        print("❌ wrangler timeout")
        return False
    except FileNotFoundError:
        print("❌ npx/wrangler not found. wrangler로 직접 실행하세요.")
        return False


def main():
    parser = argparse.ArgumentParser(description="7일 AI 입문 강좌 시드 데이터 생성")
    parser.add_argument("--dry", action="store_true", help="SQL만 출력하고 실행 안 함")
    parser.add_argument("--file", type=str, help="SQL을 파일로 저장 (경로)")
    args = parser.parse_args()

    sql = build_sql(dry=args.dry)

    if args.file:
        with open(args.file, "w", encoding="utf-8") as f:
            f.write(sql)
        print(f"SQL 저장 완료: {args.file}")
        return

    if args.dry:
        print(sql)
        return

    # 실제 실행
    print(f"=== 7일 AI 입문 강좌 시드 데이터 생성 ===")
    print(f"강좌: {COURSE_SLUG}")
    print(f"레슨 수: {len(LESSONS)}개\n")

    # 실행 전 확인
    response = input("D1(remote)에 시드 데이터를 삽입할까요? (y/N): ")
    if response.lower() != "y":
        print("취소됨.")
        return

    # migration 먼저 실행
    print("\n[1/2] 마이그레이션 실행...")
    migration_path = os.path.join(PROJECT_DIR, "scripts", "migrations", "20260710_add_course_system.sql")
    if os.path.exists(migration_path):
        with open(migration_path) as f:
            migration_sql = f.read()
        if not run_wrangler(migration_sql):
            print("마이그레이션 실패. 중단.")
            return
    else:
        print(f"마이그레이션 파일 없음: {migration_path}")

    # 시드 데이터 주입
    print("\n[2/2] 시드 데이터 삽입...")
    if not run_wrangler(sql):
        print("시드 데이터 삽입 실패.")
        return

    print(f"\n✅ 완료! {len(LESSONS)}개 레슨이 posts(D1)에 저장되고 course_lessons에 매핑되었습니다.")


if __name__ == "__main__":
    main()
