---
date: 2026-07-14
type: config
status: resolved
---

# Wrangler Auth Profile 설정 — Cloudflare 로그인 문제 해결

## What
Cloudflare Pages 배포 시 `Authentication error code: 10000` / API token 권한 부족 문제 해결.  
기존 `CLOUDFLARE_API_TOKEN` 환경변수 기반 인증에서 OAuth auth profile 기반으로 전환.

## Why
- OpenCode/Codex agent가 매 세션마다 `CLOUDFLARE_API_TOKEN`을 환경변수에 설정 (hugh 계정 ID)
- 이 token이 wrangler auth profile보다 우선 적용되어 profile 생성/활성화 차단
- Pages 배포 권한이 token에 없어 `wrangler deploy` 실패

## Files changed
- `/Users/twinssn/Projects/aikorea24/.env` — `CLOUDFLARE_API_TOKEN` 주석처리
- `/Users/twinssn/.zshrc` (lines 84-99) — 이미 wrangler 함수 존재 (`env` vars unset/restore)
- `scripts/deploy.sh` — **아직 수정 필요** (`npx wrangler` → 글로벌 바이너리)

## How
1. `wrangler` 4.50.0 → 4.110.0 업그레이드 (auth profiles 기능)
2. `wrangler auth create hugh79757` — 브라우저 OAuth 로그인
3. `wrangler auth activate hugh79757 /Users/twinssn/Projects/aikorea24` — 디렉터리 바인딩
4. `.env`에서 `CLOUDFLARE_API_TOKEN` 제거 (주석처리)
5. 배포 테스트: `exec env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler pages deploy dist ...` → 성공

## 핵심 — 다른 세션에서 다시 겪지 않으려면

### Interactive shell (.zshrc)
`.zshrc` lines 84-99에 wrangler 함수가 이미 있음 — `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` 등 env var를 자동 unset/restore. interactive shell에서는 문제없음.

### Agent 세션 (OpenCode/Codex)
`.zshrc`가 로딩되지 않으므로, wrangler 실행 시 **직접 env var 해제 필요**:
```bash
env -u CLOUDFLARE_API_TOKEN wrangler pages deploy dist --project-name aikorea24 --branch main
```

### deploy.sh 수정 필요 (아직 안 함)
`scripts/deploy.sh`가 `npx wrangler`를 사용 → 로컬 4.50.0 (profiles 미지원) 실행됨.  
글로벌 바이너리로 변경 필요:
```bash
env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler pages deploy dist ...
```

### Auth profile 상태
| Profile | Bind Directory |
|---|---|
| `hugh79757` | `/Users/twinssn/Projects/aikorea24` |
| `farmsolution` | `/Users/twinssn/projects2/farmsolution` |

## Verification
- `wrangler whoami` → `Active profile: hugh79757` / `hugh79757@gmail.com` OAuth 인증
- `wrangler pages deploy dist --project-name aikorea24 --branch main --commit-dirty=true` → `Deployment complete!`
- 권한: pages(write), d1(write), workers_scripts(write) 등 전체 포함
