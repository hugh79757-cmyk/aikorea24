#!/usr/bin/env python3
"""0원 인프라 강좌 시드 데이터 생성기 (부트스트랩/구조 보강 전용).

사용법:
  python3 scripts/seed_course_7day_infra.py           # wrangler d1 execute로 삽입
  python3 scripts/seed_course_7day_infra.py --dry     # SQL만 출력
  python3 scripts/seed_course_7day_infra.py --update  # 신규 레슨/매핑만 보강 (기존 본문 갱신 안 함)
  python3 scripts/seed_course_7day_infra.py --dry --update  # SQL 미리보기 (본문 갱신 없음 확인)
"""
import argparse
import os
import subprocess
import textwrap
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COURSE_SLUG = "7day-infra"
COURSE_TITLE = "0원 인프라, 7일 — AI에게 사이트를 만들라 하고, 0원으로 운영한다"
COURSE_DESC = (
    "코드를 쓰는 사람에서, AI를 지휘하는 사람으로. "
    "AI로 첫 사이트를 만들고, 도메인을 연결하고, 이메일을 세팅하고, "
    "자동화까지. 월 0원에 운영하는 법을 7일 만에 배웁니다."
)

LESSONS = [
    {
        "day": 8,
        "title": "첫 도메인, 첫 사이트",
        "content": textwrap.dedent("""\
            ## 첫 도메인, 첫 사이트

            제로 강좌를 완강한 당신은 이제 ChatGPT로 일을 시킬 줄 압니다. 이번 강좌에서는 **AI가 만든 코드를 세상에 공개**합니다.

            ### 오늘의 목표: 내 이름을 가진 사이트를 만든다

            오늘 하루면 됩니다. 도메인을 사고, Cloudflare에 연결하고, 첫 페이지를 배포합니다.

            ### 1. 도메인 구매

            Cloudflare Registrar에서 `.kr` 도메인을 구매합니다. 연 1~2만원. 이게 앞으로 7일간 **유일한 현금 지출**입니다. Cloudflare Registrar는 등록가에 추가 마진을 붙이지 않아 가장 싼 채널입니다.

            ### 2. Cloudflare에 도메인 연결

            도메인을 사면 네임서버(nameserver)를 Cloudflare 것으로 변경하라는 안내가 옵니다. 이게 무슨 말인지 몰라도 됩니다. Cloudflare가 안내하는 대로 따라적기만 하면 됩니다.

            Cloudflare에 연결하면 그 순간부터:
            - DNS가 보호되고 (DDoS 방어)
            - Workers, Email Routing, Pages를 모두 무료로 쓸 수 있음
            - SSL 인증서가 자동 발급됨

            ### 3. 첫 랜딩 페이지

            AI에게 시킵니다:

            > "Astro 프레임워크로 간단한 개인 랜딩 페이지를 만들어줘. 내 소개, 연락처, SNS 링크가 포함된 한 페이지짜리 사이트. 한국어로."

            AI가 만들어준 코드를 GitHub 저장소에 올리고, Cloudflare Pages에 연결하면 **5분 안에 사이트가 배포**됩니다. https://내도메인.kr 로 접속해보세요.

            ### 📖 함께 읽기

            - [코딩 몰라도 괜찮아 — 1인기업을 위한 Cloudflare 무료 인프라 완벽 가이드](https://aikorea24.kr/blog/%EC%BD%94%EB%94%A9-%EB%AA%B0%EB%9D%BC%EB%8F%84-%EA%B4%9C%EC%B0%AE%EC%95%84-1%EC%9D%B8%EA%B8%B0%EC%97%85%EC%9D%84/)
            - [웹사이트를 0원에 배포하는 방법: Cloudflare Pages 가이드](https://aikorea24.kr/blog/cloudflare-free-deploy/)
            - [웹사이트를 어디에 만들지 — 티스토리/네이버/워드프레스/Astro/Hugo](https://aikorea24.kr/blog/wepsaiteureul-eodie-mandeulji-tiseutori/)

            ### 오늘의 미션

            도메인을 구매하고 Cloudflare Pages에 첫 사이트를 배포해보세요. 완료되면 내도메인.kr이 열리는 스크린샷을 커뮤니티에 공유해주세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            제로 강좌를 완강한 당신, 이제 <strong>AI가 만든 코드를 세상에 공개</strong>할 차례입니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            오늘 하루면 됩니다. 도메인을 사고, Cloudflare에 연결하고, AI가 만든 첫 페이지를 배포합니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 도메인을 사고, 첫 사이트를 배포해보세요.
            </p>
        """),
    },
    {
        "day": 9,
        "title": "info@내도메인 — 0원 이메일",
        "content": textwrap.dedent("""\
            ## info@내도메인 — 0원 이메일

            사이트가 생겼으면 이제 **내 도메인의 이메일 주소**를 만듭니다. `info@내도메인.kr` — 이 주소 하나로 당신은 `@gmail.com`과는 다른 전문성이 생깁니다.

            ### Cloudflare Email Routing

            Cloudflare Email Routing은 **내 도메인으로 오는 이메일을 내 Gmail로 자동 전달**해주는 무료 서비스입니다. 메일 서버를 운영할 필요가 없고, Gmail로 받아서 보내기만 하면 됩니다.

            설정 방법:
            1. Cloudflare 대시보드 → Email → Email Routing
            2. 받은편지함에 내 Gmail 주소 등록
            3. info@내도메인.kr로 오는 모든 메일이 Gmail로 도착

            ### 이메일 보내기

            받기만 하면 반쪽입니다. 보내기도 내 도메인으로 하고 싶다면:
            - Gmail에서 `info@내도메인.kr`로 **보내는 주소 등록**
            - Cloudflare Email Routing이 SMTP를 지원하므로 인증만 하면 Gmail에서 발신 가능

            이렇게 하면 `info@aikorea24.kr` → Gmail 도착, Gmail에서 `info@aikorea24.kr`로 발신까지 — 완전 무료입니다.

            ### 📖 함께 읽기

            - [Cloudflare 역사를 알면 서비스가 보인다 — DNS에서 풀스택 플랫폼까지](https://aikorea24.kr/blog/cloudflare-%EC%97%AD%EC%82%AC%EB%A5%BC-%EC%95%8C%EB%A9%B4-%EC%84%9C%EB%B9%84%EC%8A%A4%EA%B0%80/)

            ### 오늘의 미션

            Cloudflare Email Routing을 설정하고, `info@내도메인.kr`로 테스트 메일을 보내보세요. Gmail에서 받아지면 성공입니다.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            사이트가 생겼으면 이제 <strong>내 도메인의 이메일</strong>을 만듭니다. @gmail.com과는 다른 전문성.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            Cloudflare Email Routing으로 info@내도메인.kr을 만들고, Gmail에서 받고 보내기까지 — 전부 무료입니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: info@내도메인.kr을 만들고 테스트 메일을 보내보세요.
            </p>
        """),
    },
    {
        "day": 10,
        "title": "콘텐츠 사이트 하나 더",
        "content": textwrap.dedent("""\
            ## 콘텐츠 사이트 하나 더

            랜딩 페이지 하나로는 부족합니다. 진짜 0원 인프라는 **여러 사이트를 하나의 계정으로 운영**하는 힘에서 나옵니다.

            ### 같은 계정, 다른 사이트

            Cloudflare Pages와 GitHub만 있으면 사이트 몇 개든 만들 수 있습니다. 추가 비용은 0원.

            - [bazi.spattra.com](https://bazi.spattra.com) — 운세/타로 랜딩 페이지 (Astro)
            - [zodiac.techpawz.com](https://zodiac.techpawz.com) — 별자리 콘텐츠 사이트 (Astro)

            두 사이트 모두 Cloudflare Pages + GitHub로 운영됩니다. 도메인만 각각 연결되어 있을 뿐, 인프라 비용은 전혀 들지 않습니다.

            ### 랜딩 페이지 vs 콘텐츠 사이트

            | 유형 | 목적 | 예시 |
            |------|------|------|
            | 랜딩 페이지 | 나/서비스를 소개 | 내도메인.kr, bazi.spattra.com |
            | 콘텐츠 사이트 | 정보를 꾸준히 발행 | zodiac.techpawz.com |

            콘텐츠 사이트는 블로그 형태로, 꾸준히 글을 써서 방문자를 모읍니다. 랜딩 페이지와 구조는 같지만, 콘텐츠가 계속 추가된다는 점이 다릅니다.

            ### AI로 콘텐츠 만들기

            > "zodiac.techpawz.com에 올릴 물병자리 운세 글을 작성해줘. 2026년 7월 넷째 주, 3문단 분량, 친근한 톤으로."

            AI가 초안을 쓰면 검토해서 올리면 됩니다. 글쓰기부터 배포까지, 한 사람이 운영하는 콘텐츠 사이트가 완성됩니다.

            ### 📖 함께 읽기

            - [웹사이트를 어디에 만들지 — 티스토리/네이버/워드프레스/Astro/Hugo](https://aikorea24.kr/blog/wepsaiteureul-eodie-mandeulji-tiseutori/)
            - [빌드/푸쉬/배포의 차이점 쉽게 이해하기](https://aikorea24.kr/blog/%EB%B9%8C%EB%93%9C-%ED%91%B8%EC%89%AC-%EB%B0%B0%ED%8F%AC%EC%9D%98-%EC%B0%A8%EC%9D%B4%EC%A0%90/)

            ### 오늘의 미션

            랜딩 페이지 외에 콘텐츠를 발행할 사이트를 하나 더 만들어보세요. 주제는 당신이 가장 잘 아는 분야로 — AI로 첫 글을 작성해서 배포까지 해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            진짜 0원 인프라는 <strong>여러 사이트를 하나의 계정으로 운영</strong>하는 힘에서 나옵니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            Cloudflare Pages + GitHub로 사이트 몇 개든 만들 수 있습니다. 추가 비용 0원. 랜딩 페이지와 콘텐츠 사이트의 차이를 배웁니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 두 번째 사이트를 만들어 콘텐츠를 발행해보세요.
            </p>
        """),
    },
    {
        "day": 11,
        "title": "이메일 구독자 모으기",
        "content": textwrap.dedent("""\
            ## 이메일 구독자 모으기

            사이트가 생겼고, 내 도메인 이메일도 있습니다. 이제 **구독자를 모을 차례**입니다. 이메일 구독은 당신과 방문자를 연결하는 가장 직접적인 채널입니다.

            ### Brevo — 무료 이메일 발송

            Brevo는 하루 300통까지 무료로 이메일을 보낼 수 있는 서비스입니다. AI 뉴스 브리핑, 강좌 발송, 마케팅 메일까지 — 지금 이 강좌를 발송하는 시스템이 바로 Brevo입니다.

            ### 사이트에 구독 폼 달기

            AI에게 시킵니다:

            > "내 Astro 사이트에 Brevo 구독 폼을 넣어줘. 이메일 주소만 입력받는 간단한 형태. 사이트 하단에 위치."

            AI가 만들어준 HTML을 사이트에 넣고, Brevo와 연결하면 방문자가 이메일을 남길 때마다 Brevo 연락처에 자동으로 추가됩니다.

            ### AI 뉴스 브리핑 — 당신의 첫 구독 콘텐츠

            AI 뉴스 브리핑은 AI코리아24가 매일 아침 발송하는 이메일 뉴스레터입니다. 이런 콘텐츠를 당신도 만들 수 있습니다:
            - 매일 아침 AI 뉴스 3선 요약
            - 주간 업계 동향 정리
            - 당신 사이트의 새 글 알림

            ### 📖 함께 읽기

            - [혼자 운영하는 사장님 필수 AI 자동 상담 시스템 구축법](https://aikorea24.kr/blog/%ED%98%BC%EC%9E%90-%EC%9A%B4%EC%98%81%ED%95%98%EB%8A%94-%EC%82%AC%EC%9E%A5%EB%8B%98-%ED%95%84%EC%88%98/)

            ### 오늘의 미션

            Brevo 계정을 만들고, 내 사이트에 구독 폼을 추가해보세요. 그런 다음 다른 이메일로 직접 구독해보고 확인 메일이 오는지 테스트해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            사이트가 있고, 이메일도 있습니다. 이제 <strong>구독자를 모을 차례</strong>입니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            Brevo로 무료 이메일 발송을 설정하고, 사이트에 구독 폼을 달아보세요. 내 첫 뉴스레터 발행까지.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: Brevo 계정 생성 + 사이트에 구독 폼 추가하기.
            </p>
        """),
    },
    {
        "day": 12,
        "title": "Workers 첫 코드 — 자동화 첫걸음",
        "content": textwrap.dedent("""\
            ## Workers 첫 코드 — 자동화 첫걸음

            이제 진짜 오케스트레이터의 세계로 들어옵니다. **Cloudflare Workers**는 서버 없이 코드를 실행하는 환경입니다. 당신이 작성한 코드가 Cloudflare의 글로벌 네트워크에서 실행됩니다.

            ### Workers가 뭔가요?

            Workers는 간단합니다:
            - 서버가 필요 없음 (서버리스)
            - 코드를 쓰면 Cloudflare가 전 세계에서 실행
            - 무료 요금제로 일 10만 건 요청 처리 가능

            ### 첫 Workers: 폼 → 자동 답장

            오늘 만들 것은 **구독 폼을 받으면 자동으로 확인 이메일을 보내는 Worker**입니다.

            AI에게 시킵니다:

            > "Cloudflare Workers로 POST 요청을 받으면 Brevo API를 호출해서 연락처를 추가하고, 확인 이메일을 보내는 코드를 작성해줘. 환경 변수는 BREVO_API_KEY로 받아."

            AI가 만들어준 코드를 Cloudflare Workers에 배포합니다. 이제 누군가 내 사이트에서 구독하면, Worker가 자동으로 Brevo를 호출하고 구독자가 추가됩니다.

            ### 이것이 자동화의 시작입니다

            Workers 하나로 당신은 "사람이 하는 일"을 "코드가 하는 일"로 바꾸기 시작합니다. 나중에는 Workers 여러 개가 서로 협력해서, 자는 동안에도 시스템이 돌아가게 만들 수 있습니다.

            ### 📖 함께 읽기

            - [Cloudflare 무료의 한계 — 빌드 제한과 하루 1회 배포 전략](https://aikorea24.kr/blog/cloudflare-muryoui-hangye-bildeu/)
            - [Cloudflare 역사를 알면 서비스가 보인다](https://aikorea24.kr/blog/cloudflare-%EC%97%AD%EC%82%AC%EB%A5%BC-%EC%95%8C%EB%A9%B4-%EC%84%9C%EB%B9%84%EC%8A%A4%EA%B0%80/)

            ### 오늘의 미션

            Cloudflare Workers에 첫 코드를 배포해보세요. 구독 폼에서 전송한 데이터를 Worker가 받아서 Brevo에 저장하는지 테스트해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            진짜 오케스트레이터의 세계로 들어옵니다. <strong>서버 없이 코드를 실행하는 Cloudflare Workers</strong>.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            첫 Workers: 구독 폼 데이터를 받아서 자동으로 Brevo 연락처에 추가하고 확인 메일을 보냅니다. 자동화의 시작입니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 첫 Worker를 배포하고 자동 응답을 테스트해보세요.
            </p>
        """),
    },
    {
        "day": 13,
        "title": "Hugo 블로그 + 정적 배포",
        "content": textwrap.dedent("""\
            ## Hugo 블로그 + 정적 배포

            지금까지 Astro로 사이트를 만들었습니다. 하지만 **또 다른 선택지**가 있습니다. Hugo는 Go 언어로 만들어진 정적 사이트 생성기로, Astro보다 더 가볍고 빠릅니다.

            ### Hugo가 필요한 순간

            Astro는 현대적이고 유연하지만, **블로그에 특화된 도구는 아닙니다**. Hugo는 블로그에 특화되어 있어:
            - 글쓰기에 집중된 구조
            - 수천 개의 글도 1초 안에 빌드
            - 테마 시스템이 잘 갖춰져 있음

            [rotcha.kr](https://rotcha.kr)이 Hugo로 만들어진 블로그입니다.

            ### AI로 Hugo 블로그 만들기

            > "Hugo 블로그를 만들어줘. 기본 테마(PaperMod)로 설정하고, about.md와 첫 포스트를 포함해줘. 한국어 블로그야."

            AI가 만들어준 Hugo 사이트를 로컬에서 확인하고, GitHub에 푸시하면 Cloudflare Pages가 자동 배포합니다.

            ### 수동 배포의 의미

            지금까지 Astro 사이트는 AI가 코드를 만들어줬습니다. Hugo는 조금 다릅니다:
            - 로컬에서 `hugo` 명령어로 빌드
            - 생성된 `public/` 폴더를 GitHub에 푸시
            - Cloudflare Pages가 배포

            이 과정이 익숙해지면, 어떤 정적 사이트든 0원에 운영할 수 있습니다. 80개 사이트도 같은 원리입니다.

            ### 📖 함께 읽기

            - [웹사이트를 어디에 만들지 — 티스토리/네이버/워드프레스/Astro/Hugo](https://aikorea24.kr/blog/wepsaiteureul-eodie-mandeulji-tiseutori/)
            - [GitHub Cloudflare Pages 무료로 세상에 공개하는 최고의 조합](https://aikorea24.kr/blog/github-cloudflare-pages-muryoro/)
            - [빌드/푸쉬/배포의 차이점 쉽게 이해하기](https://aikorea24.kr/blog/%EB%B9%8C%EB%93%9C-%ED%91%B8%EC%89%AC-%EB%B0%B0%ED%8F%AC%EC%9D%98-%EC%B0%A8%EC%9D%B4%EC%A0%90/)

            ### 오늘의 미션

            AI의 도움을 받아 Hugo 블로그를 만들고, 첫 글을 작성해서 Cloudflare Pages에 배포해보세요. 로컬 빌드 → 푸시 → 배포의 사이클을 직접 경험해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            또 다른 선택지: <strong>Hugo</strong>. Go 언어로 만들어진 정적 사이트 생성기로, 블로그에 특화되어 있습니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            로컬 빌드 → 푸시 → 배포. 이 사이클이 익숙해지면 어떤 정적 사이트든 0원에 운영할 수 있습니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: Hugo 블로그를 만들고 첫 글을 배포해보세요.
            </p>
        """),
    },
    {
        "day": 14,
        "title": "여기서 80개까지: 비전과 다음 스텝",
        "content": textwrap.dedent("""\
            ## 여기서 80개까지: 비전과 다음 스텝

            축하합니다! 0원 인프라 7일을 완주했습니다. 🎉

            ### 7일간의 정리

            | 일차 | 주제 | 핵심 내용 |
            |------|------|----------|
            | 8일차 | 첫 도메인, 첫 사이트 | Cloudflare + Astro 랜딩 페이지 |
            | 9일차 | info@내도메인 | Email Routing, 무료 이메일 |
            | 10일차 | 콘텐츠 사이트 하나 더 | 두 번째 사이트, AI 콘텐츠 |
            | 11일차 | 이메일 구독자 모으기 | Brevo, 구독 폼, 뉴스레터 |
            | 12일차 | Workers 첫 코드 | 서버리스 자동화 |
            | 13일차 | Hugo 블로그 | 정적 배포 사이클 |
            | 14일차 | 비전과 다음 스텝 | 🎉 완강, 히어로 티저 |

            ### 나는 이걸 80개까지 늘렸다

            21일 전, 나는 지금의 당신과 같은 자리에서 시작했습니다. 지금은 80개가 넘는 사이트를 Cloudflare 하나로 운영하고 있습니다. 각 사이트는:
            - 제각각 다른 주제 (운세, 블로그, 도구, AI 뉴스)
            - Cloudflare Pages + GitHub로 무료 배포
            - 일부는 Workers로 자동화되어 자는 동안 작동

            사이트 수가 중요한 게 아닙니다. 중요한 건 **한 사람이 80개를 운영할 수 있는 시스템**입니다. 당신도 지금 그 시스템의 기초를 다졌습니다.

            ### 🔜 히어로 강좌: "무료 에이전트, 7일"

            이 강좌 다음 단계가 준비되어 있습니다.

            **"무료 에이전트, 7일"** 에서는:
            - 무료 LLM API로 AI 코딩
            - Cloudflare Workers + AI = 첫 에이전트
            - 뉴스 수집 → 요약 → 메일 발송 자동화
            - 블로그 글 → SNS 자동 포스팅
            - 자는 동안 돌아가는 시스템

            *이 강좌는 곧 오픈됩니다. 커뮤니티 공지를 기다려주세요.*

            ### 📖 함께 읽기

            - [돈 쓰지 말고 바이브 코딩 이렇게 시작하세요](https://aikorea24.kr/blog/%EB%8F%88%EC%93%B0%EC%A7%80-%EB%A7%90%EA%B3%A0-%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9/)
            - [바이브 코딩 시작하기 — ChatGPT와 VS Code만 있으면 당신도 개발자](https://aikorea24.kr/blog/%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9-%EC%8B%9C%EC%9E%91%ED%95%98%EA%B8%B0-chatgpt%EC%99%80/)

            ### 오늘의 미션

            지난 7일간 만든 것들을 정리해보세요. 내 도메인, 내 사이트들, 구독 폼, Workers. 커뮤니티에 지금까지의 결과를 공유하고, 히어로 강좌 오픈 알림을 기다려주세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            축하합니다! 0원 인프라 7일 완주! 🎉 <strong>당신은 이제 AI가 만든 사이트를 0원에 운영</strong>할 수 있습니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            지금의 당신과 같은 자리에서 시작해서 80개 사이트를 운영하게 된 이야기와, 다음 단계인 히어로 강좌 티저를 공개합니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 지난 7일간의 결과를 정리하고 커뮤니티에 공유해보세요.
            </p>
        """),
    },
]


# ─── SQL 생성 ────────────────────────────────────────────────────────

def build_sql(update_mode: bool = False) -> str:
    stmts = []
    kst = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

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
        stmts.append("-- 2. courses UPDATE\n")
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

            stmts.append(f"""-- {day}. post ensure
INSERT OR IGNORE INTO posts (user_id, title, content, category, visibility, author_email, author_name, created_at)
VALUES (1, '{title}', '{content}', 'free', 'members', 'system@aikorea24.kr', 'AI코리아24', '{kst}');
""")
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
        for lesson in LESSONS:
            day = lesson["day"]
            title = lesson["title"].replace("'", "''")
            content = lesson["content"].replace("'", "''")
            teaser = lesson["teaser"].replace("'", "''")

            stmts.append(f"""-- {day}. post
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
    tmp = os.path.join(PROJECT_DIR, "scripts", "_tmp_infra_update.sql")
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
        print("❌ npx/wrangler not found.")
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    parser = argparse.ArgumentParser(description="0원 인프라 강좌 시드 데이터 생성")
    parser.add_argument("--dry", action="store_true", help="SQL만 출력")
    parser.add_argument("--file", type=str, help="SQL을 파일로 저장")
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

    print(f"=== 0원 인프라 강좌 시드 데이터 생성 ===")
    print(f"강좌: {COURSE_SLUG}")
    print(f"레슨 수: {len(LESSONS)}개\n")

    action_label = "업데이트" if args.update else "삽입"
    response = input(f"D1(remote)에 시드 데이터를 {action_label}할까요? (y/N): ")
    if response.lower() != "y":
        print("취소됨.")
        return

    print(f"\n[1/1] 시드 데이터 {action_label}...")
    if not run_wrangler(sql):
        print(f"시드 데이터 {action_label} 실패.")
        return

    print(f"\n✅ 완료! {len(LESSONS)}개 레슨이 posts(D1)에 {action_label}되었습니다.")


if __name__ == "__main__":
    main()
