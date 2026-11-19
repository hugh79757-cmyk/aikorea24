## 2026-11-19 17:26 — AIK24-TOOLDUP-NOTICE-02 완료 — 승인 버튼에 경고 창(모달) 추가

### 한 일
1. `src/pages/admin/tools.astro`
   - 승인 버튼은 **항상** 경고 창(모달)을 거친다. 카드의 승인 버튼은 `openApproveModal()` 만 호출하고, `POST /api/admin/tools/review` 는 모달의 `승인 → 공개` 버튼에서만 나간다(코드 경로 단일화: `runReview(..., 'approve', ...)` 호출 지점 1곳 = 모달 핸들러).
   - 모달 내용: 도구 이름·슬러그·URL, 등급별 박스(exact 빨강 "⚠️ 이미 중복입니다" / likely 주황 "⚠️ 중복 의심" / clean 초록 "✓ 기존 목록과 중복 없음"), 근거 문구, 매칭 항목 이름·슬러그·(목록|승인됨)·`보기 →` 최대 3건, 안내문.
   - exact 등급은 **체크박스("이미 목록에 있는 도구임을 확인했습니다")** 를 체크해야 승인 버튼이 열린다. likely·clean 은 바로 승인 가능.
   - 취소: `취소` 버튼 / 배경 클릭 / `Esc`.
   - 기존 `window.confirm` 경로는 제거했다(중복 배지가 없으면 확인 없이 바로 승인되던 구멍).
   - 반려·공개 취소 흐름은 동작 변경 없이 `runReview()` 로 통합(메시지·비활성화·에러 처리 동일).
   - XSS 방지: 제출물에서 온 이름·슬러그·사유는 `textContent` 로만 삽입(innerHTML 미사용).
2. `src/lib/tool-duplicates.ts` — `describeApproveWarning()` 추가(등급 → 제목·안내문). 화면과 테스트가 같은 문구를 쓴다.
3. `tests/js/tool_duplicates.test.ts` — 승인창 문구 3케이스 추가(clean/exact/likely). 총 15케이스.

### 결과 (검증 근거)
- [검증됨] **단위 테스트**: `npm run test:js` → `pass 15 / fail 0`. 15 = 기존 12(중복 5쌍 재현 + 별개 제품 침묵 + 수집원/자기제외/정렬/dedupe) + 승인창 문구 3.
- [검증됨] **빌드**: `npm run build` 성공. 서버 청크 `dist/server/chunks/tools_BcRVP95r.mjs` 에 `approve-modal`, `approve-modal-ack-wrap`, `data-dups`, "승인 확인 — 공개로 전환" 존재. 클라이언트 번들 `dist/client/_astro/tools.astro_astro_type_script_index_0_lang.xj9D2u6Q.js` 에 "이미 중복입니다"·"기존 목록과 중복 없음" 존재.
- [검증됨] **배포**: `bash scripts/deploy.sh` 성공, Worker Version `b4b596eb-9e35-4b06-8fad-69417b676240`. 라이브 `/_astro/tools.astro_astro_type_script_index_0_lang.xj9D2u6Q.js` 200 + 문구 포함(grep 1).
- [검증됨] **기존 페이지 무영향**: `/` 200, `/tools/` 200, `/admin/tools/` 401(변경 전과 동일한 비관리자 응답).
- [검증됨] **승인 경로 단일화(정적 확인)**: `grep -n "runReview(|openApproveModal(|modalOk.addEventListener"` → `runReview(..., 'approve', ...)` 는 404행(모달 핸들러) 1곳뿐이고, 카드 승인 버튼(464행)은 `openApproveModal()` 만 호출한다.
- [부분검증] **실제 클릭 흐름**: 관리자 세션이 없어(비관리자 401) 브라우저에서 `승인 → 창 열림 → 체크/확인 → published 반영`을 실행해 보지 못했다. 제한 사유 — 관리자 인증 필요. 확인된 것은 빌드 산출물·라이브 번들 문자열·코드 경로까지다.
- [부분검증] **`data-dups` 속성 전달**: Astro 가 `JSON.stringify` 결과를 속성으로 이스케이프하고 브라우저가 디코드하는 표준 경로이지만, 실제 렌더된 DOM 에서 `JSON.parse` 가 성공하는지는 위와 같은 이유로 미확인. 실패하면 `parseDups()` 가 빈 배열을 반환해 "중복 없음" 박스가 뜬다(창은 정상 동작, 노티스만 약해짐).

### 잔존 위험
1. **서버측 차단 없음** — 체크박스·경고는 클라이언트 강제다. 개발자도구로 우회하거나 JS 를 끄면 그대로 승인된다. `POST /api/admin/tools/review` 는 여전히 중복 여부를 모른다.
2. exact 판정은 휴리스틱이라 오탐/미탐이 있다(예: `IFTTT.ai` ↔ `New AI tools by IFTTT` 는 미탐). 오탐이면 체크박스 한 번 더 누르면 되고, 미탐이면 경고 없이 승인된다.
3. `data-dups` 에는 최대 3건만 실린다(그 외 매칭은 화면에도 표시하지 않음).
4. 제출 화면(`/my/tools`, `POST /api/tools/submit`)에는 사전 경고가 없다.
5. 모달은 이 페이지 전용 마크업·CSS 다(공용 컴포넌트 아님).

### 다음 행동
1. 대표님 세션에서 `/admin/tools/` 열어 승인 버튼 1회 클릭 → 창·체크박스·문구 확인.
2. 원하시면 승인 API 에 서버측 차단(`acknowledge` 없으면 409) 추가.
3. 수집기(`scripts/tools_collector.py`) 등록 단계에 같은 판정 적용.
