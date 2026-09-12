# FINDINGS: 브리핑 파이프라인 프롬프트 릭 진단

> 진단일: 2026-09-12 · quick-260912-vyc · 산출물 성격: 진단 보고서 (코드 수정 0건, DB 변경 0건)

## 1. 증거

### 1.1 스캔 범위 및 명령

| 데이터 소스 | 범위 | 명령/방법 |
|---|---|---|
| D1 briefing_items.comment (최근 14일) | 150 rows (2026-08-29 ~ 2026-09-12) | `env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --json --command "SELECT b.date, i.news_id, i.comment FROM briefing_items i JOIN briefings b ON i.briefing_id=b.id WHERE b.date >= '2026-08-29' ORDER BY b.date DESC, i.id LIMIT 200"` → 로컬 python 정규식 스캔 |
| D1 briefing_items.comment (전체 이력, 영어 메타 패턴) | 전체 1,496 rows | `WHERE i.comment LIKE '%Here is%' OR ... OR i.comment LIKE '%I cannot%'` (8패턴) |
| D1 briefings.intro (최근 14일) | 25 rows | 동일 wrangler SELECT → python 스캔 |
| 아웃라인 MD | 745 files (scripts/thread_topics/outlines/2026*) | python `glob` + 행 단위 영어 문장 스캔 (기능어 3개 이상 + 행 내 한글 미세) |
| model_router 일일 로그 | scripts/threads/logs/2026-09-11.log, 2026-09-12.log (릭 row 생성 시각대) | `grep -E 'finish_reason' scripts/threads/logs/2026-09-12.log` |

### 1.2 영어 릭 샘플 ↔ 출처 ↔ tier 상관표

**[검증불가] 영어 문장/영어 메타 텍스트("Here is", "Sure," 등) 릭 샘플: 0건.**
근거: D1 최근 14일 150 rows + 전체 이력 영어 메타 LIKE 8패턴 0건 + briefings.intro 25 rows 0건 + 아웃라인 745 files 0건. 어떤 스캔에서도 영어 문장 형태의 프롬프트 릭이 검출되지 않았다. 검출 스크립트는 영어 기능어(the/is/are/will/of/to 등) 3개 이상 + 한글 부재 문장, LLM 메타 인사말 8패턴, latin 문자 비율 25% 초과 3종을 모두 시도했다.

**[부분검증] 프롬프트 구조 미러링(반복 루프) 릭: 1건** — 영어가 아닌 형태지만 "프롬프트 구조" 후보의 직접 증거. 아래 3열 대응표:

| 릭 샘플 (원문 인용, 앞부분) | 출처 파일/DB row | 추정 응답 tier |
|---|---|---|
| `**제목: 앤트로픽, 악성 AI 에이전트도 CAPTCHA를 싫어한다고 공개** ... **코멘트:**` 블록이 **동일 내용으로 반복** (제목/출처/내용/코멘트 템플릿을 채우지 않고 템플릿 자체를 수회 재출력, 코멘트 비어있음) | D1 `briefing_items` (briefing_date=2026-09-11-2, news_id=49731, created_at=2026-09-12 13:25:08 UTC). 라이브 렌더링: src/pages/briefing/[date].astro가 이 row를 그대로 출력 | **nvidia-nemotron** [부분검증] — 근거: 일일 로그 `scripts/threads/logs/2026-09-12.log`에서 해당 시각대(13:25 UTC = 로컬 20:25)에 `nvidia-nemotron finish_reason=stop content_len=708/1429/122/135/56/78/79/116` 연속 응답 블록 존재. 로그에 content 스니펫이 없어 "동일 응답"은 확증 불가, 시각적 일치만으로 추정 |

### 1.3 스캔 결과 요약 (3분법)

- [검증됨] 영어 메타 릭 0건 — D1 전체 이력 LIKE 8패턴 + 최근 14일 150 rows 정규식 + 아웃라인 745 files 모두 0건. 재현: 위 1.1 표의 SELECT/LIKE 명령 그대로 실행.
- [검증됨] 정상 영어(제품명/매체명/컨퍼런스명)만 73개 아웃라인 파일에서 검출 — 예: `MIT Tech Review`, `GitHub Copilot CLI`, `IEEE International Conference on Robotics and Automation`, `The Next Web` (출처 표기/고유명사 = 릭 아님). 근거: 73건 전수 육안 분류, 영어 문장 형태(기능어 3개+한글 부재) 재스캔 시 0건.
- [부분검증] 반복 루프 릭 1건 (위 표) — tier 상관은 로그 content 스니펫 부재로 시각적 추정.
- [검증불가] "한국어 출력에 영어가 섞이는" 원형 릭의 라이브 샘플 특정 — 본 진단 시점 스캔 범위에서는 발견되지 않음. 유저가 목격한 릭이 과거 데이터(스캔 범위 외 날짜)이거나, 현재 라이브가 아닌 다른 경로(아웃라인→블로그 초안 변환 단계 등)에서 발생했을 가능성. 복구 계획: 후속 quick task에서 릭 목격 사례의 구체 URL/날짜를 입력받아 해당 row만 재스캔.

