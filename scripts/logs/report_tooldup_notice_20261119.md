## 2026-11-19 17:22 — AIK24-TOOLDUP-NOTICE-01 완료 — admin/tools 중복 노티스 + 판정기

### 한 일
1. 신규 `src/lib/tool-duplicates.ts` — 중복 판정기. 규칙 6개(우선순위 순): ① 슬러그 동일 ② 정규화 이름 동일 ③ 접미(AI·App 등)만 다른 이름 동일 ④ 도메인 동일(수집원·플랫폼 도메인 제외) ⑤ 이름 포함 관계 + 변형어(OSS·Plus·Beta·CLI…) ⑥ 이름 토큰 Jaccard ≥ 0.8. 침묵 규칙: 숫자만 다른 버전(Sonnet 5 / 5.5), 브랜드 단어가 이름 중간에만 있는 경우, `topai.tools`·`theresanaiforthat.com` 같은 디렉터리 도메인.
2. 신규 `tests/js/tool_duplicates.test.ts` 12케이스 — 2026-11-19에 실제로 지운 중복 5쌍을 재현하고, 별개 제품(ChatGPT Work·Copilot Fusion·Sonnet 5.5·Claude Duet·Kai Resolve·Mermaid Flow)은 침묵하는지 검증. `package.json` 에 `test:js` 스크립트 추가.
3. `src/pages/admin/tools.astro` — 검토 큐 pending 카드마다 판정 결과를 렌더: exact = **"이미 중복입니다"**(빨강), likely = **"중복 의심"**(주황), 매칭 항목 이름·슬러그·근거·`보기 →` 링크 최대 3건, 중복이 없으면 `✓ 기존 목록과 중복 없음`. 헤더에 `⚠️ 중복 의심 N` pill 추가. 승인 버튼은 배지가 있으면 확인 대화상자를 띄운다. 공개 목록 카드에도 같은 배지를 붙였다.

### 결과 (검증 근거)
- [검증됨] **판정기 단위 테스트**: `npm run test:js` → `pass 12 / fail 0`. 12 = 실제 중복 5쌍(①oMLX ②freebeat ③Edgee ④Make0 ⑤슬러그 충돌) + 침묵 5종(ChatGPT Work·Copilot Fusion·Claude Sonnet 5.5·Kai Resolve·Mermaid Flow) + 수집원 도메인·자기 자신 제외·정렬·dedupeIndex 2건.
- [검증됨] **실제 데이터 오탐 0**: md 564건 + 공개 submission 38건으로 인덱스를 만들고, 공개 38건을 전수 판정 → exact 0 / likely 0 / 침묵 38. 근거 — `/tmp` 로 뽑은 실제 name·url 로 `findDuplicates(excludeSameSlug:true)` 실행 결과 출력.
- [검증됨] **빌드·배포**: `npm run build` 성공, `bash scripts/deploy.sh` 성공(Worker Version `b74d7042-1dd9-452c-a42d-5dba853330b2`). 빌드 산출물 `dist/server/chunks/tools_pr25puRI.mjs` 에 "이미 중복입니다"·"기존 목록과 중복 없음" 문자열 포함 확인.
- [검증됨] **기존 페이지 무영향**: `/` 200 · `/tools/` 200 · `/admin/tools/` 401(변경 전과 동일한 비관리자 응답).
- [부분검증] **화면 렌더**: `/admin/tools/` 는 관리자 세션 없이 401 이라 pending 카드에 배지가 실제로 그려지는 것을 내가 확인하지 못했다. 제한 사유 — 관리자 인증 필요. 코드상 인덱스 구성 실패는 `try/catch` fail-soft 로 처리해 노티스만 사라지고 큐는 뜬다. 대표님 세션에서 1회 확인 필요(현재 pending 0건이라 pill 만 보인다).

### 정정
- [정정] 17:05 항목의 "라이브 564 = md 563 + D1 전용 1" 은 **틀렸다**. 그 배포의 `sync_submissions_to_md.mjs` 가 `makeasong.md` 와 `youtranscripts.md` 두 개를 만들었고, 실제 구성은 **md 564 + D1 전용 0 = 564** 다. 총계(564)는 맞고 구성비 설명이 틀렸다. SSOT 보고서(`2026-11-19-1705-AIK24-TOOLDEDUP-01-완료보고.md`)도 같은 문장을 정정했다.

### 잔존 위험
1. **판정기는 휴리스틱이다.** 오늘 지운 5쌍 중 `IFTTT.ai` ↔ `New AI tools by IFTTT` 는 잡지 못한다(브랜드 단어가 이름 중간에만 있는 경우). 오탐을 줄이려고 의도적으로 뺀 규칙이며, 필요하면 '참고' 별도 섹션으로 추가할 수 있다.
2. **승인 API 는 막지 않는다.** 노티스와 확인 대화상자는 클라이언트 경고일 뿐이고, 서버측 차단(acknowledge 필수)은 넣지 않았다.
3. **인덱스 범위**: md 컬렉션 + `tool_submissions`(published) 만 본다. legacy `tools` 테이블(656행, md 없는 94행 포함)은 대상이 아니므로 그쪽에만 있는 중복은 노티스가 뜨지 않는다.
4. **제출 단계 경고 없음**: `POST /api/tools/submit` 과 `/my/tools` 화면에는 사전 경고가 없어 제출자는 중복인지 알 수 없다.
5. **비용**: admin 페이지가 요청마다 `getCollection('tools')`(564건)을 읽는다. 관리자 전용·저빈도라 수용했으나, 대기 건이 많아지면 캐싱이 필요하다.

### 다음 행동
1. 대표님 세션에서 `/admin/tools/` 1회 확인(배지·pill·승인 확인창).
2. 원하시면 승인 API 에 서버측 차단(중복 acknowledge 없으면 409) 추가.
3. `scripts/tools_collector.py` 수집 단계에 같은 판정을 넣으면 중복 등록 자체를 막을 수 있다(지금은 화면 노티스만).
