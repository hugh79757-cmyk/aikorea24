# Worklog: WL-20261001-sitemap-index-404-fix

## Operation
`/sitemap-index.xml` 404 수정 — robots.txt / SEOHead.astro / llms.txt가 `/sitemap-index.xml`을 참조하나 라우트가 `/sitemap.xml`만 존재.

## Pre-Count
- 대상: 참조 URL 3곳 (public/robots.txt:19, src/components/SEOHead.astro:134, public/llms.txt:31)
- 라이브 상태: sitemap-index.xml = 404, sitemap.xml = 200
- 최신 Production deployment: 60c27128-93d5-45de-b4d5-d70f6992444a

## Backup / Rollback
- 롤백 대상 deployment ID: 60c27128-93d5-45de-b4d5-d70f6992444a
- 명령: `wrangler pages deployment rollback --project-name aikorea24 60c27128-93d5-45de-b4d5-d70f6992444a`

## Execution
1. `src/pages/sitemap-index.xml.ts` 신규 생성 (sitemap.xml.ts와 동일 buildIndex 출력, prerender=true)
2. `npm run build` → `dist/sitemap-index.xml` 808 bytes 생성 확인
3. wrangler pages deploy dist (env.common 토큰 export 경로) → deployment fb6c2cd8

## Post-Verification
- sitemap.xml → 200
- sitemap-index.xml → 200 (기존 404 해소)
- robots.txt → 200 / llms.txt → 200
- sitemap-blog.xml `<loc>` 1,379건 (deploy 전 dist 기준 1,379와 일치)

## Logs
- logs/deploy_2026-10-01.log
