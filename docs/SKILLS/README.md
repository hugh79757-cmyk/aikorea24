# AI코리아24 스킬 문서 인덱스

> 프로젝트 간 재사용 가능한 자동화 파이프라인 스킬 모음

---

## 스킬 목록

| # | 스킬 | 설명 | 주요 스크립트 |
|---|------|------|-------------|
| 01 | [데일리 뉴스 파이프라인](./01-daily-news-pipeline.md) | 뉴스 수집 → 선정 → 브리핑 → 심층글 → 썸네일 → 이메일 → 배포 전체 워크플로우 | `run_pipeline.py` 외 |
| 02 | [Brevo 이메일 구독·발송](./02-brevo-email-system.md) | 뉴스레터 구독/해지 + 자동 이메일 발송 시스템 | `auto_email_sender.py`, `subscribe.ts` 외 |
| 03 | [AI 도구 수집](./03-ai-tools-collector.md) | Product Hunt, GitHub, Futurepedia 등에서 AI 도구 자동 수집 | `tools_collector.py` |
| 04 | [심층글 생성](./04-deep-article-generator.md) | 뉴스 크롤링 → AI 심층분석 → 블로그 마크다운 생성 | `auto_deep_article.py` |
| 05 | [썸네일 생성](./05-thumbnail-generator.md) | Pexels + DeepSeek로 뉴스 썸네일 자동 생성 | `auto_thumbnail.py` |
| 06 | [블로그 검증](./06-blog-post-validator.md) | 배포 전 블로그 포스트 frontmatter/내용 품질 검증 | `validate_blog_posts.py` |
| 07 | [키워드 아웃라인 생성](./07-keyword-outline-generator.md) | 키워드 테이블 → D1 검색 → 아웃라인 자동 생성 | `outline_generator.py` |
| 08 | [Cloudflare 배포](./08-cloudflare-deploy.md) | Astro 빌드 → Cloudflare Pages 배포 (auth profile 처리 포함) | `deploy.sh` |
| 09 | [Threads/X 소셜 파이프라인](./09-threads-social-pipeline.md) | 콘텐츠 생성 → Threads/X API 발행 → 검증/스케줄링 | `threads/v3/*.py` |

---

## 공통 인프라

모든 스킬에서 공유하는 설정과 패턴:

### 환경변수 로드

프로젝트 `.env` + `~/.env.common` 두 곳에서 설정 로드.

```bash
# 프로젝트 .env (/Users/twinssn/Projects/aikorea24/.env)
BREVO_API_KEY=xxx
MIMO_API_KEY=xxx  # 또는 ~/.env.common 에

# 공통 ~/.env.common
MIMO_API_KEY=xxx
PEXELS_API_KEY=xxx
DEEPSEEK_API_TOKEN=sk-xxx
```

### D1 데이터베이스

```python
# wrangler d1 execute 사용
import subprocess
cmd = ["/opt/homebrew/bin/wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql]
# 또는 D1 REST API 직접 호출
```

### 로그 패턴

```python
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))

def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
```

### 중국어 안전망

모든 한국어 생성 스크립트에 포함:

```python
import re

def remove_chinese(text):
    return re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', '', text)
```

---

## 문서 규칙

각 스킬 문서는 다음 섹션을 포함:
1. 개요 (스크립트, 역할, 흐름)
2. 사전 준비 (환경변수, 의존성, API 키)
3. 실행 방법 (전체/개별/프로그래매틱)
4. 동작 흐름 (상세 단계)
5. 파일 구조
6. 체크리스트
7. 트러블슈팅

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
