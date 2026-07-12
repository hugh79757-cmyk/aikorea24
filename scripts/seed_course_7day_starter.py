#!/usr/bin/env python3
"""7일 AI 입문 강좌 시드 데이터 생성기 (부트스트랩/구조 보강 전용).
post에 콘텐츠를 저장하고 course_lessons에 매핑 + 티저를 저장.

사용법:
  python3 scripts/seed_course_7day_starter.py           # wrangler d1 execute로 삽입
  python3 scripts/seed_course_7day_starter.py --dry     # SQL만 출력
  python3 scripts/seed_course_7day_starter.py --update  # 신규 레슨/매핑만 보강 (기존 본문 갱신 안 함)
  python3 scripts/seed_course_7day_starter.py --dry --update  # SQL 미리보기 (본문 갱신 없음 확인)
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
COURSE_TITLE = "첫 AI, 7일 — AI에게 말로 일을 시키는 첫 7일"
COURSE_DESC = (
    "코드를 쓰는 사람에서, AI를 지휘하는 사람으로. "
    "매일 저녁 5분, 7일 동안 AI 기초를 완성합니다. "
    "ChatGPT로 이메일 쓰기, 문서 요약, 자료 조사, 마케팅까지. "
    "완전 무료, 커뮤니티에서 질문하며 학습하세요."
)

LESSONS = [
    {
        "day": 0,
        "title": "오케스트레이터, 시작합니다",
        "content": textwrap.dedent("""\
            ## 오케스트레이터, 시작합니다

            환영합니다. 당신은 지금부터 **AI를 지휘하는 사람**이 되는 21일 여정의 첫발을 내디뎠습니다.

            ### 이 강좌의 목표

            코드를 짜는 사람이 아니라, **AI에게 말로 지시해서 결과를 만드는 사람**이 되는 것입니다.
            이 역할을 **오케스트레이터** — AI 악기들을 지휘하는 사람이라고 부릅니다.

            ### 21일 로드맵

            | 단계 | 강좌 | 기간 | 무엇을 얻는가 |
            |------|------|------|-------------|
            | **제로** | 첫 AI, 7일 | 1~7일차 | ChatGPT로 일을 시키는 법 |
            | **중간** | 0원 인프라, 7일 | 8~14일차 | AI로 사이트를 만들고 0원에 운영 |
            | **히어로** | 무료 에이전트, 7일 | 15~21일차 | 내가 자는 동안 AI가 일하게 한다 |

            ### 오케스트레이터의 증거

            ![스크린샷: 사장님이 만든 사이트 갤러리 — bazi, rotcha, zodiac, aikorea24](이미지 자리)
            _※ 스크린샷은 추후 추가됩니다. 아래 링크에서 직접 확인 가능합니다._

            저는 혼자서 80개가 넘는 사이트를 AI로 만들고 운영하고 있습니다.

            - [bazi.spattra.com](https://bazi.spattra.com) — AI로 만든 랜딩 페이지
            - [rotcha.kr](https://rotcha.kr) — AI로 세운 블로그
            - [zodiac.techpawz.com](https://zodiac.techpawz.com) — AI로 구축한 콘텐츠 사이트
            - [aikorea24.kr](https://aikorea24.kr) — 당신이 지금 보고 있는 이 사이트

            이 모든 사이트는 **월 0원**에 운영 중입니다. 도메인 비용(연 1~2만원)을 제외하면, 서버비, DB비, 배포비가 **전혀 들지 않습니다.**

            ### "월 0원"의 철학

            모든 도구는 무료입니다. 강좌를 따라가며 하나씩 만나게 됩니다.

            **제로 단계**에서 쓰는 도구:
            - **ChatGPT** — 대화형 AI — 무료

            **중간 단계**에서 추가되는 도구:
            - **Cloudflare** — 사이트·이메일·자동화 — 무료
            - **GitHub** — 코드 저장·자동 배포 — 무료
            - **Brevo** — 이메일 발송 — 무료 (일 300통)

            **히어로 단계**에서 추가되는 도구:
            - **DeepSeek / OpenCode Zen** — AI 코딩 — 무료

            돈을 쓰지 않고도 프로덕션 수준의 시스템을 만드는 법을 가르칩니다.

            ### 이곳은 혼자가 아닙니다

            매일 저녁 18:00, 오늘의 미션이 이메일로 도착합니다. 커뮤니티 게시판에서 다른 오케스트레이터들과 경험을 공유하고, 질문하면 제가 직접 답변합니다.

            ### 지금부터 21일간

            1일차부터 7일차까지는 **ChatGPT로 일을 시키는 법**에 집중합니다.
            8일차부터는 중간 강좌에서 **0원 인프라**로 사이트를 세웁니다.
            15일차부터는 히어로 강좌에서 **내가 자는 동안 AI가 일하게** 만듭니다.

            준비되셨나요? 지금부터 1일차로 이동합니다.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            21일 후, 당신은 AI를 지휘하는 사람이 됩니다. <strong>코드를 쓰는 사람에서, AI를 지휘하는 사람으로.</strong>
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            이 강좌는 ChatGPT 입문(제로) → 0원 인프라 구축(중간) → 무료 에이전트(히어로)로 이어지는 21일 로드맵의 첫 단계입니다. 
            모든 도구는 무료, 커뮤니티에서 질문하며 함께 성장하세요.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 21일 로드맵을 확인하고 1일차부터 시작하세요.
            </p>
        """),
    },
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
            4. 무료로도 충분히 사용 가능하며, 유료 요금제는 추가 기능이 필요할 때 업그레이드하면 됩니다.

            ### 2. 첫 대화

            로그인하면 나타나는 입력창에 다음과 같이 물어보세요:

            > "AI에 대해 초보자도 이해하기 쉽게 설명해줘"

            ChatGPT가 친절하게 답변할 것입니다. 여기서 중요한 건 **완벽한 질문을 하려고 애쓰지 않는 것**입니다. 일단 입력하고, 답변을 보고, 다시 질문을 다듬으면 됩니다.

            ### 3. 기본 인터페이스

            - **입력창**: 화면 하단의 텍스트 박스 — 여기에 질문을 입력합니다
            - **새 채팅**: 왼쪽 상단의 'New Chat' 버튼 — 새로운 대화를 시작할 때 사용
            - **채팅 내역**: 왼쪽 사이드바에서 이전 대화를 불러올 수 있음
            - **음성 입력**: 모바일 앱에서는 음성으로도 질문 가능

            ### 4. TIP: 질문을 구체적으로

            | 나쁜 질문 | 좋은 질문 |
            |-----------|-----------|
            | "AI에 대해 알려줘" | "AI가 최근 1년 사이에 가장 크게 발전한 분야 3가지를 초보자에게 설명하듯 알려줘" |
            | "마케팅 전략" | "예산 100만원으로 온라인 마케팅 채널 3개를 비교해줘" |

            ### 📖 함께 읽기

            - [AI와 대화하는 법 — 챗GPT 입력 형태 총정리](https://aikorea24.kr/blog/ai%EC%99%80-%EB%8C%80%ED%99%94%ED%95%98%EB%8A%94-%EB%B2%95-%EC%B1%97gpt/)
            - [ChatGPT 무료 vs 유료, 뭐가 다를까?](https://aikorea24.kr/blog/chatgpt-free-vs-paid/)

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
        "title": "이메일/문서 작성에 쓰기",
        "content": textwrap.dedent("""\
            ## 이메일/문서 작성에 쓰기

            ChatGPT의 가장 강력한 활용법 중 하나는 **글쓰기**입니다. 이메일, 보고서, 기획안, SNS 글 — AI가 초안을 잡아주면 작성 시간이 1/3로 줄어듭니다.

            ### AI 글쓰기의 기본 공식

            프롬프트를 작성할 때 이 4가지만 기억하세요:

            1. **목적과 독자 설정**: "누구에게 보내는 글인가?" (거래처? 팀원? 고객?)
            2. **톤 지정**: "공식적인/친근한/설득하는/간결한"
            3. **핵심 메시지**: "꼭 전달해야 할 한 가지는?"
            4. **분량 지정**: "3문장으로/200자 이내로/한 페이지 분량"

            ### 이메일 작성 예시

            ❌ "이메일 써줘"
            ✅ "나는 AI 교육 스타트업 대표야. 잠재 고객에게 보낼 7일 강좌 안내 이메일을 작성해줘. 전문적이면서도 친근한 톤으로, 강좌의 혜택 3가지를 강조해줘."

            ### 문서 작성 활용

            - **보고서**: "분기별 마케팅 성과 보고서 초안을 작성해줘. 목표 대비 실적, 주요 성과, 개선점 3개 섹션으로 나눠줘"
            - **기획안**: "SNS 마케팅 기획안을 작성해줘. 목표, 타겟, 전략, 예산, 일정 5개 항목으로 구성해줘"
            - **제안서**: "협업 제안서를 작성해줘. 우리 회사의 강점을 3가지 강조하고, 협업 시 기대 효과를 포함해줘"

            ### 실전 워크플로우

            ```
            AI 초안 → 내가 검토 → 수정 → 완성
            ```

            AI가 쓴 글은 항상 검토가 필요합니다. 특히 다음 3가지는 반드시 직접 확인하세요:
            - **사실 확인**: AI는 숫자나 날짜를 잘못 기억할 수 있습니다
            - **브랜드 톤**: 회사의 목소리가 일관된지 확인하세요
            - **개인 경험**: AI는 당신의 경험을 모릅니다 — 직접 경험을 덧붙이세요

            ### 📖 함께 읽기

            - [글 못 써도 괜찮아 — AI 블로그 콘텐츠 제작 완전 가이드](https://aikorea24.kr/blog/%EA%B8%80-%EB%AA%BB-%EC%8D%A8%EB%8F%84-%EA%B4%9C%EC%B0%AE%EC%95%84/)
            - [정부지원금 받는 사업계획서 AI 작성 4단계 공식](https://aikorea24.kr/blog/%EC%A0%95%EB%B6%80%EC%A7%80%EC%9B%90%EA%B8%88-%EB%B0%9B%EB%8A%94-%EC%82%AC%EC%97%85%EA%B3%84%ED%9A%8D%EC%84%9C-ai/)

            ### 오늘의 미션

            오늘 받은 업무 이메일 중 하나를 ChatGPT로 작성해보세요. 또는 최근에 썼던 보고서나 기획안의 초안을 AI로 잡아보고, 직접 검토한 뒤 얼마나 시간이 절약됐는지 기록해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            ChatGPT의 가장 강력한 기능은 글쓰기입니다. <strong>이메일, 보고서, 기획안의 초안을 AI가 잡아주면</strong> 작성 시간이 1/3로 줄어듭니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 목적·톤·핵심메시지·분량 — 4가지 요소만 기억해서 바로 업무에 써먹는 방법을 알려드립니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 오늘 받은 이메일 하나를 ChatGPT로 작성해보세요.
            </p>
        """),
    },
    {
        "day": 3,
        "title": "긴 문서 요약에 쓰기",
        "content": textwrap.dedent("""\
            ## 긴 문서 요약에 쓰기

            ChatGPT는 긴 글을 핵심만 뽑아 요약하는 데 탁월합니다. 회의록, 공지사항, 정책 문서, 계약서 — 5분씩 걸리던 읽기 작업을 30초로 줄여보세요.

            ### 직장인: 회의록 요약

            긴 회의록을 복사해서 이렇게 물어보세요:

            > "다음 회의록을 3문장으로 요약해줘. 결정된 사항, 액션 아이템, 담당자를 표로 정리해줘."

            ChatGPT가 핵심 결정사항과 누가 무엇을 해야 하는지 깔끔하게 정리해줍니다.

            ### 개인사업자: 공지·정책·계약서 요약

            개인사업자에게 회의록은 드물지만, 대신 이렇게 활용할 수 있습니다:

            - **정부 정책**: "다음 지원사업 공고문을 요약해줘. 지원 대상, 금액, 마감일, 필요 서류만 뽑아줘."
            - **계약서**: "이 계약서의 핵심 조항 5가지를 쉽게 설명해줘. 주의할 조항이 있으면 강조해줘."
            - **뉴스레터/공지**: "이 긴 공지에서 내가 꼭 알아야 할 것만 3줄로 요약해줘."

            ### 💡 더 나은 도구: NotebookLM

            이 작업에 **ChatGPT도 훌륭하지만**, 문서 요약에 특화된 더 강력한 도구가 있습니다.
            바로 Google의 **NotebookLM**입니다.

            NotebookLM은:
            - 수백 페이지 분량의 문서를 한 번에 업로드 가능
            - 출처 기반으로만 답변 (할루시네이션 없음)
            - 오디오 개요(팟캐스트)까지 생성

            NotebookLM에 대한 자세한 내용은 **6일차**에서 다룹니다.

            ### 📖 함께 읽기

            - [AI 실생활에서 사용하기 — 유튜브 1시간 영상을 30초 만에 요약하는 방법](https://aikorea24.kr/blog/ai-%EC%8B%A4%EC%83%9D%ED%99%9C%EC%97%90%EC%84%9C-%EC%82%AC%EC%9A%A9%ED%95%98%EA%B8%B0-%EC%9C%A0%ED%8A%9C%EB%B8%8C/)

            ### 오늘의 미션

            긴 문서 하나(회의록, 공지, 정책 문서, 기사 등)를 ChatGPT에 붙여넣고 요약해보세요. 요약 결과가 만족스러운지, 어떤 점이 부족한지 기록해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            5분씩 걸리던 문서 읽기를 <strong>30초로 줄이는 방법</strong>이 있습니다. ChatGPT에게 요약을 시키면 됩니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 회의록, 공지, 정책 문서, 계약서까지 — 상황별 요약 프롬프트를 알려드립니다. 
            문서 요약에 더 특화된 NotebookLM 이야기는 6일차에서 계속됩니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 긴 문서 하나를 ChatGPT로 요약해보세요.
            </p>
        """),
    },
    {
        "day": 4,
        "title": "자료 조사/번역에 쓰기",
        "content": textwrap.dedent("""\
            ## 자료 조사/번역에 쓰기

            ChatGPT는 정보 수집과 번역 작업에서도 강력한 도구입니다. 경쟁사 분석, 업계 동향 조사, 외국어 문서 번역 — 30분 걸리던 작업을 5분으로 줄여보세요.

            ### 자료 조사: 경쟁사·업계 분석

            ChatGPT의 **웹 검색 기능**(유료 버전)이나 간단한 프롬프트만으로도 인사이트를 얻을 수 있습니다.

            > "우리 업계(예: 카페 프랜차이즈)의 최근 트렌드 5가지를 알려줘. 각 트렌드마다 구체적인 사례와 적용 방법을 포함해줘."

            > "경쟁사 A와 B의 마케팅 전략을 비교해줘. SNS, 프로모션, 타겟 고객 3개 항목으로 분석해줘."

            ### 실전 팁: 더 정확한 조사를 위해

            ChatGPT의 학습 데이터는 특정 시점까지이므로, **최신 정보**가 필요하다면:
            - "2026년 기준으로"라고 명시하세요
            - 유료 버전의 웹 검색 기능을 활성화하세요
            - AI의 답변을 출발점으로 삼고, 직접 확인하는 습관을 들이세요

            ### 번역: 언어 장벽 없애기

            단순 번역을 넘어, ChatGPT는 맥락을 고려한 번역이 가능합니다.

            ❌ "이거 번역해줘"
            ✅ "다음 영문 계약서를 한국어로 번역해줘. 법률 용어는 원문을 병기해주고, 이해하기 쉬운 표현으로 풀어줘."

            ✅ "다음 일본어 기사를 한국어로 요약 번역해줘. 마케팅 관련 내용을 중심으로, 원문의 톤을 유지해줘."

            ### 핵심 마인드셋

            ```
            나쁜 예: AI가 찾아준 정보를 100% 신뢰한다
            좋은 예: AI가 찾아준 정보를 출발점으로 삼고, 직접 검증한다
            ```

            ### 📖 함께 읽기

            - [하루 30분 투자로 AI 마스터 — 소상공인 무료 교육 가이드](https://aikorea24.kr/blog/%ED%95%98%EB%A3%A8-30%EB%B6%84-%ED%88%AC%EC%9E%90%EB%A1%9C-ai/)
            - [혼자 운영하는 사장님 필수 AI 자동 상담 시스템 구축법](https://aikorea24.kr/blog/%ED%98%BC%EC%9E%90-%EC%9A%B4%EC%98%81%ED%95%98%EB%8A%94-%EC%82%AC%EC%9E%A5%EB%8B%98-%ED%95%84%EC%88%98/)

            ### 오늘의 미션

            오늘 하루, "이 정보를 AI에게 물어보자"라는 질문을 3번 이상 던져보세요. 경쟁사 정보, 업계 동향, 번역 등 무엇이든 좋습니다. AI의 답변을 출발점으로 삼아 직접 확인하는 습관을 길러보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            경쟁사 분석, 업계 조사, 외국어 번역 — 30분 걸리던 작업을 <strong>ChatGPT로 5분으로 줄이는 방법</strong>을 알려드립니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 자료 조사와 번역에 AI를 활용하는 실전 팁을 배웁니다. AI의 답변은 출발점이라는 마인드셋이 핵심입니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: "이 정보를 AI에게 물어보자"를 3번 실천해보세요.
            </p>
        """),
    },
    {
        "day": 5,
        "title": "마케팅/콘텐츠 + AI 도구, 나에게 맞는 것 찾기",
        "content": textwrap.dedent("""\
            ## 마케팅/콘텐츠 + AI 도구, 나에게 맞는 것 찾기

            자영업자에게 마케팅은 필수지만, 시간과 예산은 한정적입니다. AI를 활용하면 **마케팅 콘텐츠 제작**과 **도구 선택**을 동시에 해결할 수 있습니다.

            ### SNS·홍보 콘텐츠 AI로 만들기

            **SNS 홍보물**: Canva AI나 DALL-E로 상품 이미지 생성
            **쇼츠 영상**: AI로 대본 작성 + 편집
            **홍보 문구**: "오늘의 할인 상품을 소개하는 SNS 카피 3가지 톤(친근/세련/긴급)으로 작성해줘"
            **블로그 글**: 제품 사용 후기를 AI 초안 → 직접 검토 후 발행

            ### 오늘 배운 도구를 찾는 3단계

            **1단계. 내 문제 정의하기**
            "무엇을 해결하려는가?" — 도구는 수단입니다.
            - 디자인이 어렵다 → AI 이미지 생성 도구
            - 글쓰기가 부담된다 → AI 글쓰기 도구
            - 영상이 필요하다 → AI 영상 도구
            - 시간이 없다 → AI 자동화 도구

            **2단계. 비교군 좁히기**
            AI코리아24 도구 디렉토리에서 카테고리별 필터링으로 후보를 추리세요.
            - 이미지 | 글쓰기 | 영상 | 마케팅 | 생산성
            - 난이도: 초급 / 중급 / 고급
            - 가격대: 무료 / 부분 유료 / 유료

            **3단계. 직접 써보기**
            리뷰만 보지 말고 직접 사용해보세요. 대부분 무료 체험을 제공합니다.

            ### AI코리아24 도구 디렉토리 활용법

            [aikorea24.kr/tools/](https://aikorea24.kr/tools/)에서:
            - 119개 AI 도구를 난이도별/가격대별로 검색
            - 한국어 지원 여부 한눈에 확인
            - 실제 사용자 리뷰 참고

            ### 📖 함께 읽기

            - [디자인 못해도 OK — 무료 툴로 프로급 SNS 홍보물 만들기](https://aikorea24.kr/blog/%EB%94%94%EC%9E%90%EC%9D%B8-%EB%AA%BB%ED%95%B4%EB%8F%84-ok-%EB%AC%B4%EB%A3%8C/)
            - [소상공인 마케팅 비용 90% 절감하는 Canva와 ChatGPT 활용법](https://aikorea24.kr/blog/%EC%86%8C%EC%83%81%EA%B3%B5%EC%9D%B8-%EB%A7%88%EC%BC%80%ED%8C%85-%EB%B9%84%EC%9A%A9-90/)
            - [얼굴 안 나와도 되는 AI 쇼츠 제작으로 매출 올리기](https://aikorea24.kr/blog/%EC%96%BC%EA%B5%B4-%EC%95%88-%EB%82%98%EC%99%80%EB%8F%84-%EB%90%98%EB%8A%94/)
            - [AI가 뭔데 다들 난리야 — 5분 만에 이해하는 인공지능의 정체](https://aikorea24.kr/blog/ai%EA%B0%80-%EB%AD%94%EB%8D%B0-%EB%8B%A4%EB%93%A4-%EB%82%9C%EB%A6%AC%EC%95%BC/)

            ### 오늘의 미션

            AI코리아24 [도구 디렉토리](https://aikorea24.kr/tools/)에서 마케팅/콘텐츠 제작에 도움될 도구 2개를 찾고, 오늘 바로 하나를 써서 SNS 콘텐츠를 만들어보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            자영업자에게 마케팅은 필수지만, 시간과 예산은 한정적입니다. <strong>AI로 SNS 콘텐츠를 만들고, 내게 맞는 도구를 찾는 법</strong>을 한 번에 알려드립니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 마케팅 콘텐츠 제작 + AI코리아24 도구 디렉토리(119개) 활용법을 함께 다룹니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: AI 도구로 SNS 콘텐츠 하나를 만들어보세요.
            </p>
        """),
    },
    {
        "day": 6,
        "title": "프롬프트 원리 정리",
        "content": textwrap.dedent("""\
            ## 프롬프트 원리 정리

            지난 4일간(2~5일차) 우리는 이메일 쓰기, 문서 요약, 자료 조사, 마케팅 콘텐츠 — 다양한 작업을 ChatGPT로 해봤습니다. 오늘은 잠시 돌아보며 **"왜 어떤 프롬프트는 잘 되고 어떤 건 안 되는가"** 그 원리를 정리합니다.

            ### 3개 패턴으로 끝내는 프롬프트 원리

            복잡한 프롬프트 공식을 외울 필요 없습니다. 이 3가지만 기억하세요.

            **1. 역할 부여 (Role)**
            AI에게 특정 역할을 주면 출력 품질이 급상승합니다.
            > "너는 10년 경력의 마케터야" → "마케팅 전략 알려줘" 보다 훨씬 구체적인 답변

            **2. 예시 제공 (Example)**
            원하는 답변의 형식을 보여주면 AI가 방향을 정확히 잡습니다.
            > "이런 식으로 써줘: [예시]" → 막연한 지시보다 결과물 일관성이 높아짐

            **3. 단계 나누기 (Steps)**
            복잡한 작업은 단계로 쪼개서 지시하세요.
            > "1단계: 자료를 분석해줘. 2단계: 분석 결과를 바탕으로 3가지 전략을 제안해줘."

            ### NotebookLM vs ChatGPT: 언제 무엇을 쓸까?

            3일차에서 **NotebookLM**을 잠시 언급했습니다. NotebookLM은 Google의 AI 노트북 도구로, 문서 요약과 질의응답에 특화되어 있습니다.

            | 비교 | ChatGPT | NotebookLM |
            |------|---------|-----------|
            | 강점 | 다양한 작업 (글쓰기, 코딩, 분석) | 문서 기반 질의응답, 요약 |
            | 할루시네이션 | 가능 | 거의 없음 (출처 기반) |
            | 문서 업로드 | 제한적 | 수백 페이지 가능 |
            | 활용 | 이메일, 마케팅, 브레인스토밍 | 논문, 리포트, 계약서 분석 |

            **결론**: NotebookLM은 **"내 문서에 대해 질문하기"** 에 특화되어 있습니다. ChatGPT는 **"무언가를 생성하거나 변환하는 작업"** 에 강합니다. 둘은 경쟁 관계가 아니라, 상황에 따라 선택하는 도구입니다.

            ### 프롬프트를 더 깊이 알고 싶다면

            AI코리아24 블로그에는 프롬프트 공식 시리즈가 준비되어 있습니다. 3개 패턴을 기본으로 삼고, 필요할 때 아래 글들을 참고하세요.

            ### 📖 함께 읽기 — 프롬프트 공식 시리즈

            - [프롬프트 기초 — AI에게 원하는 결과를 얻는 말하기 법칙](https://aikorea24.kr/blog/peurompeuteu-gicho-aiege-wonhaneun/)
            - [ChatGPT 프롬프트 5가지 공식 — 원하는 답을 얻는 핵심](https://aikorea24.kr/blog/chatgpt-%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-5%EA%B0%80%EC%A7%80-%EA%B3%B5%EC%8B%9D/)
            - [프롬프트 TAG 공식 — 가장 심플하고 빠른 프레임워크](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-tag-%EA%B3%B5%EC%8B%9D-%EA%B0%80%EC%9E%A5/)
            - [프롬프트 RISE 공식 — 분석과 보고서에 강한 프레임워크](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-rise-%EA%B3%B5%EC%8B%9D-%EB%B6%84%EC%84%9D%EA%B3%BC/)
            - [프롬프트 CO-STAR 공식 — 마케팅과 고객 대상 글](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-co-star-%EA%B3%B5%EC%8B%9D/)
            - [프롬프트 CREATE 공식 — 콘텐츠와 창작 작업](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-create-%EA%B3%B5%EC%8B%9D-%EC%BD%98%ED%85%90%EC%B8%A0%EC%99%80/)
            - [프롬프트 RISEN 공식 — RISE보다 정교한 결과가 필요할 때](https://aikorea24.kr/blog/%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8-risen-%EA%B3%B5%EC%8B%9D-rise%EB%B3%B4%EB%8B%A4/)

            ### 오늘의 미션

            2~5일차에 썼던 프롬프트 중 하나를 골라, 오늘 배운 3개 패턴(역할 부여, 예시 제공, 단계 나누기)을 적용해서 다시 작성해보세요. 개선 전과 후의 차이를 비교해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            지난 4일간 써본 프롬프트, 왜 어떤 건 잘 되고 어떤 건 안 됐을까요? <strong>복잡한 공식이 아닌 3개 패턴</strong>으로 원리를 정리합니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 역할 부여, 예시 제공, 단계 나누기 — 이 3가지만으로 프롬프트 품질을 높이는 법을 알려드립니다. NotebookLM과 ChatGPT 비교도 함께 다룹니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 2~5일차 프롬프트 중 하나를 3개 패턴으로 개선해보세요.
            </p>
        """),
    },
    {
        "day": 7,
        "title": "습관화 + 다음 단계로",
        "content": textwrap.dedent("""\
            ## 습관화 + 다음 단계로

            축하합니다! 🎉 7일 강좌를 완주하셨습니다. 오늘은 그간 배운 내용을 정리하고, AI를 업무에 **습관으로 만드는 법**과 **다음 단계**를 안내합니다.

            ### 7일간의 정리

            | 일차 | 주제 | 핵심 내용 |
            |------|------|----------|
            | 1일차 | ChatGPT 첫 시작 | 계정 생성, 첫 대화, 기본 인터페이스 |
            | 2일차 | 이메일/문서 작성 | AI 글쓰기 4요소, 업무 문서 초안 작성 |
            | 3일차 | 긴 문서 요약 | 회의록·정책·계약서 요약, NotebookLM |
            | 4일차 | 자료 조사/번역 | 경쟁사 분석, 업계 조사, 번역 활용 |
            | 5일차 | 마케팅/콘텐츠 + 도구 찾기 | SNS 콘텐츠, AI 도구 3단계 선정법 |
            | 6일차 | 프롬프트 원리 | 역할 부여, 예시 제공, 단계 나누기 |
            | 7일차 | 습관화 + 완강 | 🎉 습관 루틴, 완강 인증, 다음 강좌 |

            ### AI를 업무에 습관화하는 3가지 루틴

            **① 매일 아침 ChatGPT를 먼저 켠다**
            이메일을 쓰기 전, 보고서를 시작하기 전, 무언가 검색하기 전 — 일단 ChatGPT를 엽니다.

            **② "이걸 AI에게 시킬 수 없을까?"를 입버릇처럼**
            귀찮은 일이 생길 때마다 이 질문을 먼저 던져보세요. AI에게 시키는 데 1분, 검토하는 데 2분. 직접 하는 것보다 항상 빠릅니다.

            **③ 하루 5분 AI 일지**
            "오늘 AI로 해결한 일"을 한 줄씩 기록해보세요. 1주일이면 AI 활용이 자연스러워집니다.

            ### 완강 인증 — 커뮤니티에서 함께해요

            [AI코리아24 커뮤니티](https://aikorea24.kr/community/)에 **"7일 전과 7일 후의 차이"** 한 줄을 남겨주세요.
            다른 수강생들과 경험을 공유하고, 질문하고, 답변하세요. 가르치는 것이 가장 좋은 학습입니다.

            ### 🔜 다음 강좌: "사장님의 0원 인프라"

            이 강좌를 완강하셨습니다. 이제 다음 단계가 준비되어 있습니다.

            **"사장님의 0원 인프라" (7일 강좌)** 에서는:
            - 무료 AI 도구로 나만의 업무 시스템 구축하기
            - AI 챗봇으로 24시간 고객 응대 자동화
            - Cloudflare Pages로 웹사이트 0원 배포
            - AI 자동화로 반복 업무 없애기

            *이 강좌는 곧 오픈됩니다. 커뮤니티 공지를 기다려주세요.*

            ### 📖 함께 읽기

            - [하루 30분 투자로 AI 마스터 — 소상공인 무료 교육 가이드](https://aikorea24.kr/blog/%ED%95%98%EB%A3%A8-30%EB%B6%84-%ED%88%AC%EC%9E%90%EB%A1%9C-ai/)
            - [바이브 코딩 시작하기 — ChatGPT와 VS Code만 있으면 당신도 개발자](https://aikorea24.kr/blog/%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9-%EC%8B%9C%EC%9E%91%ED%95%98%EA%B8%B0-chatgpt%EC%99%80/)

            ### 오늘의 미션

            오늘 배운 습관화 루틴 중 하나를 오늘 당장 실천해보세요. 그리고 커뮤니티에 7일 간의 변화를 한 줄로 남겨주세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            축하합니다! 7일 강좌 완주! 🎉 <strong>이제 AI를 업무에 습관으로 만드는 법</strong>과 다음 단계를 안내합니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘은 7일간의 배움을 정리하고, AI를 일상에 고정하는 3가지 루틴을 알려드립니다. 
            그리고 다음 강좌 "사장님의 0원 인프라" 티저도 공개합니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 습관 루틴 하나를 실천하고 커뮤니티에 완강 인증을 남겨보세요.
            </p>
        """),
    },
]


# ─── SQL 생성 ────────────────────────────────────────────────────────

def build_sql(update_mode: bool = False) -> str:
    """전체 시드 SQL을 생성.
    
    Args:
        update_mode: True면 INSERT 대신 UPDATE로 기존 post 콘텐츠 갱신
    """
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

    if update_mode:
        stmts.append("-- 2. courses UPDATE (기존 row 갱신)\n")
        stmts.append(f"""UPDATE courses SET
  title = '{COURSE_TITLE.replace("'", "''")}',
  description = '{COURSE_DESC.replace("'", "''")}'
WHERE slug = '{COURSE_SLUG}';
""")

        stmts.append("-- 3. post + course_lessons 신규 보강 (INSERT OR IGNORE만, 기존 본문 갱신 안 함)\n")
        for lesson in LESSONS:
            day = lesson["day"]
            title = lesson["title"].replace("'", "''")
            content = lesson["content"].replace("'", "''")
            teaser = lesson["teaser"].replace("'", "''")

            # INSERT if post doesn't exist (신규 lesson)
            stmts.append(f"""-- {day}. post ensure
INSERT OR IGNORE INTO posts (user_id, title, content, category, visibility, author_email, author_name, created_at)
VALUES (1, '{title}', '{content}', '강의', 'members', 'system@aikorea24.kr', 'AI코리아24', '{kst}');
""")
            # INSERT if course_lessons mapping doesn't exist (신규 lesson)
            stmts.append(f"""-- {day}. course_lessons ensure
INSERT OR IGNORE INTO course_lessons (course_slug, day_number, community_post_id, teaser_html)
SELECT '{COURSE_SLUG}', {day}, id, '{teaser}'
FROM posts
WHERE title = '{title}' AND visibility = 'members'
AND NOT EXISTS (
  SELECT 1 FROM course_lessons
  WHERE course_slug = '{COURSE_SLUG}' AND day_number = {day}
);
""")
    else:
        # INSERT 모드 (최초 실행): post INSERT → course_lessons INSERT
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
  '강의',
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
    """wrangler d1 execute --remote --file로 SQL 실행 (긴 SQL 대응)"""
    tmp = os.path.join(PROJECT_DIR, "scripts", "_tmp_update.sql")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(sql)
        result = subprocess.run(
            ["npx", "wrangler", "d1", "execute", "aikorea24-db", "--remote", "--file", tmp],
            capture_output=True, text=True, timeout=120, cwd=PROJECT_DIR,
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
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    parser = argparse.ArgumentParser(description="7일 AI 입문 강좌 시드 데이터 생성")
    parser.add_argument("--dry", action="store_true", help="SQL만 출력하고 실행 안 함")
    parser.add_argument("--file", type=str, help="SQL을 파일로 저장 (경로)")
    parser.add_argument("--update", action="store_true", help="신규 레슨/매핑만 보강 (기존 본문은 갱신 안 함)")
    args = parser.parse_args()

    mode = "UPDATE" if args.update else "INSERT"
    sql = build_sql(update_mode=args.update)

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
    action_label = "업데이트" if args.update else "삽입"
    response = input(f"D1(remote)에 시드 데이터를 {action_label}할까요? (y/N): ")
    if response.lower() != "y":
        print("취소됨.")
        return

    # migration 먼저 실행 (INSERT 모드에서만)
    if not args.update:
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
    print(f"\n[{'2/2' if not args.update else '1/1'}] 시드 데이터 {action_label}...")
    if not run_wrangler(sql):
        print(f"시드 데이터 {action_label} 실패.")
        return

    print(f"\n✅ 완료! {len(LESSONS)}개 레슨이 posts(D1)에 {action_label}되었습니다.")


if __name__ == "__main__":
    main()
