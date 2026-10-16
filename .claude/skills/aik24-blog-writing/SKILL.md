---
name: aik24-blog-writing
description: Use when writing or editing long-form posts for aikorea24 EmDash blog (emdash.aikorea24.kr) — guides, how-to, model reviews, documentation-style articles, or when rewriting a post that scored low on 사실성·체류시간. Triggers on "블로그 글 써줘", 새 글 발행, 기존 글 재작성·보완.
---

# aik24-blog-writing — aikorea24 블로그 글쓰기

대상: EmDash 블로그 `https://emdash.aikorea24.kr/posts/<slug>`.
기준 사례: `opencode-cli-guide` 전면 재작성 (2026-10-16, 대표님 평가 100/100), `groq-free-api-key-guide` 재작성 (표 7행·외부 링크 5개).
아래 규칙은 그 재작성에서 지적받은 4가지를 뼈대로 만든 것이다. 어기면 재작업이다.

**정답지 사본이 repo 안에 있다** — 쓰기 전에 한 편을 통째로 읽고 밀도를 맞춘다:
`scripts/logs/opencode_cli_guide_draft.md` (5,362자) · `scripts/logs/groq_free_api_key_guide_draft.md` (3,447자).
규칙 목록보다 완성된 글 한 편이 더 잘 먹는다. 새 글은 이 밀도에 맞춘다.

## 0. 쓰기 전 — 사실 수집 (건너뛰면 글이 반드시 얇아진다)

순서: **수집 → 작성 → 게이트(3절) → 발행**. 수집을 건너뛰고 바로 쓰면 기억에 의존하게 되고,
빈 곳을 "한도는 바뀔 수 있으니 확인하세요" 같은 회피 문장으로 채운다.
(2026-10-16 실측: 수집 없이 쓴 판 = 수치 0개·표 0개·3,054자 / 수집 후 재작성 = 표 7행·외부 링크 5개·3,447자.)

```bash
curl -s "https://<공식 문서 페이지>" -o /tmp/src.html -w 'status %{http_code}\n'
python3 -c "
import re,html
s=open('/tmp/src.html',encoding='utf-8',errors='ignore').read()
s=re.sub(r'<script.*?</script>|<style.*?</style>',' ',s,flags=re.S)
t=html.unescape(re.sub(r'<[^>]+>',' ',s)); print(re.sub(r'\s+',' ',t)[:2000])"
```

수집 체크리스트 — 이 4개가 안 채워지면 아직 쓸 때가 아니다:

1. **숫자** — 한도·요금·속도·개수. 문서 표를 그대로 전사한다(요약·반올림 금지).
2. **날짜** — 공개일·버전, 그리고 "YYYY년 M월 D일 기준" 표기.
3. **URL 3개 이상** — 공식 홈 / 키 발급·설치 / 공식 문서.
4. **한계 한 줄** — 무료로 안 되는 것, 제한, 주의점.

공식 페이지가 JS 렌더·리다이렉트(308)·404 라 본문이 비어 나오면 **그 사실은 쓰지 않는다.** 지어내면 회귀다.

## 1. 구조 — 도입 설명문 → 소제목/본문 → 마무리 소제목

- **본문에 `#`(H1)을 쓰지 않는다.** 제목은 `upsert_post` 의 title 하나뿐이다.
  본문에 `#` 을 넣으면 라이브에 `<h1>` 이 두 번 나오고 즉시 지적받는다.
- **도입 문단(첫 3~4문장)** — ① 무엇인지 ② 언제 공개됐고 규모가 어떤지(사실) ③ 이 글이 답하는 것(독자가 얻는 것).
  도입부터 "설치부터 시작합니다" 같은 안내문으로 시작하지 않는다.
- **소제목** = `## N. 동작 — 결과/약속` 형태. 번호를 붙이고, 소제목만 읽어도 목차가 된다.
  예: `## 1. 설치 — 3분이면 끝납니다` / `## 2. 무료 API 키 — 어디서 받고 어디에 넣나`.
- **마무리 소제목**은 반드시 하나 둔다. 제목은 **문자 그대로 `## 마무리 — …`** 로 시작한다(4·5절 검증 grep 이 이 단어를 찾는다). 가능하면 **실행 체크리스트**(오늘 30분 안에 할 3단계)로 끝낸다. **없으면 발행하지 않는다.** (실제 누락 사례: `groq-free-api-key-guide` — H2 7개가 `주의사항` 으로 끝나고 마무리가 없었다.)
- 길이 목표: 분량은 사실 밀도로 채운다. 표·링크·실측 수치 없이 3분 분량이면 실패다.

## 2. 내용 — 사실이 체류시간을 만든다

- **사실을 먼저 채운다.** 공개일, 저장소, 스타 수, 라이선스, 버전, 실측 수치.
  ("자랑성 팁"은 체류시간을 못 만든다 — 2026-10-16 지적: "점수 30점도 안 된다".)
- **우리끼리 용어·내부 운영 이야기 금지.** 프로젝트 내부 도구명, 장애 복구, 배포 스크립트, 사내 키 이름 등은
  독자에게 쓸모가 없다. (예: `.dev.vars Firecrawl 키 401` 이야기 → 전부 삭제.)
- **"어떻게 하는가"는 실행 가능한 표로.** 무엇을 위한 정보든 ① 어디서 받는지(URL) ② 어디에 넣는지(환경변수명)
  ③ 예시 코드 3종을 갖춘다. "API 키를 등록해야 합니다"에서 멈추면 지적받는다.
- **무료/유료를 사실대로 구분한다.** 무료라고 뭉뚱그리지 않는다.
  (예: OpenCode Zen 내장 `-free` 는 키 없이 바로 / Zen 유료 모델은 `$20` 잔액 필요 — 실측 후 그대로 적었다.)
- **실측 수치는 내 데이터에서.** "623세션 중 564건(90.5%) 무료" 처럼 표본·분모·비율을 같이 쓴다.
- **링크를 넣는다.** 출처·설치·키 발급 페이지를 인라인 링크로. 링크 0개인 글은 미완성이다.
- **확인 못 한 것은 쓰지 않는다.** 공식 페이지에서 확인되지 않은 설치 명령(예: npm/brew), `--help` 에 안 나오는
  서브커맨드는 빼거나 "확인 필요"로 남긴다. 추측해서 쓰면 회귀다.
- **시점 의존 수치는 "YYYY년 M월 D일 기준"을 명시한다.** 스타 수·버전·세션 수는 계속 변한다.

## 3. 발행 경로 (repo 에 글 소스가 없다)

**발행은 게이트를 통과한 뒤에만 한다** — 규칙 준수를 작성자에게 맡기지 않고 코드로 막는다(exit 3 = 발행 금지).
게이트 검사 항목: 본문 H1 없음 / `## 마무리` 있음 / 외부 링크 ≥3 / 표 ≥1 / 코드펜스 짝 / 3,000자 이상 / 내부 용어 0.

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/emdash_precheck.py /tmp/my-post.md     # exit 0 확인 (실패 시 사유 출력)
```

통과 후 이어서 발행한다(게이트 + 발행을 한 명령으로 묶은 형태 — 권장):

```bash
cd /Users/twinssn/Projects/aikorea24
set -a && . ./.env && . "$HOME/.env.common" && set +a   # PAT 는 ~/.env.common 에만 있다
python3 scripts/emdash_precheck.py /tmp/my-post.md --publish <slug> "<제목>" "<excerpt 한 줄>"
```

또는 직접 호출:

```bash
cd /Users/twinssn/Projects/aikorea24
set -a && . ./.env && . "$HOME/.env.common" && set +a   # PAT 는 ~/.env.common 에만 있다
.venv/bin/python3 -c "
import sys; sys.path.insert(0,'scripts')
from emdash_publish import upsert_post
url = upsert_post('my-slug', '제목', open('/tmp/my-post.md').read(), excerpt='한 줄 요약')
print(url)"
```

- PAT 키 이름: `EMDASH_AIKOREA24_API_TOKEN` / `EMDASH_PAT` — **`~/.env.common` 에만 존재**. 프로젝트 `.env` 에는 없다.
- `upsert_post(slug, title, body_md, excerpt=None, featured_image=None)` — 같은 slug면 갱신(PUT + publish),
  없으면 생성. **생성 시 slug 는 title 을 slugify 한 값**이므로 고정 URL 을 원하면 slug/title 을 미리 맞춰라.
- **HTML 금지** — `md_to_pt()` 가 HTML 을 처리하지 않아 태그가 텍스트로 노출된다. 마크다운 표만 쓴다.
- `get_post(slug)` 가 `None` 을 반환해도 발행은 정상일 수 있다(조회 quirk). 발행 결과 URL 로 판단한다.

## 4. 발행 후 검증 (건너뛰지 말 것)

```bash
curl -s -o /tmp/p.html -w '%{http_code}\n' https://emdash.aikorea24.kr/posts/<slug>
grep -c '<h1' /tmp/p.html                    # 1 이어야 한다 (중복 H1 = 회귀)
grep -c 'href="http' /tmp/p.html              # 외부 링크 수 (0이면 미완성)
grep -ci 'firecrawl\|내부도구명' /tmp/p.html    # 0 이어야 한다
grep -c '<h2[^>]*>[^<]*마무리' /tmp/p.html      # 1 이상 — 없으면 발행 금지 (본문이 마무리 없이 끝난다)
```

- **중복 글 확인**: EmDash DB 를 직접 조회한다(목록 API 는 `st=0` 반환).
  `cfnew.sql("SELECT id, slug, status FROM ec_posts WHERE slug='<slug>'", database_id=cfnew.EMDASH_DB)` → **1행**이어야 한다.
- `docs/state.md` 맨 위에 엔트리 1건 추가 + 본문 사본을 `scripts/logs/<slug>_draft.md` 로 남기고 커밋한다.
  (EmDash 글은 repo 밖에 있어 diff 추적이 안 되므로 사본이 유일한 이력이다.)

## 5. 재작성 시 진단 체크리스트

기존 글을 받으면 먼저 이 5개를 실측한다 (전부 실제 지적 사례):

1. `<h1>` 이 2개인가 → 본문 `#` 제거.
2. 외부 링크가 0개인가 → 출처·키 발급·설치 페이지 링크 추가.
3. 내부 프로젝트 용어·운영 이야기가 있는가 → 삭제.
4. 사실(공개일·규모·실측 수치)이 있는가 → 없으면 수집해서 도입과 각 소제목에 배치.
5. 마무리 소제목(`## 마무리`)이 있는가 → 없으면 실행 체크리스트(오늘 30분 안에 할 3단계)로 추가.
   실제 누락 사례: `groq-free-api-key-guide`(H2 7개가 `주의사항` 으로 끝남), 표 0개·외부 링크 1개·3,054자로 얇았다.
