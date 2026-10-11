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

## 7. 잔존 위험

1. **`scripts/weekly_blog_publisher.py` 의 `_publish_to_emdash`** (기본 off, `EMDASH_PUBLISH=1` 일 때만 동작) 미확인. 이번 작업 범위 밖이며, 켜져 있으면 EmDash 경유 발행으로 계속 중복 적재될 수 있음.
2. **기존 EmDash 중복 데이터 미정리** — EmDash `ec_posts`/`revisions` 의 과거 행은 그대로 남김. 대표님이 aikorea24.kr/blog 를 정식 위치로 확정한 만큼 중복 수집본 제거는 별건으로 필요.
3. **신규 생성 12건 이미지는 git 미추적** — `.gitignore:67` `public/images/` 규칙에 의해 커밋되지 않음(기존 1,567 디렉터리와 동일한 house 규칙). 백업 시 `public/images/` 별도 보관 필요.
4. **백필 대상이 2026-10-10 배치 한 건뿐** — 같은 배치에서 `featured_image` 미설정 원인은 D1 기록만으로 특정 불가. 동일 증상 재발 시 동일 절차 재사용 가능.
5. **이미지 관련성 일부는 수동 확인 필요** — Pexels 검색어 기반 자동 매칭이므로 카드 이미지가 글 내용과 무관할 수 있음 (예: "삼성 브로드컴 칩 계약" 카드에 추상 기술 이미지). 전수 육안 검수는 하지 않음.
