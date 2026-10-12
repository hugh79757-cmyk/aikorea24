# AIK24-THUMB-BACKFILL-01 결과 보고

- 작업일: 2026-10-11
- 지시서: `2026-10-11-1718-AIK24-THUMB-BACKFILL-01.md`
- 대상 DB: Cloudflare D1 `aikorea24-emdash-db` (`bbbcbc34-f346-49e0-9aab-058836bee16d`) 테이블 `ec_posts`
- 라이브: https://emdash.aikorea24.kr/posts/

## 1. 지시서 전제 vs 실측

| 항목 | 지시서 전제 | 실측 (D1 ground truth) |
|---|---|---|
| 대상 건수 | ec_posts 전체 약 1,460건 | `featured_image IS NULL` **48건** (전체 1,471건 중) |
| 원인 | Astro→EmDash 마이그레이션 시 필드 미이전 | 필드 이관은 정상 동작 (1,423/1,471 = 96.7% 존재). **2026-10-10 단일 배치 48건만 누락** |
| 누락 시각 분포 | — | 48건 전부 `created_at = 2026-10-10` |
| 상태 | — | 48건 전부 `status = published` |

지시서의 "약 1,460건"은 필드 존재 여부가 아니라 "썸네일이 안 보인다"는 관찰에서 나온 추정치였고, 실제 미설정 행은 48건이다. 대표님 확인 후 **48건만** 백필.

## 2. 처리 방식 (대표님 확정, 3개 질문 답변)

1. **48건만 백필** — 지시서의 1,460건으로 확대하지 않음.
2. **기존 URL 재사용** — 신규 EmDash R2 업로드 없음. 이미 1,423건이 쓰던 형태 그대로
   `{"provider":"external","id":"","src":"https://aikorea24.kr/images/<slug>/thumbnail.webp"}` 로만 설정.
   근거: `scripts/emdash10_images.py` 가 이미 이 형태를 표준화해 두었고, 1,423건이 실측으로 정상 동작 중.
3. **Pexels 검색으로 생성** — 로컬 대응 이미지가 없는 12건만 (지시서 §4.2 우선순위 2).

## 3. 처리 결과

| 구분 | 건수 | 방법 |
|---|---|---|
| 기존 Astro 썸네일 재사용 | 36 | `public/images/<astro-slug>/thumbnail.webp` 절대 URL 재사용 |
| Pexels 신규 생성 | 12 | `auto_thumbnail.process_thumbnail()` 재사용 → `public/images/<emdash-slug>/thumbnail.webp` |
| **합계** | **48** | |

슬러그 매칭 규칙: Astro 슬러그는 `YYYY-MM-DD-NNN-제목`, EmDash 슬러그는 `제목`. `emdash12_thumb_backfill.py::norm()` 이 날짜 접두사를 제거 + NFC 정규화 + 영숫자/한글만 남긴 키로 비교.

## 4. 신규 생성 12건 처리 과정 (중요)

`auto_thumbnail.process_thumbnail()` 로 12건 생성 → **4건이 공용 placeholder(`public/images/news-keyword-og.webp` 사본)로 폴백.**

원인: `auto_thumbnail` 이 Pexels `src.large`(1200px)를 쓰는데, 일부 사진은 800×800 WebP 변환 후
`validate_thumbnail_quality(min_size_kb=15)` 게이트(15KB)를 통과하지 못한다.

조치: `scripts/emdash12_thumb_retry.py` 로 4건만 재시도. 같은 검색 결과의 `src.large2x`(2배 해상도)를
사용해 게이트를 통과시킴.

- 재시도 1차: 4건 성공했지만 **4건 모두 동일 이미지(id=12696432)** — `emdash12_thumb_retry.py` 가
  `_save_used_id()` 로 파일만 쓰고 메모리 `used` 집합을 갱신하지 않아 중복 발생.
- 버그 수정: `used.add(p["id"])` 추가.
- 재시도 2차: 4건 모두 **서로 다른 이미지**로 확정 (id 12696432 / 12939552 / 25630341 / 12627677).

최종 검증 — 12건 전부: 800×800 WEBP, 파일 크기 15KB 이상, placeholder 0건, md5 중복 0건.

| # | slug (앞 30자) | 크기 |
|---|---|---|
| 1 | 정체-공개-huggingface-trending-1… | 134,366B |
| 2 | 벤치마크-비교-무료-inkling-small-vs… | 49,710B |
| 3 | 오늘의-추천-llm-inkling-small-입출력… | 71,674B |
| 4 | 이번-주-무료-llm-순위-top-5와-이번-주… | 30,074B |
| 5 | 스탠퍼드-ai-보고서-2026-전문가-낙관… | 33,988B |
| 6 | openai의-새로운-ai-키패드-사용-후기… | 53,468B |
| 7 | 삼성-브로드컴-2000억-달러-규모-칩-계약… | 71,586B |
| 8 | 코그니션의-포크-인수-ai-개성이-경쟁-우위… | 181,250B |
| 9 | 제미니-메모리-개선과-스마트-홈-업데이트… | 17,476B |
| 10 | 알파폴드-ai가-유전자-편집-단백질을… | 24,014B |
| 11 | 오푸스-5-브라우저-기반-프롬프트-인젝션… | 52,014B |
| 12 | 오픈ai의-또-다른-안전-관련-퇴사-공개… | 80,810B |

## 5. 검증

### D1
```
SELECT COUNT(*) total, SUM(featured_image IS NULL) nulls, SUM(featured_image IS NOT NULL) has FROM ec_posts
→ {'total': 1471, 'nulls': 0, 'has': 1471}
```
`featured_image` JSON 형식도 기존 1,423건과 동일 (`provider=external`, `id=""`).

### 이미지 파일 (로컬)
12건 전부 800×800 WEBP / ≥15KB / placeholder 0 / md5 중복 0.

### 이미지 (라이브 https://aikorea24.kr)
신규 12건 **12/12 HTTP 200**.

### 배포
`npm run build` OK → `npm run deploy` OK → sitemap ping `{"google": true, "naver": true}`.
(신규 12개 이미지가 카드에서 보이려면 aikorea24.kr 배포가 선행되어야 해서 백필 D1 반영보다 먼저 수행.)

### 라이브 목록 페이지 (https://emdash.aikorea24.kr/posts/)
- 카드 60개 중 **이미지 있는 카드 60개 / 없는 카드 0개** (작업 전 11개 누락).
- 카드 이미지의 src **60/60 실 GET 200**.
- 백필본과 기존본 응답 동일 확인: `Content-Type: image/webp`, 실제 바이트 수 일치 형태.

## 6. 산출물

| 파일 | 설명 |
|---|---|
| `docs/thumbnail-backfill-list.csv` | 48건 전체 목록 (slug, status, created_at, source, thumbnail_url, http_200) |
| `docs/thumbnail-backfill-result.md` | 본 문서 |
| `scripts/emdash12_thumb_backfill.py` | 조사(dry) + 반영(`--apply`) 1벌. `need_gen` 잔존 시 apply 차단 |
| `scripts/emdash12_thumb_gen.py` | Pexels 신규 생성 12건 (house `process_thumbnail` 재사용) |
| `scripts/emdash12_thumb_retry.py` | placeholder 폴백 건 `src.large2x` 재시도 |

## 7. 잔존 위험 (후속 작업으로 갱신, 2026-10-11 18:0x)

초기 보고 시 5건이resid로 남아 있었으나, 후속 작업에서 ①③④ 을 처리했고 ②는 대표님 판단 대기 중이다.

1. ~~`weekly_blog_publisher.py` 의 `_publish_to_emdash` 미확인~~ → **해소 (삭제 완료)**
   `EMDASH_PUBLISH` 가 어디에서도 설정되지 않음을 확인 (`.env`, `~/.env.common`, `~/Library/LaunchAgents/*.plist` 전부 부재). 도달 가능한 스케줄러 `kr.aikorea24.weekly-contrast.plist` 의 `EnvironmentVariables` 에는 `OPENAI_API_KEY`/`PATH`/`WEEKLY_CONTRAST_ENABLED` 만 있어 게이트가 항상 조기 반환한다. 도큐스트링이 주장하던 "`/blog/*` → emdash 리다이렉트" 전제도 앞선 작업에서 철회된 상태였다. 호출부(130행) + 함수 전체(134–199행) + 미사용 상수 `EMDASH_ORIGIN`(26행)/`IMG_ORIGIN`(27행) 삭제. 회귀 검증: `pytest tests/test_weekly_blog_publisher.py -q` **수정 전 12 passed / 수정 후 12 passed**.
2. **기존 EmDash 중복 데이터 — 조사 완료, 대표님 판단 대기** (조치 안 함)
   정정: **EmDash 내부 중복은 없다.** `ec_posts` 1,471행 = 고유 슬러그 1,471개, 정규화 키 충돌 0건. Astro `src/content/blog` 는 1,470개로 사실상 1:1 미러(차이 1행). 즉 중복은 *플랫폼 간* 문제이며, 그래서 행 삭제가 정답이 아니다.
   실제 문제는 SEO 이중화다 — `emdash.aikorea24.kr/posts/<slug>` 가 자기 자신을 가리키는 `canonical` 을 선언하고 `robots` meta 가 없어 aikorea24.kr 과 검색 결과를 경쟁한다.
   선택지: (a)现状 유지 (b) EmDash 측 `noindex` 또는 aikorea24.kr 로의 크로스도메인 canonical (c) `/posts/*` → `aikorea24.kr/blog/*` 301 (d) 행 삭제(라이브 사이트 파괴).
   **추천: (b) 또는 (c). (d) 는 대 unilaterally 실행 금지.**
3. ~~신규 생성 12건 이미지는 git 미추적~~ → **해소**
   `.gitignore:67` `public/images/` 규칙은 기존 1,567 디렉터리 전부에 적용되는 house 규칙이나, 이번 12건은 `git add -f` 로 예외적으로 커밋했다(백필 산출물 보존 목적).
4. ~~백필 대상이 2026-10-10 배치 한 건뿐 / 원인 특정 불가~~ → **해소 (원인 규명)**
   `scripts/emdash06_direct.py` 143–147 행이 `featured_image` 를 `lit(str(img)) if img else "NULL"` 로 기록하는데, 원본 마크다운 frontmatter 에 이미지가 없으면 NULL 이 된다. 일회성 마이그레이션 경로(EMDASH-06)의 동작이며 라이브 경로가 아니다.
   재발 방지 확인 — 현재 NULL 을 만들 수 있는 스케줄러 경로는 3개뿐이고 2개가 제거됐다: `blog_draft_generator.py::_push_to_emdash` (앞선 작업에서 삭제), `weekly_blog_publisher.py::_publish_to_emdash` (이번 작업에서 삭제), `blog_v2_generator.py::publish()` (수동 실행 전용, `--publish` 플래그만 존재하고 env 킬스위치 없음).
5. **이미지 관련성 — 육안 검수 완료, 12건 중 11 OK / 1 WEAK**
   Read 도구로 실제 이미지를 4라운드 육안 검수했다. 1라운드 **2 OK / 7 WEAK / 3 BAD** (주제 불일치 3건: LLM 추천 카드에 "CYBER AWARENESS" 간판, 유전자편집 단백질 카드에 **주식 캔들 차트**, 스마트홈 카드에 주제 없는 추상 블록). `emdash12_thumb_retry.py` 에 `slug::query` 인자 지원을 추가하고 주제 일치 키워드로 재생성 → 2라운드 **8 OK / 2 WEAK / 0 BAD**, 3라운드 **10 OK / 1 WEAK / 0 BAD**.
   최종 잔여 1건(WEAK): `오늘의-추천-llm-inkling-small…` — ChatGPT 로고를 제거하려 했으나 후속 검색어에서 **DeepSeek 로고**가 등장(추천 대상과 다른 모델의 로고이므로 오도). 4라운드(`text on computer screen macro`)에서 브랜드 없는 이미지를 얻었으나 주제 강도는 회귀(범용 코드 화면).
   **판단: 브랜딩 없는 이미지를 채택하고 반복 생성을 중단.** 경쟁사 로고가 붙으면 독자가 오인할 수 있는 반면( actively misleading ), 범용 기술 이미지는 그저 기억에 남지 않을 뿐이기 때문이다. 무료 AI 인터페이스 스톡 사진은 대부분 브랜드를 포함하므로 4라운드면 충분하다고 봤다.
6. **`scripts/blog_v2_generator.py::publish()` 는 env 킬스위치가 없다** — 252–271 행에서 `ec_posts`+`revisions` 에 직접 INSERT 하며, 보호 장치는 `--publish` CLI 플래그(278행) 뿐이다. 어떤 plist/crontab 에도 등록되어 있지 않아 수동 실행 전용이다. ① 과 달리 env 변수 하나로 되살릴 수 없어 위험도가 낮아 조치하지 않았다. EmDash 자체를 살려 둘지는 대표님 제품 결정 사항이다.
7. `scripts/logs/` 가 여전히 untracked & gitignore 미설정 (본 작업과 무관, 前 작업부터 잔존).
