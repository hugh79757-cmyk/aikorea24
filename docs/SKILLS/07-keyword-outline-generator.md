# 키워드 아웃라인 생성 스킬

> keywords.json 기반 키워드 테이블 → D1 뉴스 DB 검색 → 매칭 기사 있으면 내용 포함 아웃라인, 없으면 intent만으로 아웃라인 생성

---

## 1. 개요

사전 정의된 키워드 테이블을 기반으로 각 키워드에 대한 블로그 아웃라인을 자동 생성하는 파이프라인. D1 뉴스 DB에서 오늘+어제 기사를 검색해 매칭되는 기사가 있으면 기사 내용을 반영한 아웃라인을, 없으면 키워드 intent만으로 아웃라인을 생성.

**주요 스크립트:** `scripts/thread_topics/outline_generator.py`

**입력:** `scripts/thread_topics/keywords.json`

**출력:** `scripts/thread_topics/outlines/YYYYMMDD-키워드슬러그_outline.md`

---

## 2. 사전 준비

### 2.1 환경변수

```bash
# MIMO/DeepSeek API (아웃라인 생성용)
MIMO_API_KEY=xxx
# 또는
DEEPSEEK_API_TOKEN=sk-xxx

# Cloudflare
CLOUDFLARE_ACCOUNT_ID=xxx

# Telegram 알림
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

### 2.2 keywords.json 구조

`scripts/thread_topics/keywords.json`:

```json
{
  "keyword-slug": {
    "keyword": "키워드 제목",
    "search_volume": "1000",
    "grade": "A",
    "intent": "검색 의도 설명",
    "db_query": "SELECT ... FROM news WHERE ..."
  },
  ...
}
```

| 필드 | 설명 |
|------|------|
| `keyword` | 사람이 읽을 수 있는 키워드명 |
| `search_volume` | 검색량 (참고) |
| `grade` | 등급 (A/B/C) |
| `intent` | 검색 의도 설명 (아웃라인 생성 시 사용) |
| `db_query` | D1에서 관련 기사를 찾기 위한 SQL 쿼리 |

### 2.3 Python 의존성

```bash
pip install requests
```

---

## 3. 실행 방법

### 3.1 수동 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/thread_topics/outline_generator.py
```

### 3.2 특정 키워드만 실행

코드 수정이 필요하지만, 특정 키워드 슬러그 필터 추가 가능.

---

## 4. 동작 흐름

### 4.1 키워드 테이블 로드

```python
def load_keywords():
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data  # {slug: {keyword, search_volume, grade, intent, db_query}, ...}
```

### 4.2 D1 뉴스 검색

```python
def query_d1(sql):
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    # Cloudflare D1 REST API 호출
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {os.environ.get('CLOUDFLARE_API_TOKEN', '')}",
        "Content-Type": "application/json"
    }
    payload = {"sql": sql}
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()
```

각 키워드의 `db_query`를 실행해 관련 기사 검색.

### 4.3 아웃라인 생성

**매칭 기사 있음:**
```
- 키워드: {keyword}
- 검색량: {search_volume}
- 등급: {grade}
- 매칭기사: {N}건
- 검색의도: {intent}

## 기사 요약
{기사 제목 + 내용 요약}

## 아웃라인
1. ...
2. ...
```

**매칭 기사 없음:**
```
- 키워드: {keyword}
- 검색량: {search_volume}
- 등급: {grade}
- 매칭기사: 0건
- 검색의도: {intent}

## 아웃라인
1. ... (intent 기반)
```

### 4.4 파일 저장

`scripts/thread_topics/outlines/YYYYMMDD-키워드슬러그_outline.md`

### 4.5 텔레그램 알림

생성 완료 시 텔레그램으로 알림 전송.

---

## 5. 파일 구조

```
scripts/
└── thread_topics/
    ├── outline_generator.py          # 아웃라인 생성기
    ├── keywords.json                 # 키워드 테이블
    └── outlines/                     # 생성된 아웃라인
        ├── 20260807-keyword1_outline.md
        └── ...
```

---

## 6. 체크리스트

### 최초 설정
- [ ] `scripts/thread_topics/keywords.json` 작성/보완
- [ ] D1 DB에 뉴스 데이터 존재 확인
- [ ] API 키 설정 (MIMO 또는 DeepSeek)
- [ ] `python3 scripts/thread_topics/outline_generator.py` 테스트 실행
- [ ] 생성된 아웃라인 파일 확인

### 정기 실행
- [ ] 매일/주기적 실행 스케줄 설정
- [ ] 신규 키워드 추가 시 keywords.json 업데이트
- [ ] 생성된 아웃라인 품질 검토

---

## 7. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| D1 쿼리 실패 | API 토큰/권한 | CLOUDFLARE_API_TOKEN 확인 |
| 매칭 기사 0건 | db_query 조건 너무 좁음 | 쿼리 조건 완화 |
| 아웃라인 생성 실패 | API 키/프롬프트 | API 키 확인, 프롬프트 조정 |
| 파일 저장 실패 | 디렉토리 없음 | `scripts/thread_topics/outlines/` 생성 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
