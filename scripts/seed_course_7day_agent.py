#!/usr/bin/env python3
"""무료 에이전트 강좌 시드 데이터 생성기 (히어로 코스 — 부트스트랩/구조 보강 전용).

사용법:
  python3 scripts/seed_course_7day_agent.py           # wrangler d1 execute로 삽입
  python3 scripts/seed_course_7day_agent.py --dry     # SQL만 출력
  python3 scripts/seed_course_7day_agent.py --update  # 신규 레슨/매핑만 보강 (기존 본문 갱신 안 함)
  python3 scripts/seed_course_7day_agent.py --dry --update  # SQL 미리보기 (본문 갱신 없음 확인)
"""
import argparse
import os
import subprocess
import textwrap
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COURSE_SLUG = "7day-agent"
COURSE_TITLE = "무료 에이전트, 7일 — AI를 지휘하는 사람으로"
COURSE_DESC = (
    "코드를 쓰는 사람에서, AI를 지휘하는 사람으로. "
    "무료 LLM API로 첫 AI 에이전트를 만들고, "
    "뉴스 수집 → 요약 → 발송, 블로그 → SNS 자동 포스팅까지. "
    "당신이 자는 동안 시스템이 돌아가게 만드는 법을 7일 만에 배웁니다."
)

LESSONS = [
    {
        "day": 15,
        "title": "LLM 직접 부르기 — API 키 하나면 시작",
        "content": textwrap.dedent("""\
            ## LLM 직접 부르기 — API 키 하나면 시작

            지금까지 당신은 ChatGPT 웹 인터페이스로 AI를 사용했습니다. 이제는 **코드로 AI를 직접 호출**합니다. API 키 하나만 있으면 AI를 내 프로그램의 부품으로 쓸 수 있습니다.

            ### 왜 API로 직접 부르나요?

            ChatGPT 웹은 사람이 손으로 쓰기 위한 도구입니다. API는 **프로그램이 AI를 호출**하기 위한 도구입니다. API를 쓰면:
            - AI 호출을 자동화할 수 있음
            - 내 데이터를 AI에 넣고 결과를 받을 수 있음
            - 다른 프로그램과 연결할 수 있음

            ### 무료 LLM API 고르기

            유료 LLM (GPT-4, Claude 3.5)은 비싸지만, 요즘은 **무료로 쓸 수 있는 LLM**이 많습니다:

            | 서비스 | 무료 모델 | 특징 |
            |--------|----------|------|
            | OpenRouter | 수십 개 모델 | 무료 모델 트래픽 제한 있음, 신용카드 없이 시작 |
            | Groq | Llama 3 70B | 속도가 매우 빠름, 무료 티어 generous |
            | Cloudflare Workers AI | Llama, DeepSeek | Workers에서 바로 호출, 별도 키 불필요 |

            이 강좌에서는 **OpenRouter**를 추천합니다. 계정만 만들면 무료 모델을 바로 쓸 수 있고, 나중에 유료 모델로 업그레이드하기도 쉽습니다.

            ### 첫 API 호출 — curl로 시작

            ```bash
            curl https://openrouter.ai/api/v1/chat/completions \\
              -H "Authorization: Bearer $OPENROUTER_API_KEY" \\
              -H "Content-Type: application/json" \\
              -d '{
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": "AI 에이전트란 무엇인가요? 3문장으로 설명해주세요."}]
              }'
            ```

            이 한 줄이 당신을 오케스트레이터의 세계로 초대합니다. 터미널에서 직접 실행해보세요.

            ### API 호출의 구조

            모든 LLM API는 같은 구조를 가집니다:
            1. **모델 선택** — 어떤 AI를 쓸지 지정
            2. **메시지** — 역할(시스템/사용자)과 내용
            3. **응답** — AI가 생성한 텍스트

            ### 📖 함께 읽기

            - [코딩 몰라도 괜찮아 — 1인기업을 위한 Cloudflare 무료 인프라 완벽 가이드](https://aikorea24.kr/blog/%EC%BD%94%EB%94%A9-%EB%AA%B0%EB%9D%BC%EB%8F%84-%EA%B4%9C%EC%B0%AE%EC%95%84-1%EC%9D%B8%EA%B8%B0%EC%97%85%EC%9D%84/)
            - [돈 쓰지 말고 바이브 코딩 이렇게 시작하세요](https://aikorea24.kr/blog/%EB%8F%88%EC%93%B0%EC%A7%80-%EB%A7%90%EA%B3%A0-%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9/)

            ### 오늘의 미션

            OpenRouter에 가입하고, curl로 첫 LLM API 호출을 해보세요. 응답이 돌아오면 성공입니다. API 응답을 캡처해서 커뮤니티에 공유해주세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            지금까지 ChatGPT 웹으로 AI를 썼습니다. 이제 <strong>코드로 AI를 직접 호출</strong>합니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            API 키 하나만 있으면 AI를 내 프로그램의 부품으로 쓸 수 있습니다. curl 명령어 한 줄로 첫 호출을 경험해보세요.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: OpenRouter 가입 + curl로 첫 API 호출해보기.
            </p>
        """),
    },
    {
        "day": 16,
        "title": "Workers + AI = 첫 에이전트",
        "content": textwrap.dedent("""\
            ## Workers + AI = 첫 에이전트

            API 키로 LLM을 직접 호출할 수 있게 되었습니다. 이제 그 호출을 **Workers 안에서 실행**합니다. Workers가 요청을 받아서 AI를 호출하고, 결과를 반환하는 — 이것이 첫 에이전트입니다.

            ### 에이전트란 무엇인가요?

            **에이전트 = AI 호출 + 로직 + 자동 실행**

            단순한 API 호출이 아니라:
            - 요청을 받아서 (`input`)
            - 상황에 맞는 프롬프트를 구성하고 (`think`)
            - AI를 호출해서 (`act`)
            - 결과를 가공해서 반환 (`output`)

            이 전체 흐름이 하나의 함수 안에 담겨 있으면, 그것이 에이전트입니다.

            ### Workers로 첫 에이전트 만들기

            ```javascript
            export default {
              async fetch(request, env, ctx) {
                // 1. 요청에서 질문 추출
                const { question } = await request.json();

                // 2. AI 호출
                const response = await fetch(
                  "https://openrouter.ai/api/v1/chat/completions",
                  {
                    method: "POST",
                    headers: {
                      "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
                      "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                      model: "meta-llama/llama-3.1-8b-instruct:free",
                      messages: [
                        { role: "system", content: "당신은 친절한 AI 도우미입니다. 한국어로 간결하게 답변하세요." },
                        { role: "user", content: question },
                      ],
                    }),
                  }
                );

                const data = await response.json();
                const answer = data.choices[0].message.content;

                // 3. 응답 반환
                return new Response(JSON.stringify({ answer }), {
                  headers: { "Content-Type": "application/json" },
                });
              },
            }
            ```

            이 코드를 `wrangler deploy`하면, 당신만의 AI API가 탄생합니다.

            ### 배포하고 테스트하기

            ```bash
            # wrangler secret put OPENROUTER_API_KEY 로 키 등록
            wrangler secret put OPENROUTER_API_KEY

            # 배포
            wrangler deploy

            # 테스트
            curl https://my-agent.workers.dev/ \\
              -H "Content-Type: application/json" \\
              -d '{"question": "오늘의 AI 뉴스 요약해줘"}'
            ```

            ### 개념: 환경 변수와 보안

            API 키는 코드에 직접 쓰지 않습니다. `wrangler secret put`으로 등록하면 암호화된 환경 변수로 주입됩니다. 코드에는 `env.OPENROUTER_API_KEY`로 접근합니다.

            ### 📖 함께 읽기

            - [바이브 코딩 시작하기 — ChatGPT와 VS Code만 있으면 당신도 개발자](https://aikorea24.kr/blog/%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9-%EC%8B%9C%EC%9E%91%ED%95%98%EA%B8%B0-chatgpt%EC%99%80/)
            - [Cloudflare 역사를 알면 서비스가 보인다](https://aikorea24.kr/blog/cloudflare-%EC%97%AD%EC%82%AC%EB%A5%BC-%EC%95%8C%EB%A9%B4-%EC%84%9C%EB%B9%84%EC%8A%A4%EA%B0%80/)

            ### 오늘의 미션

            위 Workers 코드를 AI에게 작성하게 시키고, 배포해서 curl로 테스트해보세요. 당신만의 AI API가 0원에 탄생합니다.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            API 키로 LLM을 직접 호출할 수 있게 되었습니다. 이제 <strong>Workers 안에서 AI를 실행</strong>합니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            Workers가 요청을 받아서 AI를 호출하고 결과를 반환합니다. 요청 + 프롬프트 + AI 호출 + 응답 — 이것이 첫 에이전트입니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: Workers + AI 에이전트를 배포하고 curl로 테스트해보세요.
            </p>
        """),
    },
    {
        "day": 17,
        "title": "일정 자동화 — launchd / cron / Scheduled Workers",
        "content": textwrap.dedent("""\
            ## 일정 자동화 — launchd / cron / Scheduled Workers

            에이전트가 생겼으니, 이제 **매일 특정 시간에 자동 실행**되게 만듭니다. 진정한 자동화는 사람이 버튼을 누르지 않고 시스템이 스스로 움직이는 데서 시작합니다.

            ### 세 가지 선택지

            | 방식 | 환경 | 특징 |
            |------|------|------|
            | Mac launchd | 내 Mac | Mac이 켜져 있을 때만 실행, 설정 간단 |
            | Linux cron | 서버/VPS | 전통적이고 안정적, 항상 켜져 있어야 |
            | Workers Cron Triggers | Cloudflare | 0원, 항상 켜짐, 가장 추천 |

            이 강좌에서는 **Workers Cron Triggers**를 메인으로 사용합니다. Cloudflare Workers의 Scheduled Worker는 무료 요금제에서도 하루 1회 이상 실행 가능합니다.

            ### Scheduled Worker 만들기

            ```javascript
            export default {
              async scheduled(event, env, ctx) {
                // 매일 아침 8시(KST=23UTC)에 실행됨
                console.log("⏰ 에이전트 기동!");

                const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
                  method: "POST",
                  headers: {
                    "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    model: "meta-llama/llama-3.1-8b-instruct:free",
                    messages: [
                      { role: "user", content: "오늘의 할 일을 간단히 브리핑해줘. 한국어로 3줄." },
                    ],
                  }),
                });

                const data = await response.json();
                console.log("📨 에이전트 응답:", data.choices[0].message.content);
              },
            }
            ```

            wrangler.toml (또는 wrangler.jsonc)에 cron 트리거를 추가합니다:

            ```jsonc
            {
              "triggers": {
                "crons": ["0 23 * * *"]  // 매일 UTC 23:00 = KST 08:00
              }
            }
            ```

            ### Mac 사용자를 위한 launchd

            Mac을 서버처럼 쓰고 싶다면 launchd로도 가능합니다:

            ```xml
            <!-- ~/Library/LaunchAgents/kr.aikorea24.daily-brief.plist -->
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "...">
            <plist version="1.0">
            <dict>
              <key>Label</key>
              <string>kr.aikorea24.daily-brief</string>
              <key>ProgramArguments</key>
              <array>
                <string>/usr/bin/python3</string>
                <string>/Users/you/scripts/daily_brief.py</string>
              </array>
              <key>StartCalendarInterval</key>
              <dict>
                <key>Hour</key>
                <integer>8</integer>
                <key>Minute</key>
                <integer>0</integer>
              </dict>
            </dict>
            </plist>
            ```

            ### 📖 함께 읽기

            - [Cloudflare 무료의 한계 — 빌드 제한과 하루 1회 배포 전략](https://aikorea24.kr/blog/cloudflare-muryoui-hangye-bildeu/)

            ### 오늘의 미션

            Scheduled Worker를 만들고 wrangler로 배포해서, 지정한 시간에 자동 실행되는지 확인해보세요. Cloudflare 대시보드에서 로그를 확인할 수 있습니다.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            에이전트가 생겼으니 <strong>매일 특정 시간에 자동 실행</strong>되게 만듭니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            Cloudflare Workers Cron Triggers로 하면 0원이고, Mac은 launchd, Linux는 cron. 당신의 환경에 맞게 고르세요.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: Scheduled Worker를 배포하고 자동 실행을 확인해보세요.
            </p>
        """),
    },
    {
        "day": 18,
        "title": "뉴스 수집 → 요약 → 메일: 첫 파이프라인",
        "content": textwrap.dedent("""\
            ## 뉴스 수집 → 요약 → 메일: 첫 파이프라인

            지금까지 배운 것을 하나로 연결합니다. **뉴스 RSS를 읽고 → AI로 요약하고 → 이메일로 발송**하는 완전한 파이프라인을 만듭니다.

            ### 파이프라인 구조

            ```
            RSS/API → Workers → LLM 요약 → Email → 당신
            (수집)     (실행)    (가공)      (전달)   (수신)
            ```

            각 단계가 독립적이어서, 중간에 문제가 생겨도 다음 실행 때 복구됩니다.

            ### 전체 코드 (AI에게 시키세요)

            아래 설명을 AI에게 복붙하면 Workers 코드를 만들어줍니다:

            > "Cloudflare Workers Scheduled Worker를 만들어줘.
            > 1. 매일 아침 Hacker News API에서 상위 뉴스 5개를 가져오고
            > 2. OpenRouter 무료 LLM으로 각 뉴스를 한국어로 3줄 요약하고
            > 3. 요약 결과를 Brevo API로 내 이메일로 발송해줘
            > 4. OPENROUTER_API_KEY와 BREVO_API_KEY는 env에서 읽어와
            > 5. 응답은 JSON으로 로그에만 출력하고, HTTP 응답은 간단한 OK 메시지"

            AI가 작성해준 코드를 `wrangler deploy` 하루면 완성입니다. 단 3일 전만 해도 몰랐던 것들이 이제 하나의 시스템이 되어 움직입니다.

            ### 단계별로 이해하기

            **수집**: RSS/API를 fetch로 호출합니다. Hacker News, Reddit, 네이버 뉴스, 자체 블로그 — 무엇이든 가능합니다.

            **요약**: 가져온 데이터를 LLM에 보내서 요약합니다. 프롬프트에 "한국어로 3줄, 핵심만, 초등학생도 이해할 수 있게" 같은 조건을 넣으면 출력 품질이 높아집니다.

            **발송**: Brevo API나 Cloudflare Email Routing을 사용합니다. Workers에서 메일을 직접 보낼 수도 있습니다.

            ### 에러 처리의 중요성

            실제로 돌아가는 시스템에서는 에러 처리가 필수입니다:

            ```javascript
            try {
              const news = await fetchNews();
              const summary = await summarize(news);
              await sendEmail(summary);
            } catch (error) {
              // 실패해도 다음 실행 때 다시 시도
              console.error("파이프라인 실패:", error.message);
              // 필요하면 슬랙/텔레그램으로 알림
            }
            ```

            핵심 원칙: **실패해도 전체가 죽지 않게, 다음 실행이 복구하게**.

            ### 📖 함께 읽기

            - [혼자 운영하는 사장님 필수 AI 자동 상담 시스템 구축법](https://aikorea24.kr/blog/%ED%98%BC%EC%9E%90-%EC%9A%B4%EC%98%81%ED%95%98%EB%8A%94-%EC%82%AC%EC%9E%A5%EB%8B%98-%ED%95%84%EC%88%98/)

            ### 오늘의 미션

            뉴스 수집 → 요약 → 메일 발송 파이프라인을 완성해보세요. 아침에 일어나면 메일함에 AI가 요약한 뉴스가 와 있어야 합니다.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            배운 것을 하나로 연결합니다. <strong>뉴스 RSS → LLM 요약 → 이메일 발송</strong> 완전한 파이프라인.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            AI에게 코드를 시키면 됩니다. 단 3일 전만 해도 몰랐던 것들이 이제 하나의 시스템이 되어 움직입니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 수집 → 요약 → 발송 파이프라인을 완성하세요.
            </p>
        """),
    },
    {
        "day": 19,
        "title": "블로그 → SNS 자동 포스팅",
        "content": textwrap.dedent("""\
            ## 블로그 → SNS 자동 포스팅

            새 블로그 글을 쓰면 SNS에 자동으로 공유됩니다. 매일 아침 AI 뉴스 브리핑이 자동 발송됩니다. 당신은 **글만 쓰면 나머지는 시스템이 처리**합니다.

            ### 자동 포스팅 파이프라인

            ```
            새 블로그 글 (GitHub Push)
              → Cloudflare Pages 재배포
                → Workers Webhook 감지
                  → LLM이 SNS용 카피 작성
                    → Twitter/X API 발행
                    → LinkedIn API 발행
            ```

            GitHub에 푸시하면 모든 것이 자동으로 연결됩니다.

            ### Workers로 RSS 감지 → SNS 발행

            ```javascript
            export default {
              async scheduled(event, env, ctx) {
                // 1. 블로그 RSS에서 최신 글 확인
                const rss = await fetch("https://내블로그.kr/rss.xml").then(r => r.text());

                // 2. LLM으로 SNS 카피 생성
                const copy = await callLLM(env, `
                  다음 블로그 글의 제목과 요약을 보고,
                  Twitter(280자)와 LinkedIn(3문단)용 카피를 각각 작성해줘.
                  블로그 글: ${rss.slice(0, 2000)}
                `);

                // 3. Twitter에 발행
                await postToTwitter(env, copy.twitter);

                // 4. LinkedIn에 발행
                await postToLinkedIn(env, copy.linkedin);
              }
            }
            ```

            ### 실제 예: AI코리아24의 자동 포스팅 시스템

            AI코리아24는 이와 같은 시스템으로 운영됩니다:
            - 블로그에 새 글이 발행되면
            - Workers RSS 리더가 감지
            - LLM이 한국어 SNS 카피 생성
            - Twitter/X에 자동 발행

            하루 24시간, 사람이 손대지 않아도 시스템이 돌아갑니다.

            ### 토큰과 권한 관리

            SNS API를 쓰려면 각 플랫폼에서 API 키를 발급받아야 합니다:
            - **Twitter/X**: Developer Portal → OAuth 2.0 → Consumer Key + Token
            - **LinkedIn**: Developer Portal → API → Access Token

            이 키들은 절대 코드에 쓰지 말고, `wrangler secret put`으로 등록하세요.

            ### 📖 함께 읽기

            - [빌드/푸쉬/배포의 차이점 쉽게 이해하기](https://aikorea24.kr/blog/%EB%B9%8C%EB%93%9C-%ED%91%B8%EC%89%AC-%EB%B0%B0%ED%8F%AC%EC%9D%98-%EC%B0%A8%EC%9D%B4%EC%A0%90/)
            - [웹사이트를 어디에 만들지 — 티스토리/네이버/워드프레스/Astro/Hugo](https://aikorea24.kr/blog/wepsaiteureul-eodie-mandeulji-tiseutori/)

            ### 오늘의 미션

            블로그 RSS를 읽어서 새 글이 있으면 SNS에 자동 포스팅하는 Worker를 만들어보세요. 글이 발행되면 자동으로 트윗이 올라가는지 확인해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            새 블로그 글을 쓰면 <strong>SNS에 자동으로 공유</strong>됩니다. 당신은 글만 쓰면 됩니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            GitHub Push → Workers 감지 → LLM 카피 생성 → SNS 발행. 사람이 손대지 않아도 시스템이 돌아갑니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 블로그 → SNS 자동 포스팅 Worker를 완성해보세요.
            </p>
        """),
    },
    {
        "day": 20,
        "title": "자는 동안 돌아가는 시스템",
        "content": textwrap.dedent("""\
            ## 자는 동안 돌아가는 시스템

            드디어 마지막 퍼즐입니다. 지금까지 만든 모든 조각을 하나로 연결합니다. **당신이 자는 동안 시스템이 스스로 돌아가게** 만듭니다.

            ### 완전한 아침 자동화

            ```
            매일 아침 8시 (Scheduled Worker 기동)
              ├── 1. 뉴스 수집 (Hacker News / RSS)
              ├── 2. LLM 요약 (OpenRouter 무료 모델)
              ├── 3. 내 이메일로 브리핑 발송
              ├── 4. 블로그 RSS 확인
              │     └── 새 글 있으면 → SNS 자동 포스팅
              └── 5. 상태 로그 저장 (D1 / KV)
            ```

            당신은 아침에 일어나서 메일함만 확인하면 됩니다. 모든 뉴스가 요약되어 있고, 새 블로그 글은 이미 SNS에 공유되어 있습니다.

            ### 로깅과 모니터링

            시스템이 돌아가면 "잘 돌아가는지"를 확인해야 합니다:

            ```javascript
            // D1에 상태 기록
            await env.DB.prepare(
              "INSERT INTO agent_logs (date, status, summary) VALUES (?, ?, ?)"
            ).bind(today, "success", "뉴스 5건 요약 + 메일 발송 완료").run();

            // 문제가 있으면 나에게 알림
            if (errorCount > 3) {
              await fetch("https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage", {
                method: "POST",
                body: JSON.stringify({
                  chat_id: env.MY_CHAT_ID,
                  text: "🚨 에이전트 비정상: 3회 연속 실패",
                }),
              });
            }
            ```

            ### 정리: 7day-agent 스택

            | 구성 요소 | 역할 | 비용 |
            |-----------|------|------|
            | Cloudflare Workers | 실행 환경 | 0원 (10만 req/일) |
            | Workers Cron Triggers | 스케줄링 | 0원 |
            | OpenRouter (무료 모델) | LLM | 0원 |
            | Cloudflare Email/Brevo | 메일 발송 | 0원 |
            | Cloudflare D1 | 상태 저장 | 0원 (5GB) |
            | Twitter/LinkedIn API | SNS 발행 | 0원 |

            **총 운영비: 0원.** 당신이 이미 가진 것들로 완성됩니다.

            ### 신뢰성 설계 원칙

            1. **멱등성** — 같은 작업을 두 번 실행해도 문제 없게
            2. **재시도** — 실패하면 다음 실행 때 다시 시도
            3. **분리** — 한 파이프라인이 죽어도 다른 파이프라인은 영향 없게
            4. **가시성** — 로그로 항상 상태를 확인할 수 있게

            ### 📖 함께 읽기

            - [Cloudflare 무료의 한계 — 빌드 제한과 하루 1회 배포 전략](https://aikorea24.kr/blog/cloudflare-muryoui-hangye-bildeu/)
            - [GitHub Cloudflare Pages 무료로 세상에 공개하는 최고의 조합](https://aikorea24.kr/blog/github-cloudflare-pages-muryoro/)

            ### 오늘의 미션

            지금까지 만든 모든 Worker를 하나의 Scheduled Worker로 통합해보세요. 내일 아침, 당신이 일어나기 전에 시스템이 먼저 움직이는지 확인해보세요.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            드디어 마지막 퍼즐. <strong>당신이 자는 동안 시스템이 스스로 돌아갑니다</strong>.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            매일 아침 8시: 뉴스 수집 → LLM 요약 → 메일 발송 → SNS 포스팅. 아침에 일어나면 모든 것이 준비되어 있습니다. 운영비는 0원.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 모든 Worker를 통합하고, 내일 아침 자동 실행을 확인해보세요.
            </p>
        """),
    },
    {
        "day": 21,
        "title": "당신도 오케스트레이터 (완강)",
        "content": textwrap.dedent("""\
            ## 당신도 오케스트레이터 (완강)

            축하합니다! 21일의 여정을 완주했습니다. 🎉

            ### 21일간의 정리

            | 단계 | 강좌 | 기간 | 핵심 |
            |------|------|------|------|
            | 제로 | 7day-starter | 1~7일 | AI에게 코딩을 시키는 법 |
            | 인프라 | 7day-infra | 8~14일 | 0원에 사이트를 운영하는 법 |
            | 에이전트 | 7day-agent 🏁 | 15~21일 | AI를 지휘하는 법 |

            ### 당신이 지금 할 수 있는 것

            1. **AI에게 코드를 시켜서** 원하는 기능을 만들 수 있음
            2. **Cloudflare 위에 0원으로 사이트를 운영**할 수 있음
            3. **Workers로 AI 에이전트를 만들고** 자동 실행할 수 있음
            4. **뉴스 수집 → 요약 → 메일 발송** 파이프라인을 만들 수 있음
            5. **블로그 → SNS 자동 포스팅**으로 콘텐츠 유통을 자동화할 수 있음
            6. **자는 동안 시스템이 돌아가게** 할 수 있음

            ### "나도 AI 오케스트레이터가 될 수 있을까?"

            당신은 이미 오케스트레이터입니다. 오케스트레이터는 지휘자입니다. 모든 악기를 직접 연주할 필요는 없습니다. 각 악기(API, Workers, LLM)가 언제 어떻게 연주할지를 지휘하면 됩니다.

            21일 전, API가 뭔지 몰랐어도 괜찮습니다. 지금 당신은 API를 호출하고, Workers를 배포하고, 에이전트를 만들고, 스케줄러로 자동화합니다. 이게 오케스트레이터입니다.

            ### 다음 스텝

            21일 강좌가 끝났지만, 당신의 여정은 계속됩니다:

            - **커뮤니티 참여** — 다른 오케스트레이터들과 경험 공유
            - **사이트 늘리기** — 다양한 주제의 사이트를 운영해보기
            - **에이전트 고도화** — RAG, 멀티모달, 복합 워크플로우 도전
            - **자동화 확장** — 더 많은 파이프라인을 시스템에 추가

            ### 마지막 메시지

            > "21일 전, 당신은 코드 앞에서 두려웠을지 모릅니다. 지금 당신은 코드가 아니라 AI를 지휘합니다. 당신 손에 달려 있습니다. 무한한 가능성이 펼쳐집니다."

            ### 📖 함께 읽기

            - [돈 쓰지 말고 바이브 코딩 이렇게 시작하세요](https://aikorea24.kr/blog/%EB%8F%88%EC%93%B0%EC%A7%80-%EB%A7%90%EA%B3%A0-%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9/)
            - [바이브 코딩 시작하기 — ChatGPT와 VS Code만 있으면 당신도 개발자](https://aikorea24.kr/blog/%EB%B0%94%EC%9D%B4%EB%B8%8C-%EC%BD%94%EB%94%A9-%EC%8B%9C%EC%9E%91%ED%95%98%EA%B8%B0-chatgpt%EC%99%80/)
            - [코딩 몰라도 괜찮아 — 1인기업을 위한 Cloudflare 무료 인프라 완벽 가이드](https://aikorea24.kr/blog/%EC%BD%94%EB%94%A9-%EB%AA%B0%EB%9D%BC%EB%8F%84-%EA%B4%9C%EC%B0%AE%EC%95%84-1%EC%9D%B8%EA%B8%B0%EC%97%85%EC%9D%84/)

            ### 오늘의 미션

            커뮤니티에 21일 완강 인증을 남겨주세요. 지금까지 만든 것들 — 첫 API 호출 결과, Workers 에이전트, 자동화 파이프라인 — 의 스크린샷이나 링크를 공유해주세요. 당신의 완강이 다른 사람의 시작이 됩니다.
        """),
        "teaser": textwrap.dedent("""\
            <p style="font-size:15px;line-height:1.6;color:#1f2937;">
            축하합니다! 21일 완주! 🎉 <strong>당신은 이제 AI 오케스트레이터</strong>입니다.
            </p>
            <p style="font-size:15px;line-height:1.6;color:#1f2937;margin-top:12px;">
            API를 호출하고, Workers를 배포하고, 에이전트를 만들고, 스케줄러로 자동화합니다. 21일 전 코드 앞에서 두려웠던 당신이, 지금은 AI를 지휘합니다.
            </p>
            <p style="font-size:14px;line-height:1.6;color:#374151;margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;">
            🎯 오늘의 미션: 커뮤니티에 21일 완강 인증을 남겨주세요!
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
VALUES (1, '{title}', '{content}', '강의', 'members', 'system@aikorea24.kr', 'AI코리아24', '{kst}');
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
    tmp = os.path.join(PROJECT_DIR, "scripts", "_tmp_agent_update.sql")
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
    parser = argparse.ArgumentParser(description="무료 에이전트 강좌 시드 데이터 생성")
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

    print(f"=== 무료 에이전트 강좌 시드 데이터 생성 ===")
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
