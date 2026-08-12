# 데일리 뉴스 파이프라인 스킬

> aikorea24.kr의 매일 아침 AI 뉴스 브리핑 발행 전체 워크플로우

---

## 1. 개요

매일 아침 실행되어 뉴스 수집 → 선정 → 브리핑 생성 → 심층글 작성 → 썸네일 생성 → 이메일 발송 → 빌드/배포까지 처리하는 엔드투엔드 파이프라인.

**전체 흐름:**
```
뉴스 수집(D1) → 2-Pass 임팩트 평가 → 브리핑 생성 → 심층글(선택) → 썸네일(선택) → 이메일 발송 → 빌드/배포
```

**주요 스크립트:**
| 스크립트 | 역할 |
|---------|------|
| `scripts/run_pipeline.py` | 전체 워크플로우 오케스트레이터 |
| `scripts/auto_news_selector.py` | 뉴스 선정 (2-Pass 평가) |
| `scripts/auto_briefing.py` | 브리핑 생성 (코멘트 + D1 저장) |
| `scripts/auto_deep_article.py` | 심층 분석 블로그 글 생성 |
| `scripts/auto_thumbnail.py` | Pexels 썸네일 생성 |
| `scripts/auto_email_sender.py` | Brevo 이메일 발송 |
| `scripts/deploy.sh` | 빌드 + Cloudflare Pages 배포 |

---

## 2. 사전 준비

### 2.1 환경변수

`~/.env.common` 또는 프로젝트 `.env`에 다음 설정 필요:

```bash
# MIMO API (브리핑 코멘트 + 심층글 생성)
MIMO_API_KEY=xxx

# Brevo (이메일 발송 + 구독 관리)
BREVO_API_KEY=xkeysib-xxx
BREVO_LIST_ID=2
SUBSCRIBER_EMAIL=your@email.com

# Pexels (썸네일 이미지)
PEXELS_API_KEY=xxx

# DeepSeek (썸네일 키워드 추출)
DEEPSEEK_API_TOKEN=sk-xxx

# Cloudflare
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_ZONE_ID=xxx

# OpenAI (AI 도구 수집 시 사용)
OPENAI_API_KEY=sk-xxx
```

### 2.2wrangler 환경

wrangler 4.110.0 이상 + auth profile 설정 필요:

```bash
wrangler whoami  # auth profile 확인
```

### 2.3 Python 의존성

```bash
pip install requests beautifulsoup4 pillow openai
```

---

## 3. 전체 파이프라인 실행

### 3.1 전체 실행 (기본)

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/run_pipeline.py
```

실행 순서:
1. 뉴스 선정 (auto_news_selector)
2. 브리핑 생성 (auto_briefing)
3. 심층글 생성 (auto_deep_article) ← 기본 스킵됨
4. 썸네일 생성 (auto_thumbnail) ← 기본 실행
5. 이메일 발송 (auto_email_sender)
6. 빌드 + 배포 (deploy.sh)

### 3.2 단계별 건너뛰기

```bash
# 심층글만 실행 (나머지는 기본)
python3 scripts/run_pipeline.py --no-skip-deep

# 뉴스 선정 건너뛰고 기존 브리핑으로 진행
python3 scripts/run_pipeline.py --skip-news

# 이메일 발송만 건너뛰기
python3 scripts/run_pipeline.py --skip-email

# 배포만 건너뛰기 (로컬 테스트용)
python3 scripts/run_pipeline.py --skip-deploy

# 여러 단계 조합
python3 scripts/run_pipeline.py --skip-deep --skip-thumbnails --skip-deploy
```

### 3.3 Dry-run (실행 계획만 확인)

```bash
python3 scripts/run_pipeline.py --dry-run
```

출력 예시:
```
[HH:MM:SS] ╔══════════════════════════════════════╗
[HH:MM:SS] ║  aikorea24 데일리 파이프라인 시작    ║
[HH:MM:SS] ╚══════════════════════════════════════╝
[HH:MM:SS] DRY RUN 모드 - 실행하지 않음
[HH:MM:SS]   → 1. 뉴스 선정
[HH:MM:SS]   → 2. 브리핑 생성
[HH:MM:SS]   → 3. 심층글 생성
[HH:MM:SS]   → 4. 썸네일 생성
[HH:MM:SS]   → 5. 이메일 발송
[HH:MM:SS]   → 6. 빌드/배포
```

### 3.4 특정 날짜 지정

```bash
python3 scripts/run_pipeline.py --date 2026-08-07
```

---

## 4. 개별 단계 실행

### 4.1 뉴스 선정만 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_news_selector.py
```

**동작 방식:**
1. D1에서 최근 24시간 크롤링 가능 매체 뉴스 조회 (최대 100건)
2. 9개 주제로 클러스터링 (openai/google/anthropic/meta/microsoft/nvidia/ai-regulation/investment/opensource/misc)
3. Phase A: 모든 후보에 light score 산출
4. Phase B: 상위 20개 크롤링 → full score 산출
5. 2-Pass 선택:
   - Pass 1: full_score ≥ 70점 상위 3개 (클러스터 중복 방지)
   - Pass 2: 잔여 슬롯 round-robin 채움 (misc는 light_score ≥ 20 하한)
6. 중복 제거 (Phase 1-3)

**모드:**
- `live`: 실제 2-Pass 선택 실행
- `shadow`: 2-Pass 계산 후 레거시와 diff 로깅 (선택 변경 없음)
- `dry_run`: 레거시 round-robin 실행 + shadow diff 로그 출력

모드 전환:
```bash
BRIEFING_SCORER_MODE=live python3 scripts/auto_news_selector.py
BRIEFING_SCORER_MODE=shadow python3 scripts/auto_news_selector.py
```

**Shadow diff 로그:** `scripts/logs/briefing_shadow_diff.log` (3-layer JSONL)

### 4.2 브리핑 생성만 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_briefing.py
```

**동작 방식:**
1. 뉴스 선정 (auto_news_selector 호출, 48시간 범위)
2. Phase 2 중복 제거 (선정 후 재검증)
3. MiMo API로 기사별 코멘트 생성 (1~2문장, 한국어)
4. 브리핑 데이터 구성 (intro + items)
5. D1에 브리핑 저장 (briefings + briefing_items 테이블)

**외부 선정 기사 전달:**
```python
from auto_briefing import main
articles = [{"id": 123, "title": "...", "link": "...", ...}]
main(selected_articles=articles)
```

**브리핑 DB 스키마:**
```sql
-- briefings
CREATE TABLE briefings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,        -- 예: "2026-08-07-1"
  intro TEXT,
  status TEXT DEFAULT 'published',
  published_at DATETIME,
  created_at DATETIME
);

-- briefing_items
CREATE TABLE briefing_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  briefing_id INTEGER NOT NULL,
  news_id INTEGER NOT NULL,
  sort_order INTEGER,
  comment TEXT,
  deep_dive_url TEXT          -- 심층글 URL (후속적으로 연결)
);
```

### 4.3 심층글 생성만 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_deep_article.py
```

※ 이 스크립트는 테스트용 main()이 포함되어 있어 단독 실행 시 테스트 기사를 크롤링/생성합니다.  
실제 파이프라인에서는 `run_pipeline.py`의 Step 3으로 실행됩니다.

### 4.4 썸네일 생성만 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_thumbnail.py <URL> <slug> --title "제목" --description "설명"
```

예시:
```bash
python3 scripts/auto_thumbnail.py \
  "https://example.com/article" \
  "openai-new-model-released" \
  --title "OpenAI 새 모델 출시" \
  --description "OpenAI가 새로운 AI 모델을 공개했다"
```

### 4.5 이메일 발송만 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/auto_email_sender.py
```

---

## 5. 뉴스 선정 알고리즘 상세

### 5.1 2-Pass 선택

**Pass 1 (임팩트 상위):**
- full_score ≥ 70점
- 최대 3개
- 클러스터 중복 방지 (동일 주제 2개 이상 제외)

**Pass 2 (다양성 보충):**
- 잔여 슬롯만큼 round-robin
- Pass 1에서 선택된 클러스터 제외
- misc 클러스터: light_score ≥ 20점 하한 적용
- 상한 미달 시 다른 클러스터에서 차순위 인출
- 최종 fallback: misc에서 full_score 순

### 5.2 스코어링

`scripts/briefing_scorer.py`에서 수행.

**Light score** (Phase A, 크롤링 없이):
- 제목/설명/출처 기반
- 엔티티 티어, 임팩트 금액, 중복 패널티 등

**Full score** (Phase B, 크롤링 후):
- 본문 내용 기반 추가 점수
- 티어 추론(reasoning) 포함

스코어 구성 요소는 `briefing_scorer.py`의 `score_article()` 함수 참조.

### 5.3 중복 제거 (3단계)

| 단계 | 위치 | 검사 방식 | threshold |
|------|------|----------|----------|
| Phase 1 | auto_news_selector | original_title Jaccard + entity overlap | 0.30 / 2개 |
| Phase 2 | auto_briefing | briefing 저장 전 재검증 | 동일 |
| Phase 3 | save_pitch_to_history | entities 저장 → 이후 Phase 2에 활용 | — |

---

## 6. Shadow Mode (신구 비교)

새로운 선택 알고리즘과 기존 round-robin 방식을 비교하기 위한 shadow 모드.

```bash
BRIEFING_SCORER_MODE=shadow python3 scripts/auto_news_selector.py
```

**로그 파일:** `scripts/logs/briefing_shadow_diff.log`

**로그 구조 (3-layer JSONL):**
```json
{"ts": "...", "layer": 1, "mode": "shadow", "data": {"diff": "CHANGED", "added": [...], "removed": [...], "added_titles": [...], "removed_titles": [...]}}
{"ts": "...", "layer": 2, "mode": "shadow", "data": {"light_histogram": {...}, "full_histogram": {...}, "light_count": N, "full_count": M}}
{"ts": "...", "layer": 3, "mode": "shadow", "data": {"borderline_count": N, "borderline_articles": [...]}}
```

- Layer 1: 선정 결과 diff (추가/제거된 기사)
- Layer 2: 스코어 분포 히스토그램
- Layer 3: 경계역(65-75점) 기사 분석 (shadow 전용)

---

## 7. 파일 구조

```
scripts/
├── run_pipeline.py              # 오케스트레이터
├── auto_news_selector.py        # 뉴스 선정
├── auto_briefing.py             # 브리핑 생성
├── auto_deep_article.py         # 심층글 생성
├── auto_thumbnail.py            # 썸네일 생성
├── auto_email_sender.py         # 이메일 발송
├── briefing_scorer.py           # 스코어링 로직
├── briefing_dedup.py            # 중복 제거
├── deploy.sh                    # 빌드 + 배포
└── logs/
    └── briefing_shadow_diff.log # shadow diff 로그
```

---

## 8. 체크리스트

### 최초 설정
- [ ] `.env` / `~/.env.common`에 모든 API 키 설정
- [ ] wrangler auth profile 설정 (`wrangler whoami`)
- [ ] Pexels API 키 발급
- [ ] Brevo API 키 + List ID 설정
- [ ] DeepSeek API 토큰 설정 (썸네일 키워드용)
- [ ] MIMO API 키 설정 (브리핑/심층글용)
- [ ] `python3 scripts/run_pipeline.py --dry-run` 실행 확인

### daily 실행
- [ ] 전날 뉴스 수집 여부 확인 (D1 뉴스 테이블)
- [ ] `python3 scripts/run_pipeline.py` 실행
- [ ] 파이프라인 로그 확인 (에러 여부)
- [ ] 이메일 수신 확인
- [ ] 사이트 반영 확인 (https://aikorea24.kr)

### 트러블슈팅
- [ ] 뉴스 선정 0건 → D1 뉴스 테이블 확인 / 크롤링 소스 설정 확인
- [ ] 브리핑 생성 실패 → MIMO API 키 / 네트워크 확인
- [ ] 이메일 발송 실패 → Brevo API 키 / Sender 인증 확인
- [ ] 배포 실패 → wrangler auth profile / CLOUDFLARE_API_TOKEN env var 확인

---

## 9. 통합 실행 예시

### 매일 아침 자동화 (launchd)

`~/Library/LaunchAgents/kr.aikorea24.pipeline-runner.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>kr.aikorea24.pipeline-runner</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/twinssn/Projects/aikorea24/.venv/bin/python3</string>
        <string>/Users/twinssn/Projects/aikorea24/scripts/run_pipeline.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/twinssn/Projects/aikorea24</string>
    <key>StandardOutPath</key>
    <string>/Users/twinssn/Projects/aikorea24/scripts/logs/pipeline_runner.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/twinssn/Projects/aikorea24/scripts/logs/pipeline_runner.log</string>
</dict>
</plist>
```

설치:
```bash
launchctl load ~/Library/LaunchAgents/kr.aikorea24.pipeline-runner.plist
```

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
