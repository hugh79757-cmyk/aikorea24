# LIVE-DATA-BACKUP — news.title 영어 3건 한국어 UPDATE (260913-0af Task 4c)

> 파괴적 변경 4단계 프로토콜 — 사전 카운트/백업 단계 (1/4)
> 대상: briefing 2026-09-13-1 라이브 렌더링 영어 제목 3건 (news_ids 50155, 50235, 50269)
> briefing_items에 title 컬럼 없음 (PRAGMA table_info 확인: id, briefing_id, news_id, sort_order, comment, created_at, deep_dive_url) — news 테이블만 수정하면 됨

## 사전 상태 (UPDATE 전 SELECT — 2026-09-13 실행)

| news_id | title (원본 — 영어) | original_title | country | source |
|---|---|---|---|---|
| 50155 | Steve Jones on the pros and cons of AI datacentres – cartoon | Steve Jones on the pros and cons of AI datacentres – cartoon | us | The Guardian AI |
| 50235 | GPT-6 Astra appears to show a "step change" in spatial reasoning based on early benchmarks | GPT-6 Astra appears to show a "step change" in spatial reasoning based on early benchmarks | us | The Decoder |
| 50269 | Conversations that AIs are having in the office that may influence your performance review and pay | Conversations that AIs are having in the office that may influence your performance review and pay | us | CNBC Tech |

## UPDATE 계획 (한국어 번역 — 고유명사 유지)

| news_id | 새 title (한국어) |
|---|---|
| 50155 | 스티브 존스가 그린 AI 데이터센터의 장단점 – 만화 |
| 50235 | GPT-6 Astra, 초기 벤치마크에서 공간 추론 '획기적 변화' 보여줘 |
| 50269 | 사무실에서 오가는 AI 대화가 당신의 인사평가와 연봉에 영향줄 수 있다 |

## 사후 검증 (UPDATE 후 SELECT — 실행 결과, 4/4 완료)

- [x] 4단계: post-verify SELECT 결과 (2026-09-13 실행):

```
{'id': 50155, 'title': '스티브 존스가 그린 AI 데이터센터의 장단점 – 만화', 'original_title': 'Steve Jones on the pros and cons of AI datacentres – cartoon'}
{'id': 50235, 'title': 'GPT-6 Astra, 초기 벤치마크에서 공간 추론 ‘획기적 변화’ 보여줘', 'original_title': 'GPT-6 Astra appears to show a "step change" in spatial reasoning based on early benchmarks'}
{'id': 50269, 'title': '사무실에서 오가는 AI 대화가 당신의 인사평가와 연봉에 영향줄 수 있다', 'original_title': 'Conversations that AIs are having in the office that may influence your performance review and pay'}
```

3건 모두 한국어 title 적용 확인. original_title은 영어 원문 유지 (롤백 가능 상태).
브리핑 2026-09-13-1 (briefing_items ids 1571-1576)는 news JOIN으로 title 조회 → 즉시 한국어 렌더링.

