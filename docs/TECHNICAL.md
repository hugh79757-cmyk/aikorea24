# aikorea24.kr 기술 문서

**최종 업데이트: 2026-06-22**
**버전: 2.2.0**

---

## 1. 프로젝트 개요

### 1.1 소개
AI 관련 국내외 뉴스를 자동 수집, 번역, 큐레이션하여 한국어로 제공하는 웹사이트

- **사이트**: https://aikorea24.kr
- **운영**: 스타일 팩토리9 (대표: 조진연)
- **목적**: AI 도구 추천, 무료 강좌, 정부 지원사업 정보, AI 뉴스 한국어 큐레이션

### 1.2 핵심 기능
- 뉴스 자동 수집 (국내 28개+ 해외 소스)
- AI 필터링 및 번역 (GPT-4o-mini)
- 키워드 기반 콘텐츠 파이프라인
- 카드뉴스 자동 생성
- 블로그, 커뮤니티 게시판
- Google 로그인 인증
- 다크/라이트 모드

---

## 2. 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| 프레임워크 | Astro | 5.17.1 |
| 스타일링 | Tailwind CSS | 3.4.19 |
| 배포 | Cloudflare Pages | - |
| 데이터베이스 | Cloudflare D1 (SQLite) | - |
| 스토리지 | Cloudflare R2 | - |
| 인증 | Google OAuth 2.0 | - |
| 뉴스 수집 | Python 3 | - |
| AI 번역/요약 | OpenAI GPT-4o-mini | - |
| 카드뉴스 | Pillow + OpenAI | - |
| 스케줄러 | macOS launchd | - |

### 2.1 의존성 (package.json)
```json
{
  "@astrojs/cloudflare": "^12.6.12",
  "@astrojs/mdx": "^4.3.13",
  "@astrojs/rss": "^4.0.15",
  "@astrojs/sitemap": "^3.7.0",
  "@astrojs/tailwind": "^6.0.2",
  "@tailwindcss/typography": "^0.5.19",
  "astro": "^5.17.1",
  "tailwindcss": "^3.4.19"
}
```

---

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    macOS (로컬 서버)                      │
├─────────────────────────────────────────────────────────┤
│  05:30 news_collector.py (D1 뉴스 수집)                  │
│  06:00 keyword_updater.py (키워드 동적 갱신)              │
│  06:10 thread_topic_finder.py (스레드 글감 생성)          │
│  06:30 outline_generator.py (블로그 아웃라인 생성)        │
└─────────────────────┬───────────────────────────────────┘
                      │ wrangler d1 execute
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Cloudflare Pages + Workers                   │
├─────────────────────────────────────────────────────────┤
│  Astro 5 (SSR) + @astrojs/cloudflare                    │
│  API: /api/news/*, /api/posts/*, /api/auth/*            │
└─────────────────────┬───────────────────────────────────┘
                      │ D1 바인딩
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Cloudflare D1 (SQLite)                      │
├─────────────────────────────────────────────────────────┤
│  users, posts, comments, news, briefings, briefing_items│
│  briefings는 날짜별 큐레이팅용 테이블                     │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 데이터베이스 스키마

### 4.1 users
```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  google_id TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  avatar TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
```

### 4.2 posts
```sql
CREATE TABLE posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT DEFAULT 'general',
  views INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 4.3 comments
```sql
CREATE TABLE comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (post_id) REFERENCES posts(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 4.4 news
```sql
CREATE TABLE news (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  link TEXT UNIQUE NOT NULL,
  description TEXT,
  source TEXT NOT NULL,
  category TEXT DEFAULT 'AI',
  pub_date TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
```

### 4.5 briefings (날짜별 큐레이팅)
```sql
CREATE TABLE briefings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT UNIQUE NOT NULL,
  intro TEXT DEFAULT '',
  status TEXT DEFAULT 'draft',
  created_at TEXT DEFAULT (datetime('now')),
  published_at TEXT
);
```

### 4.6 briefing_items
```sql
CREATE TABLE briefing_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  briefing_id INTEGER NOT NULL,
  news_id INTEGER NOT NULL,
  sort_order INTEGER DEFAULT 0,
  comment TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (briefing_id) REFERENCES briefings(id),
  FOREIGN KEY (news_id) REFERENCES news(id)
);
```

### 4.7 인덱스
```sql
CREATE INDEX idx_news_created_at ON news(created_at DESC);
CREATE INDEX idx_news_country ON news(country);
CREATE INDEX idx_news_category ON news(category);
```

---

## 5. 뉴스 수집 시스템

### 5.1 수집 소스 (28개+)

#### 국내 뉴스
- 네이버 검색 API (AI타임스, 전자신문 등)
- 과기정통부 보도자료
- 행안부 보도자료
- 공공데이터포털 정부 공문서

#### 해외 뉴스 (RSS)
| 카테고리 | 소스 |
|----------|------|
| AI 전문 | TechCrunch AI, MIT Tech Review, Ars Technica AI, VentureBeat AI, The Verge AI, Wired AI, ZDNET AI, AI News EU |
| 빅테크 공식 | OpenAI Blog, Google AI Blog, HuggingFace Blog, GitHub Blog |
| 주요 언론 | CNN Technology, Reuters Technology, Business Insider AI, NYT Technology, Washington Post Technology, BBC Technology, SCMP China Tech |
| AI 전용 피드 | NYT AI Spotlight, The Guardian AI, Financial Times AI, Fast Company AI |
| 뉴스레터/블로그 | The Decoder, MarkTechPost, Ben's Bites, Simon Willison, Interconnects AI |
| 커뮤니티 | Hacker News (Algolia API) |

### 5.2 AI 필터링 알고리즘

#### 기존 필터 (is_ai)
```python
STRONG_KEYWORDS = ["AI", "GPT", "인공지능", ...]
WEAK_KEYWORDS = ["로봇", "자동화", ...]
EXCLUDE_KEYWORDS = ["귀촌", "귀어", "교복", ...]
```

#### 강화 필터 (is_ai_related)
```python
# 1차 키워드 10개 그룹
GROUP1 = ["AI", "인공지능", "artificial intelligence"]
GROUP2 = ["LLM", "대규모언어모델", "large language model"]
# ... 총 10개 그룹

# 2차 키워드 (2개 이상 매칭 시 AI 관련으로 판단)
SECONDARY = ["robot", "automation", "transformer", ...]

# REJECT 조건 (단독 기사 제외)
REJECT = ["자동차", "주가", ...]
```

### 5.3 중복 제거
1. 제목 해시 기반 중복 체크
2. prefix/키워드/고유명사 3단계 유사도 기반 중복 방지
3. 특수문자 안전 처리

### 5.4 Reuters fallback
RSS 실패 시 Google News 검색 우회 URL 자동 재시도

---

## 6. 키워드 파이프라인 (v2.2)

### 6.1 keywords.json 구조
```json
{
  "keyword": "챗GPT",
  "search_volume": 150000,
  "grade": "S",
  "intent": "최신 기능, 활용법, 비용 비교",
  "db_query": "chatgpt OR 챗GPT",
  "source": "seed"
}
```

### 6.2 처리 흐름
```
seeds.json (10개 베이스)
    ↓
D1 오늘 뉴스 기반 키워드 추출 (GPT-4o-mini)
    ↓
네이버 검색광고 API 검색량/경쟁도 조회 (HMAC-SHA256)
    ↓
grade 자동 계산 (S: 10만+, A: 3만+, B: 그 외)
    ↓
intent + db_query 자동 생성 (GPT-4o-mini)
    ↓
keywords.json 갱신 (source 필드: seed/news)
```

### 6.3 실행 스케줄
| 시각 | 스크립트 | 작업 |
|------|----------|------|
| 05:30 | `news_collector.py` | D1 news 테이블 뉴스 수집 |
| 06:00 | `keyword_updater.py` | keywords.json 동적 갱신 |
| 06:10 | `thread_topic_finder.py` | threads/YYYYMMDD/ 스레드 글감 생성 |
| 06:30 | `outline_generator.py` | outlines/YYYYMMDD/ 블로그 아웃라인 생성 |

---

## 7. 콘텐츠 생성 시스템

### 7.1 스레드 글감 생성기 (thread_topic_finder.py)
1. 1차: title 기반 클러스터링 (GPT-4o-mini)
2. 스코어링:
   - 해외+국내 교차: +3점
   - data_points 3개+: +2점
   - contrast_possible: +2점
   - 기사 3개+: +1점
3. Top 5 소재 → GPT-4o 아웃라인 생성
4. 구조: 훅/반전/스레드 7단계

### 7.2 블로그 아웃라인 생성기 (outline_generator.py)
1. keywords.json 로드
2. 각 키워드의 db_query로 D1 뉴스 DB 검색 (오늘 + 어제)
3. 매칭 기사 있으면 → 키워드 intent + 기사 내용으로 아웃라인 생성
4. 매칭 기사 없으면 → 키워드 intent만으로 아웃라인 생성
5. 저장: `outlines/YYYYMMDD/키워드슬러그_outline.md`

### 7.3 아웃라인 메타정보
```markdown
- 키워드: {keyword}
- 검색량: {search_volume}
- 등급: {grade}
- 매칭기사: {매칭된 기사 수}건
- 검색의도: {intent}
```

### 7.4 카드뉴스 생성 (card_news_generator.py)
- Pillow로 이미지 생성
- OpenAI로 텍스트 합성
- KDE Connect로 안드로이드 폰 전송

---

## 8. 웹사이트 구조

### 8.1 주요 페이지
| 경로 | 설명 |
|------|------|
| `/` | 홈페이지 (오늘의 AI 브리핑) |
| `/blog` | 블로그 목록 |
| `/blog/[id]` | 블로그 상세 |
| `/tools` | AI 도구 소개 |
| `/glossary` | AI 용어사전 |
| `/chronicle` | AI 타임라인 |
| `/news` | 뉴스 |
| `/community` | 커뮤니티 게시판 |
| `/community/write` | 글쓰기 |
| `/community/[id]` | 글 상세/댓글 |
| `/pricing` | 요금제 |
| `/briefing/[date]` | 날짜별 브리핑 |

### 8.2 API 엔드포인트
| 경로 | 메서드 | 설명 |
|------|--------|------|
| `/api/auth/login` | GET | Google 로그인 |
| `/api/auth/callback/google` | GET | Google 콜백 |
| `/api/news/latest` | GET | 최신 뉴스 |
| `/api/news/policy` | GET | 정책 뉴스 |
| `/api/news/benefit` | GET | 혜택 뉴스 |
| `/api/news/global` | GET | 해외 뉴스 |
| `/api/news/official` | GET | 기업 공식 발표 |
| `/api/posts` | GET/POST | 글 목록/작성 |
| `/api/posts/[id]` | GET/PUT/DELETE | 글 상세/수정/삭제 |
| `/api/posts/[id]/comments` | GET/POST | 댓글 |
| `/api/payments/request` | POST | 결제 요청 |
| `/api/payments/confirm` | POST | 결제 확인 |

### 8.3 인증 시스템
- Google OAuth 2.0
- 리다이렉트 URI: `https://aikorea24.kr/api/auth/callback/google`
- 시크릿: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, AUTH_SECRET

### 8.4 다크/라이트 모드
- Tailwind `darkMode: class`
- localStorage 테마 저장
- FOUC 방지: html 인라인 스크립트

---

## 9. 배포 및 인프라

### 9.1 Cloudflare 설정 (wrangler.toml)
```toml
name = "aikorea24"
compatibility_date = "2024-12-01"
pages_build_output_dir = "./dist"

[[d1_databases]]
binding = "DB"
database_name = "aikorea24-db"
database_id = "bec650ce-f732-46bc-87c0-bd76ed17e42a"

[[r2_buckets]]
binding = "R2"
bucket_name = "aikorea24-files"
```

### 9.2 환경변수
#### Cloudflare Pages 시크릿
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `AUTH_SECRET`
- `TOSS_CLIENT_KEY` (미등록)
- `TOSS_SECRET_KEY` (미등록)

#### 로컬 .env
- `DATA_GO_KR_KEY`: 공공데이터포털 API 키
- `NAVER_CLIENT_ID`: 네이버 검색 API
- `NAVER_CLIENT_SECRET`: 네이버 검색 API

### 9.3 빌드 명령어
```bash
npm run build  # Astro 빌드 + _routes.json 패치
npm run deploy  # Cloudflare Pages 배포
```

---

## 10. 파일 구조

```
aikorea24/
├── api_test/                    # 뉴스 수집 Python 스크립트
│   ├── news_collector.py        # 메인 수집기 (28개 RSS + HN)
│   ├── card_news_generator.py   # 카드뉴스 생성
│   ├── senior_briefing.py       # 노인복지 브리핑
│   ├── gov_doc_collector.py     # 정부 문서 수집
│   └── .env.sh                  # 환경변수
├── scripts/                     # 동적 키워드 및 콘텐츠 파이프라인
│   ├── keyword_updater.py       # 키워드 자동 갱신
│   ├── thread_topic_finder.py   # 스레드 글감 생성
│   ├── outline_generator.py     # 블로그 아웃라인 생성
│   ├── seeds.json               # 베이스 씨드 키워드
│   ├── keywords.json            # 동적 키워드 테이블
│   ├── outlines/                # 생성된 아웃라인
│   └── threads/                 # 생성된 스레드
├── src/
│   ├── components/              # Astro 컴포넌트
│   ├── content/                 # 블로그, 도구 콘텐츠 (MDX)
│   ├── layouts/                 # 레이아웃
│   ├── lib/                     # 유틸리티 (auth.ts 등)
│   ├── pages/                   # 페이지 및 API
│   │   ├── api/                 # API 엔드포인트
│   │   ├── blog/                # 블로그
│   │   ├── community/           # 커뮤니티
│   │   └── news.astro           # 뉴스
│   └── styles/                  # 전역 스타일
├── public/                      # 정적 파일
├── schema.sql                   # D1 스키마
├── wrangler.toml                # Cloudflare 설정
├── package.json                 # 의존성
├── astro.config.mjs             # Astro 설정
└── tailwind.config.mjs          # Tailwind 설정
```

---

## 11. 개발 가이드

### 11.1 로컬 개발
```bash
# 웹사이트
npm install
npm run dev

# 뉴스 수집
cd api_test
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
source .env.sh
python3 news_collector.py
```

### 11.2 배포
```bash
npm run build
npm run deploy
```

### 11.3 뉴스 수집 수동 실행
```bash
# 국내 뉴스만
python3 news_collector.py --source kr

# 해외 뉴스만
python3 news_collector.py --source global

# 전체
python3 news_collector.py
```

---

## 12. 문제 해결

### 12.1 빌드 에러
- `Astro.request.headers` 에러: prerender 페이지에서 발생
- 해결: SSR 모드로 전환 또는 특정 페이지 비활성화

### 12.2 뉴스 수집 실패
- RSS 피드 접근 차단: User-Agent 설정 필요
- API 키 만료: .env 파일 확인
- D1 연결 실패: wrangler.toml 설정 확인

### 12.3 카드뉴스 생성 실패
- Pillow 설치 필요: `pip install Pillow`
- OpenAI API 키 확인

---

## 13. 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|-----------|
| v2.2.0 | 2026-06-10 | 동적 키워드 파이프라인 |
| v2.1.0 | 2026-05 | 해외 RSS 10개 추가, AI 필터 강화 |
| v2.0.0 | 2026-02-21 | 해외 뉴스 수집, 기업 공식 발표 |
| v1.4.0 | 2026-02-16 | 블로그 UI 개선 |
| v1.3.0 | 2026-02 | Google AdSense, Pinterest |
| v1.2.0 | 2026-02 | 노인복지, 카드뉴스 |
| v1.1.0 | 2026-01 | 뉴스 수집 고도화 |
| v1.0.0 | 2026-01 | 최초 릴리즈 |

---

## 14. 참고 문서

- [README.md](./README.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [SOP.md](./SOP.md)
- [AGENTS.md](./AGENTS.md)
