## 2026-10-20 19:30 — AIK24-PIPE-07 후속: 내일 자동 실행 경로 검증 + 렌더 계약 회귀 테스트

**질문**: 내일(2026-10-21) 자동 파이프라인에서도 "기사 원문 읽기"와 "이 기사 더 깊게 읽기"
버튼의 목적지가 모두 올바르게 설정되는가?

### 확인한 실행 경로 (내일과 동일한 스케줄)
- 05:30 로컬 `kr.aikorea24.news-unified` → `api_test/news_collector.py`
  → 서브프로세스 `scripts/news_collector_v2.py --models-only` (api_test/news_collector.py:1252).
  오늘 로그: 192건 수집 / 4건 신규 저장 (api_test/cron_unified.log:48453-48470).
- 07:00 로컬 `kr.aikorea24.pipeline-runner` → 브리핑 생성 → 배포. 렌더는 D1 읽기.
- 07:30 / 20:15 로컬 `kr.aikorea24.blog-draft` → EmDash 발행 후
  `briefing_items.deep_dive_url` 연결 (blog_draft_generator.py:202-215).
  로그 타임스탬프는 KST 이므로 09:30/22:15 = 로컬 07:30/20:15 (blog_draft_generator.py:94 `datetime.now(KST)`).

### 한 일
1. 프로덕션 인터프리터로 수집 경로 재현:
   `.venv/bin/python3 scripts/news_collector_v2.py --models-only --dry-run`
   → 192건, 제공사 4종 전부, `origin_link` 누락 0.
2. 오늘 05:30 이후 생성된 무료 모델 행 3건(56528~56530) `origin_link` 채움 확인.
3. `tests/test_origin_link_render_contract.py` 신설 (3건) — 표시 경로가
   `COALESCE(n.blog_link, n.link)` 로 되돌아가면 실패, 원문/심층이 서로 다른 필드임을 고정.
4. 오늘 07:30 블로그 발행 로그 확인 — 신규 글 2건 모두 게이트에서 보류된 사실 확인.

### 결과
- [검증됨] 내일 신규 무료 모델 행은 `origin_link` 를 갖고 INSERT 된다.
  근거: `.venv` dry-run 192/192 누락 0 + `save()` 단위 테스트 2건(URL 기록/비무료 NULL)
  + D1 `news` 15컬럼 + 실제 INSERT 경로가 v2 `save()` 임을 로그로 확인.
- [검증됨] 표시 5곳이 `blog_link` 로 폴백하지 않는다.
  근거: 신규 계약 테스트 3건 통과 + 라이브 브리핑 카드 실측
  (원문 `https://opencode.ai/v2/docs/console/models/`, 심층 emdash 글 — 서로 다름).
- [검증됨] 테스트 899 passed / 10 skipped / 0 failed.
  산출: 896(기존: 863 + PIPE-07 30 + 수집기 2 + 카탈로그 1) + 3(계약 테스트) = 899.
- [부분검증] 심층 버튼은 "발행 완료된 글"이 있을 때만 렌더된다. 오늘 07:30 실행에서
  (a) 미니맥스 신규 글은 썸네일 placeholder 사본으로 배포 차단, (b) 레플리카 글은
  1차 게이트 미달로 발행 보류 → 신규 2건 모두 `deep_dive_url` 미연결.
  제한 사유: 발행 게이트(본문·썸네일)는 외부 이미지 API·LLM 품질에 의존해 결정적이지 않다.
- [정정] 이전 보고에서 "이메일 원문 링크"라고 적은 부분은 과장이다.
  `scripts/auto_email_sender.py` / `src/pages/api/briefing/send-email.ts` 는
  `news_link` 를 SELECT 하지만 템플릿은 브리핑 페이지로만 링크하고 원문 버튼을 렌더하지 않는다.
  SQL 변경은 방어적 변경이며 화면 효과는 없다.

### 잔존 위험
- 신규 기사의 심층 버튼 유무는 블로그 발행 게이트 통과 여부에 달려 있다(오늘 실측 0/2 발행).
  잘못된 목적지로 가는 것은 아니고 버튼이 없는 상태다.
- Kilo 단종 모델의 per-model 페이지 404 가능성 → 목록 페이지로 다운그레이드(백필 시 20건).
- 07:00 배포 시점에는 `deep_dive_url` 이 아직 NULL 일 수 있다. 07:30 발행 후 SSR 로 즉시 반영된다
  (재배포 불필요).

### 다음 행동
1. 내일 05:30 이후: `SELECT id, source, origin_link FROM news WHERE created_at >= '2026-10-21'`
   로 신규 행 `origin_link` NULL 0건 확인.
2. 내일 07:30 이후: `SELECT news_id, deep_dive_url FROM briefing_items WHERE briefing_id=<내일 id>`
   로 심층 링크 연결 여부 확인.
3. 심층 버튼 누락이 반복되면 별도 작업으로 썸네일/본문 게이트 실패율을 다룬다(PIPE-08 후보).
