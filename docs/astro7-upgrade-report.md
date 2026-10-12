# AIK24-ASTRO-UPGRADE-01 — Astro 5→7 업그레이드 타당성 조사 보고서

- 조사일: 2026-10-11 18:41 ~ 18:50
- 프로젝트: `/Users/twinssn/Projects/aikorea24`
- 성격: **조사 전용** — main 커밋 없음, 배포 없음
- 브랜치: `test/astro7-chunked` 생성 → 실측 후 **삭제 완료**, `npm install` 복원, Astro 5.17.2 정상 빌드 재확인

---

## 최종 판정: 조건부 권장 — **지금 업그레이드는 불가**

| 질문 | 판정 |
|---|---|
| `chunked`가 24MB 문제를 해결하는가? | ✅ **해결한다** (실측 확인) |
| 지금 업그레이드할 수 있는가? | ❌ **불가** — 블로커 2건 |

핵심은 "기술적으로 해결 가능하다"와 "지금 당장 할 수 있다"가 다르다는 점입니다. 해결 수단은 실측으로 확인했으나, 착수 전에 막아야 할 블로커 2건이 있습니다.

---

## ① 현재 vs 목표 버전

| 패키지 | 현재 | Astro 7 목표 | 비고 |
|---|---|---|---|
| astro | 5.17.2 (`^5.17.1`) | **7.3.8** | |
| @astrojs/cloudflare | 12.6.12 | **14.3.4** | peer `astro ^7.2.0` |
| @astrojs/mdx | 4.3.13 | **8.0.3** | peer `astro ^7.2.10` |
| @astrojs/tailwind | 6.0.2 | **대체 없음** | 🚨 peer `astro ^3\|\|^4\|\|^5`, 릴리스 최종 |
| tailwindcss | 3.4.19 | **4.3.3** | v4 이관 필요 |
| Node | v25.2.1 | `>=22.12.0` | ✅ 충족 |

기준 브랜치는 지시서 가정과 다르게 `main`이 아니라 **`agent/phase40-compass-diversification`** 입니다.

---

## ② breaking changes 항목별 판정

| 항목 | 판정 | 근거 |
|---|---|---|
| Astro 6 legacy collections 제거 | **영향 없음** | 이미 Content Layer 사용(`loader: glob`, 최상위 `src/content.config.ts`). astro@7.3.8 `dist/content/loaders/index.js:2`에서 `glob` export 확인. `legacy.collectionsBackwardsCompat` 기본 false이나 해당하지 않음 |
| Vite 8 | 영향 없음 추정 | Vite 내부 API 의존 플러그인 없음 |
| Rust 컴파일러 기본·유일 | **영향 있음(소)** | `ToolForm.astro` 212·221행 — 표현식 내부 HTML 주석이 거부됨 |
| experimental 플래그 제거 | 영향 없음 | config에 미사용 |
| `src/fetch.ts` 예약화 | 영향 없음 | 해당 파일 없음 |
| `compressHTML` 기본 `'jsx'` | 확인 필요 | 출력이itespace 변화 가능 |
| `markdown.processor` 통합 | **영향 있음** | deprecated 경고 발생. 아래 ④ 참조 |
| `@astrojs/db` 제거 | 영향 없음 | 미사용 |
| `astro:transitions` 내부 제거 | 영향 없음 | `ClientRouter`/`ViewTransitions` 미사용 |
| zod 3→4 | 확인 필요 | astro 7이 zod `^4.6.5` 번들. `astro:content`의 `z` re-export도 deprecated |

---

## ③ collectionStorage chunked 동작 범위 — **배포 산출물까지** 분할

공식 문서에는 `collectionStorage`/`chunked` 언급이 없어 문헌만으로 확정할 수 없었습니다. **astro@7.3.8 tarball을 내려받아 소스를 직접 읽고 확정**했습니다.

- `dist/types/public/config.d.ts:3350-3387` — `@version 7.1.0`, `@default 'single-file'`, 타입 `'single-file' | 'chunked' | {type:'chunked', chunkSize:number}`
- `dist/content/vite-plugin-content-virtual-mod.js:247-262` — chunked 시 각 part를 `(await import("astro:data-layer-content-chunk:<hash>.txt"))` 형태로 lazy import하는 코드 생성. 원문 주석: *"Emit each part as a lazy virtual import so the parts stay separate chunks instead of being inlined into one huge module (**the very thing chunking avoids**)."*
- 미청크 경로는 `export default JSON.parse("<전체 JSON>")` 인라인 — 현재 24MB 단일 청크의 원인

**결론: 분할은 `.astro/data-store.json`만이 아니라 배포 산출물의 청크까지 적용됩니다.**

---

## ④ Phase 2 실측 수치

| 항목 | BASELINE (Astro 5.17.2) | Astro 7.3.8 + chunked | 변화 |
|---|---|---|---|
| data-layer 파일 수 | 1개 | **28개** | 1 → 28 |
| **최대 파일 크기** | 24,106,348 B | **1,101,232 B** | **-95.4%** |
| 25MiB 한도 대비 | **91.96%** | **4.20%** | 위험 해소 |
| data-layer 총 크기 | 24,106,348 B | 25,436,540 B | +5.5% |
| 20MB 초과 파일 | 1개 | **0개** | |
| 5MB 초과 파일 | 1개 | **0개** | |
| 전체 산출물 | 4,782 파일 / 325 MB | 2,483 파일 / 252 MB* | *prerender 중단분 포함 |

파일 수 감소는 Astro 7이 `dist/client` + `dist/server`로 분리하고 prerender가 중단되었기 때문이며, 정상 완료 시에는 4,782 이상입니다.

**블로커 때문에 빌드가 완주하지 못했으므로(아래), 실측값은 "청크 분할 자체"에 대해 유효하지만 "완전한 빌드 산출물"에 대해서는 유효하지 않습니다.**

---

## ⑤ 블로커 2건

### 블로커 1 — `@astrojs/tailwind`가 Astro 7 미지원 (선행 이관 필수)

peer가 `astro ^3.0.0 || ^4.0.0 || ^5.0.0`이고 2025-03-26 이후 릴리스가 없습니다. 전체 버전 이력을 확인했으나 Astro 6/7 대응 버전이 존재하지 않습니다. `deprecated` 표시는 없으나 사실상 미유지입니다.

대안은 Tailwind v3→v4 이관입니다. 실제 마이그레이션 범위는:
- `@astrojs/tailwind` 제거 → `@tailwindcss/vite` plugin
- `@tailwind base/components/utilities` → `@import "tailwindcss"`
- `darkMode:'class'` → CSS `@custom-variant`
- typography plugin → `@plugin`, `tailwind.config.mjs` → CSS `@theme`

**우리 규모는 소~중입니다**: `@apply` 사용처 **0건**, `global.css` 단일 파일, 유틸리티 클래스 사용 .astro 46개.

### 블로커 2 — 빌드/배포 차단: `ASSETS` 바인딩 충돌

`@astrojs/cloudflare` 14.3.4 + `@cloudflare/vite-plugin` 1.63.1이 Pages 프로젝트용 `assets.binding: "ASSETS"`를 생성하는데, **동일 플러그인이 이를 거부**합니다.

```
The name 'ASSETS' is reserved in Pages projects.
Please use a different name for your Assets binding.
  at node_modules/@cloudflare/vite-plugin/dist/index.mjs:48549
```

prerender 단계에서 중단되어 blog HTML이 **1,796개 중 4개만** 생성됐습니다.
wrangler **4.149.0(최신)** 과 **4.125.0(peer 하한)** 양쪽 모두 동일 실패 → 버전 핀이 아닌 업스트림 버그입니다. (`@astrojs/cloudflare` peer는 `wrangler ^4.125.0`.)

---

## ⑥ 예상 작업량 및 주의사항

**작업량: 중** (차단 해소가 별도 작업이므로 대가 될 수 있음)

| 순서 | 작업 | 규모 |
|---|---|---|
| 1 | Tailwind v3→v4 이관 | 소~중 |
| 2 | `ASSETS` 충돌 해결 (업스트림 버그 회기 대기 또는 Pages→Workers 검토) | **불명 — 외부 의존** |
| 3 | astro/cloudflare/mdx 버전 올리기 | 소 |
| 4 | `ToolForm.astro` 표현식 내부 주석 2건 제거 | 소 |
| 5 | `remark-gfm`, `@astrojs/markdown-remark` 명시 설치 | 소 |
| 6 | **`deploy.sh` 경로 갱신** | 소 |

### ⚠️ 가장 중요한 주의사항 — `deploy.sh` 경로 파괴

Astro 7 + cloudflare 14는 산출물 레이아웃이 `dist/_worker.js/` → **`dist/server/` + `dist/client/`**로 바뀝니다.

`scripts/deploy.sh`의 `[1.5/3]`은 `rm -f dist/_worker.js/chunks/_astro_data-layer-content_*.mjs`, `[1.6/3]` fail-safe도 동일 경로를 검사합니다. **경로가 바뀌면 `rm`은 조용히 성공(경로 부재)하고 `[1.6/3]` 검증은 항상 통과**하게 되어, 방금 만든 fail-safe가 무의미해집니다. 업그레이드 시 두 경로를 `dist/server/chunks/`로 갱신해야 합니다.

### 마크다운 렌더링 관련

`markdown.remarkPlugins`/`gfm`은 Astro 7.3.8 스키마에 **남아 있으나 deprecated**이며, 동작하려면 `@astrojs/markdown-remark` 명시 설치가 필요합니다(에러 메시지가 안내). 이번 조사에서는 **1,470개 포스트의 렌더링을 바꾸지 않기 위해 구형 문법을 의도적으로 유지**했습니다. 향후 메이저에서 제거되므로 재작업 여지가 있습니다.

---

## 잔존 위험

- `@astrojs/tailwind` 대체 미이관 — 업그레이드 선행 필수
- `ASSETS` 충돌의 근본 해결책 미확정 — **업스트림 버그이므로 버전 대기 또는 아키텍처 검토가 필요**
- 업그레이드 후 전 페이지 시각 회귀 검증 미수행(이번에는 빌드 중단으로 미완료)
- 조사라서 커밋·배포 없음. `docs/state.md`·`scripts/deploy.sh` 미커밋 상태는 DATALAYER-01/02와 동일 잔여

조사 완료 — 시니어 2 verify 요청
