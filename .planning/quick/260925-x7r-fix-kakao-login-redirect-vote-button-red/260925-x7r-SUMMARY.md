---
phase: quick
plan: 260925-x7r
subsystem: auth
tags: [kakao, login, redirect, vote-button]
dependency_graph:
  requires: []
  provides: [kakao-callback-state, vote-redirect-to]
  affects: [src/pages/api/auth/kakao.ts, src/pages/api/auth/callback/kakao.ts, src/pages/tools/[id].astro]
tech-stack: [astro, kakao-oauth, cookies]
key_files:
  created: []
  modified:
    - src/pages/api/auth/kakao.ts
    - src/pages/api/auth/callback/kakao.ts
    - src/pages/tools/[id].astro
decisions:
  - kakao.ts mirrors Google login.ts: read redirect_to, pass as state
  - callback/kakao.ts mirrors Google callback: validate state, redirect
  - consent.astro already had redirect_to logic — Fix 3 was no-op
status: complete
actuals:
  tokens: 4200
  tasks: 3
  commits: 3
---

# Quick 260925-x7r: Fix Kakao Login Redirect + Vote Button redirect_to

## Results

| Fix | File | Status |
|-----|------|--------|
| 1a | `src/pages/api/auth/kakao.ts` | [검증됨] — `redirect_to` query param → state param |
| 1b | `src/pages/api/auth/callback/kakao.ts` | [검증됨] — state read, validate (`/` start, no `//` or `\`), redirect |
| 2 | `src/pages/tools/[id].astro` | [검증됨] — 401 → `/api/auth/login?redirect_to=<path>` |
| 3 | `src/pages/auth/consent.astro` | [검증됨] — already had redirect_to logic; no change needed |

## Commits

- `213ee74e`: fix(kakao-auth): pass redirect_to as state to Kauth OAuth URL
- `381ff353`: fix(kakao-callback): read state param, validate, redirect after login
- `03a65ad6`: fix(vote-button): add redirect_to to login redirect on 401

## Deviations

None — plan executed exactly as written. Fix 3 (consent page) was already implemented.

## Self-Check

- Build: `npm run build` → completed in 2.14s, no errors
- All 3 files changed per git diff
