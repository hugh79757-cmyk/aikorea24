---
slug: threads-self-improvement
date: 2026-09-01
status: planned
---

# Threads 자가개선 (Self-Improvement) 로직 — 성과 측정 → 분석 → 피드백 루프

## 목표

Threads 파이프라인이 자신의 발행 성과를 측정하고, 데이터 기반으로 피치 생성(토픽/포맷/시간대 선택)에 피드백하는 폐쇄 루프 구축.

**핵심 정정 (라이브 프로브 완료, 2026-09-01 22:5x KST)**: Threads insights API는 **views 제공함**.
이전 분석("조회수 미제공, 답글 프록시 사용")은 틀림. 실측:
- `GET /v1.0/{media_id}/insights?metric=views,likes,replies,reposts,quotes&access_token=...` → HTTP 200
- 18:00 root 18122058901870182: views **311**, likes 2, replies 5, reposts/quotes (응답 계속)
- 20:00 root 18426508516181136: views **194**, likes 1
- `likes`는 media 필드가 아니라 insights metric으로만 조회 (media fields에 `likes` 넣으면 code 100 "Tried accessing nonexisting field (likes)")
- `metric` 미지정 시 code 100 "The parameter metric is required"
- `replies` metric = `thread_replies` 내부 이름, 반환 name은 "replies" — **자기 링크 답글 포함** (18:00 포스트 replies 5 = SpeedFloor 텍스트 답글들 + 우리가 단 🔗 링크 답글 18109210742151438). 자가 답글 제외 시 replies edge 텍스트 확인 또는 replies-1 보정 필요
- media fields에 `username` 있음 (aikorea24) → 자기 답글 식별 가능
- 토큰: EnvConfig 기반 `publisher.load_env()` 정상 동작, `.env` 수동 파싱은 quote 이슈로 code 190 (EnvConfig 경로 사용할 것)

## 데이터 소스 (라이브 프로브로 검증됨)

| 데이터 | 획득 방법 | 확인 상태 |
|--------|----------|----------|
| views/likes/replies/reposts/quotes | `/v1.0/{media_id}/insights?metric=views,likes,replies,reposts,quotes` | ✅ 라이브 200 확인 |
| 자기 답글 식별 | `/v1.0/{media_id}/replies` edge (id/text) + username | ✅ 확인 (링크 답글 노출됨) |
| root post ID | `publish_thread_chain()` 반환값 | 이미 발행 시점에 확보 |
| 포맷/토픽/훅 메타 | main_v3.py 발행 컨텍스트 | 코드에 존재 (`📌 format: D`) |

## 아키텍처 — 3단계 (기존 분석 유지, views 직접 측정으로 업그레이드)

```
[1 측정] 발행 시: root_id + 메타 → performance_log.json
          일 1회: insights 수집 → performance_log.json 갱신
[2 분석] weekly_analyzer.py: 포맷/토픽/시간대별 views·engagement율 집계 → insights_report.json
[3 적용] pitch.py 프롬프트에 최근 30일 상위 토픽/포맷 주입
```

### 로그 파일 설계

`scripts/threads/logs/performance_log.json`:
```json
{
  "posts": [
    {
      "root_id": "18122058901870182",
      "posted_at": "2026-09-01T20:00:53+09:00",
      "format": "D",
      "article_id": "47319",
      "title": "인천성장펀드 4번째 투자처 '스피드플로어'",
      "source": "네이버뉴스",
      "topic_tags": ["스타트업", "투자"],       // 제목에서 추출 (선택)
      "metrics": null                           // 일 1회 수집 시 채움
    }
  ]
}
```
metrics 수집 후:
```json
"metrics": {
  "collected_at": "2026-09-02T06:00:00+09:00",
  "views": 311, "likes": 2, "replies": 5,
  "reposts": 0, "quotes": 0,
  "net_replies": 4                             // 자기 답글(링크) 1개 제외 보정
}
```

### 배치 스케줄

- **[1 측정-기록]**: main_v3.py 발행 완료 직후 (기존 `_log_api_based_publish` 패턴 복제). 추가 API 호출 0건.
- **[1 측정-수집]**: 신규 `scripts/threads/insights_collector.py` — 매일 06:00 launchd (`kr.aikorea24.threads-insights`). 어제+그제 발행 건의 insights 조회 (48h window: 직후보다 반응 안정화). 발행 12건/일 × 1 call = 12 calls/일 — API 한도 여유.
- **[2 분석]**: 동일 insights_collector.py가 수집 후 집계 (별도 프로세스 아님 — ponytail: 파일 하나).
- **[3 적용]**: pitch.py `generate_pitch()`가 시작 시 `insights_report.json` 읽어 프롬프트에 "최근 30일 반응 상위 토픽: ..." 한 줄 주입. 파일 없으면/30일 미만 데이터면 주입 스킵 (부트스트랩).

## 변경 대상 (최소 diff)

### 1. `scripts/threads/performance_log.py` (신규, ~80줄)
- `record_publish(root_id, posted_at, format, article_id, title, source, topic_tags)` — 발행 시 메타 기록
- `collect_insights(days=2)` — 미수집 posts의 insights GET, net_replies 보정 (replies edge에서 username==aikorea24 제외 카운트; 실패 시 replies-1)
- `analyze()` — 최근 30일 집계: 포맷별/토픽별/2h 슬롯별 평균 views + engagement율((likes+net_replies)/views) → `insights_report.json`
- 토큰: `publisher.load_env()` 재사용 (EnvConfig). 직접 .env 파싱 금지 (code 190 재발).
- 분석 문턱: 최소 30 posts 없으면 report 스킵 (통계 무의미 방지)

### 2. `scripts/threads/main_v3.py` (수정, ~5줄)
- 발행 성공 블록 (`result` true 직후, ~line 429)에:
```python
from performance_log import record_publish
record_publish(root_id=result, posted_at=now, format=_fmt,
               article_id=pitch_id, title=publish_article.get('title',''),
               source=publish_article.get('source',''), topic_tags=[])
```
- `run_v3` 서명 변경 없음. 기존 흐름·검증 그대로 (break nothing).

### 3. `scripts/threads/v3/narrative_pitcher.py` 경유 `pipeline/threads/pitch.py` (수정, ~10줄)
- `generate_pitch()` 시작 부분에서 insights_report.json 존재 시:
  - 상위 토픽 3개 (평균 views 기준) → 프롬프트에 "최근 반응이 좋았던 토픽: A, B, C (참고용, 강제 아님)" 주입
  - 포맷별 평균은 현재 단일 포맷(D)이라 스킵 (contrast 채택 시에만 유효)
- dry-run 포함 전 경로 주입됨 → 검증 가능

### 4. launchd `kr.aikorea24.threads-insights.plist` (신규)
- 일 06:00, `.venv/bin/python3 scripts/threads/insights_collector.py`
- 로그: `scripts/threads/logs/insights_collector.log`
- 등록 절차는 execute 단계에서 (기존 threads-publisher.plist 패턴 복제)

### 5. `scripts/threads/insights_collector.py` (신규, ~15줄)
```python
from performance_log import collect_insights, analyze
collect_insights(days=2)
analyze()
```
진입점 래퍼만 (ponytail: 로직은 performance_log.py 단일 파일).

## 검증 계획

| 항목 | 방법 |
|------|------|
| record_publish | `--dry-run` 후 performance_log.json에 레코드 존재 + 스키마 확인 |
| collect_insights | 수동 실행 → 18:00/20:00 실제 root_id의 views(311/194 근사) 기록 확인 — 프로브 값을 라이브 회귀 기준선으로 사용 |
| net_replies 보정 | 18:00 포스트 replies=5 → net_replies=4 (자기 링크 답글 1개) 확인 |
| analyze | 30 posts 미만 → report 미생성 (부트스트랩 보호) 확인 |
| 피드백 주입 | insights_report.json 수동 생성 후 `--dry-run` 로그에서 프롬프트 주입 라인 확인 |
| 회귀 방지 | 기존 dry-run/publish 흐름 변화 없음 (append-only 수정) — 22:00 슬롯 정상 발행 확인 |

## 명시적 스코프 제외 (YAGNI)

- 통계 모델/유의성 검정 — 단순 평균 비교로 충분, 2~4주 데이터 쌓이면 재평가
- 훅 문구별 A/B — 데이터량 부족, views→hook 텍스트 클러스터링은 3차 확장
- contrast 포맷 가중치 — 단일 포맷 운영 중
- 조회수 미제공 대응(이전 설계) — 무효화됨 (views 제공 확인)

## 리스크

- insights "in development" 라벨 (views metric) — Meta가 지표 변경 가능 → 수집 실패 시 metrics에 error 기록하고 계속 (수집 불가 ≠ 발행 중단)
- replies에 자기 답글 포함 → net_replies 보정으로 처리, 보정 실패 시 raw 값 저장
- 데이터 부족 (부트스트랩 2~4주) → 30 posts 문턱 + report 없으면 주입 스킵 → 폐쇄 루프가 graceful degradation
