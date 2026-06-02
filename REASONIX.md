# Reasonix project memory

Notes the user pinned via the `#` prompt prefix. The whole file is
loaded into the immutable system prefix every session — keep it terse.

- Task: news_collector.py 해외 RSS 소스 추가 및 AI 키워드 필터링 강화

## 작업 전 필수 확인
1. 현재 `news_collector.py` 전체 코드를 먼저 읽어라
2. 기존 RSS 파싱 방식, 필터링 로직, D1 저장 구조를 파악한 뒤 작업하라
3. 기존 동작 중인 소스들은 절대 건드리지 마라

---

## 작업 1: 신규 RSS 소스 추가

기존 해외 RSS 소스 리스트에 아래 소스들을 추가하라.
기존 소스 목록이 딕셔너리/리스트 형태로 관리되고 있다면 그 구조를 그대로 따라라.

### 추가할 소스 목록

| 매체 | RSS URL | category 값 | 비고 |
|------|---------|-------------|------|
| CNN Technology | http://rss.cnn.com/rss/cnn_tech.rss | global | AI 키워드 필터링 필수 |
| Reuters Technology | https://feeds.reuters.com/reuters/technologyNews | global | AI 키워드 필터링 필수 |
| Business Insider AI | https://feeds.businessinsider.com/custom/all | global | AI 키워드 필터링 필수 |
| NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | global | AI 키워드 필터링 필수 |
| NYT AI Spotlight | https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/spotlight/artificial-intelligence/rss.xml | global | AI 전용 피드, 필터링 완화 가능 |
| Washington Post Technology | https://feeds.washingtonpost.com/rss/business/technology | global | AI 키워드 필터링 필수 |
| The Guardian AI | https://www.theguardian.com/technology/artificialintelligenceai/rss | global | AI 전용 피드, 필터링 완화 가능 |
| BBC Technology | https://feeds.bbci.co.uk/news/technology/rss.xml | global | AI 키워드 필터링 필수 |
| Financial Times AI | https://www.ft.com/artificial-intelligence?format=rss | global | AI 전용 피드, 필터링 완화 가능 |
| Fast Company AI | https://www.fastcompany.com/section/artificial-intelligence/rss | global | AI 전용 피드, 필터링 완화 가능 |

Reuters RSS가 응답 없거나 파싱 실패 시,
아래 Google News 우회 URL로 자동 fallback 처리하라:
https://news.google.com/rss/search?q=site:reuters.com+artificial+intelligence&hl=en&gl=US&ceid=US:en

---

## 작업 2: AI 키워드 필터링 함수 구현 또는 강화

### 요구사항

기존에 필터링 함수가 있으면 아래 기준으로 강화하고,
없으면 신규로 `is_ai_related(title: str, summary: str = "") -> bool` 함수를 만들어라.

### 필터링 기준

**[PASS 조건] 아래 키워드 중 하나라도 title 또는 summary에 포함되면 통과**

1차 키워드 (고신뢰, 단독으로 통과):
- AI, A.I., artificial intelligence
- machine learning, deep learning
- large language model, LLM, LLMs
- ChatGPT, GPT-4, GPT-5, Claude, Gemini, Grok, Llama, Mistral
- OpenAI, Anthropic, DeepMind, Hugging Face
- generative AI, gen AI, genAI
- neural network
- natural language processing, NLP
- computer vision
- autonomous, self-driving (단, 자동차 단독 기사 제외 — 아래 REJECT 참고)

2차 키워드 (복합 조건, 아래 중 2개 이상 포함 시 통과):
- robot, robotics
- automation
- algorithm
- data model, foundation model
- transformer, diffusion model
- prompt, inference, fine-tuning

**[REJECT 조건] 아래 패턴은 1차 키워드가 있어도 제외**
- 제목에 "self-driving car", "autonomous vehicle" 만 있고 AI 언급 없는 순수 자동차 뉴스
- 제목에 "stock", "earnings", "revenue", "profit" 만 있는 순수 주가/실적 뉴스
  (단, "AI stock", "AI earnings" 처럼 AI와 결합된 경우는 통과)

### 함수 적용 범위
- 위 작업 1에서 추가한 "AI 키워드 필터링 필수" 표기 소스 전체에 적용
- "AI 전용 피드, 필터링 완화 가능" 소스는 1차 키워드만으로 필터링 (REJECT 조건은 동일 적용)
- 기존 소스들은 현재 필터링 방식 유지 (변경 금지)

---

## 작업 3: 소스별 에러 핸들링

각 신규 소스에 대해 아래 처리를 적용하라:

1. **타임아웃**: 소스당 fetch timeout = 15초
2. **실패 시 skip**: 특정 소스 fetch/parse 실패해도 전체 스크립트가 멈추지 않도록
   기존 에러 핸들링 패턴이 있으면 그것을 그대로 따라라
3. **Reuters fallback**: 작업 1에서 명시한 fallback URL로 자동 전환
4. **로그**: 실패한 소스는 기존 로깅 방식대로 기록

---

## 작업 4: 중복 제거 확인

기존 코드에 중복 제거 로직(link UNIQUE 기반 또는 별도 dedup 처리)이 있을 것이다.
신규 소스도 동일한 중복 제거 흐름을 타는지 확인하고, 누락되어 있으면 포함시켜라.
중복 제거 로직 자체를 수정하지는 마라.

---

## 작업 5: 검증

코드 수정 완료 후:
1. 신규 소스 10개가 실제로 리스트에 등록되어 있는지 확인
2. `is_ai_related()` 함수(또는 강화된 필터링 함수)가 아래 테스트 케이스를 통과하는지 확인

**통과해야 할 케이스 (is_ai_related = True)**
- "OpenAI releases new GPT-5 model"
- "Google DeepMind achieves breakthrough in protein folding with AI"
- "How companies are using generative AI to cut costs"
- "Claude 3.5 outperforms rivals on new benchmark"
- "Reuters: Anthropic raises $2 billion in funding"

**걸러져야 할 케이스 (is_ai_related = False)**
- "Tesla reports record quarterly revenue"
- "Apple announces new iPhone pricing"
- "Ford recalls 500,000 autonomous vehicles over brake issue"
- "Amazon Q3 earnings beat Wall Street expectations"

테스트 케이스 결과를 코드 아래 주석 또는 출력으로 보여주고 완료 보고하라.

---

## 절대 하지 말 것
- 기존 소스 목록 수정 또는 삭제
- D1 저장 스키마 변경
- 기존 필터링/파싱 로직을 리팩토링 명목으로 변경
- 작업 범위 외 파일 수정 (publish_*.py, auto_publish.py 등)
