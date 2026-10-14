## 2026-10-14 13:45 AIK24-RENEWAL-01 B그룹(디자인 7건)현황 감사 — B-1/B-2 이미 적용됨 확인, 잔여 1건 + 스펙 확인 대기

### 한 일
- 지시(원문): "10-11 백로그(B디자인·C버그·D프롬프트·E이관) … 다해줘 / 마무리 하자."
- [PRODUCTION CODE] **없음.** 감사만. 이유 하단.

### 결과 — B그룹 7건 실측
| 항목 | 상태 | 근거 |
|---|---|---|
| B-1 7일강의 배경(검정→흰/검정텍스트) | **[완료]** | `courses/7day-starter.astro:25` `class="bg-white text-[#111111] min-h-screen"`. 검정 배경 아님. |
| B-2 초록/핑크 제거(전제 "25개 파일") | **[사실과 불일치 — 잔여 1건]** | `global.css` 토큰은 이미 흑백+빨강(`--bg-primary:#ffffff`, `--text-primary:#111111`, `--accent-red:#E63B2E`). `grep -rniE "green\|pink" src/` → 웹 UI 에 **2건만**. Tailwind 초록/핑크 21건은 전부 `src/auto_poster/`(Threads 카드, 웹 아님). |
| B-3 타임라인 통일 | **[감사 불가]** | 대상 4파일(`tools/finder`, `compare`, `chronicle/[...id]`) 확인. "통일" 기준이 스펙에 없어 판정 불가. |
| B-4 푸터 통일 | **[감사 불가]** | `src/components/` 에 Footer 컴포넌트 없음 — `layouts/Layout.astro` 인라인. 비교 대상 부재. |
| B-5 EmDash 헤더/푸터 | **[감사 불가]** | EmDash CMS 소스(`~/projects2/aikorea24emdash`) 대상. aikorea24 사이트와 디자인 기준 공유 여부 불명. |
| B-6 블로그 타이포(글자크기·대칭·표→단락·여백) | **[대상 이동]** | Astro 블로그 소스 삭제 완료(EMDASH-04) → 대상이 `~/projects2/aikorea24emdash/src/pages/posts/[slug].astro` 로 옮겨감. |
| B-7 마스코트 배치 | **[감사 불가]** | `mascot` 참조 5파일(`home/HeroSection`, `home/ToolsSection`, `404`, `global`, `unsubscribe`). "배치" 기준 미정의. |

- [검증됨] B-2 잔존 2곳: `src/pages/chronicle/index.astro:17` `color: "green"` — **죽은 필드**(91행에서 `.emoji` 만 사용, `.color` 미사용) / `:37` `border-l-green-500` — `borderColorClass()` 에서 실제 사용됨.
- [검증됨] E그룹(블로그 이관)은 EMDASH-01~05 로 완료. D그룹도 D-1/D-2/D-3 완료. C그룹 5건 완료.

### 잔존 위험
1. **B그룹 잔여 5건(B-3/B-4/B-5/B-6/B-7)을 임의 스펙으로 수정하지 않음** — RENEWAL-01 의 서술은 "통일/대칭/여백" 처럼 정량 기준이 없어 재작업하면 대표님 의도와 어긋날 수 있음.
2. chronicle 의 5개 카테고리는 blue/green/red/purple/amber 색 구분|border-left)이라 "green 만 제거" 하면 5색 중 1개만 빠진 비대칭 상태가 됨.
3. `border-l-green-500` 는 실제 렌더에 영향. 미수정 상태.

### 다음 행동
- 대표님: (a) chronicle 초록 border 색 결정(검정/회색/유지) (b) B-3~B-7 정량 스펙(또는 대상 화면 스크린샷) 제공 시 그 기준으로 재작업.
