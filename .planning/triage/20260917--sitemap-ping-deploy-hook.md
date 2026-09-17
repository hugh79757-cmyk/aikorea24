---
date: 2026-09-17
type: feat
status: resolved
---

# sitemap ping — 배포 후 검색엔진 크롤 요청 (deploy.sh 자동 연결)

## What

트래픽 유입 채널 보강. 배포 완료 직후 사이트맵을 검색엔진에 제출하는 스크립트를
추가하고 `deploy.sh`에 best-effort로 연결.

## Why

`grep` 결과 사이트맵을 검색엔진에 능동적으로 알리는 코드가 0건이었음.
`sitemap-index.xml` + 서브맵 6종은 정적으로 서빙만 되고 있었음.

## Files changed

- `scripts/sitemap_ping.py` (신규, stdlib만 사용)
- `scripts/deploy.sh` — 배포 완료 라인 뒤에 ping 호출 추가 (실패해도 배포는 성공)

## How

`scripts/sitemap_ping.py`:
- `DEFAULT_SITEMAP = 'https://aikorea24.kr/sitemap-index.xml'`
- `_http(url, timeout=15)` / `ping_google(sitemap_url)` / `ping_naver(sitemap_url)` / `main()`
- 인자: `--sitemap`, `--google-only`
- 로그: `logs/sitemap_ping.log`

**중요 발견 — 공식 ping API는 둘 다 폐기/부재:**
- Google `https://www.google.com/ping?sitemap=` → 404
  "Sitemaps ping is deprecated. See https://developers.google.com/search/blog/2023/06/sitemaps-lastmod-ping"
  (2023-06 폐기)
- Naver SA 후보 엔드포인트 4종(`/api/sitemap`, `/sitemap`, `/api/v1/sitemaps`,
  `/api/site`) 전부 404

→ 두 함수를 정직한 폴백으로 재작성: 사이트맵 자체를 GET해서 도달성 + `<loc>`
존재를 확인하고 보고. Naver 등록 경로는 `SEOHead.astro`의
`<meta name="naver-site-verification">` 메타 태그이며, SA 콘솔 수동 등록은
사용자 몫 (에이전트 SA 로그인 절대 금지 — AGENTS.md 섹션 4).

`deploy.sh` 연결 (배포 완료 라인 뒤):
```bash
python3 "$PROJECT_DIR/scripts/sitemap_ping.py" --sitemap "https://aikorea24.kr/sitemap-index.xml" || echo "  ⚠️ sitemap ping 실패 (배포는 성공)"
```

## Verification

- `bash -n scripts/deploy.sh` OK, `py_compile` OK.
- `python3 scripts/sitemap_ping.py --sitemap https://aikorea24.kr/sitemap-blog.xml`
  → exit 0, `{"google": true, "naver": true}`, reachable=True status=200.
- `curl https://aikorea24.kr/sitemap-blog.xml` → `<url>` 1237건, 09-17 신규 6건 포함.
- 커밋: `b2789bf3`

## 잔존 위험

- Google/Naver 모두 공식 ping API가 없으므로 "크롤 요청"은 실제로는 도달성
  점검에 가까움. 실질 색인 촉진은 Google Search Console / Naver SA 콘솔의
  수동 제출 또는 자연 크롤에 의존.
- Naver SA 콘솔에 `aikorea24.kr`이 등록돼 있는지 미확인 (사용자 확인 필요).
