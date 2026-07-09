---
date: 2026-07-09
type: fix
status: resolved
---

# env_loader: load_to_environ() setdefault로 인해 project .env 무시

## What
`EnvConfig.load_to_environ()`이 `if key not in os.environ:` 조건으로 setdefault 방식 동작.
`~/.env.common`의 유효하지 않은 `CLOUDFLARE_API_TOKEN`이 os.environ에 먼저 설정되어,
프로젝트 `.env`의 올바른 토큰이 무시됨. D1 쿼리 Authentication error 발생.

## Why
`_load_file()` 단계에서는 project .env가 ~/.env.common을 올바르게 덮어쓰지만
(`setdefault=False`), `load_to_environ()`에서 다시 `if key not in os.environ` 조건을 적용하여
이미 설정된 ~/.env.common 값을 덮어쓰지 않음. 문서화된 우선순위("프로젝트 .env 최우선")와 실제 동작이 불일치.

## Files changed
- `pipeline/infra/env_loader.py` (load_to_environ)

## How
`load_to_environ()`의 `if key not in os.environ:` 조건 제거.
`_vars`의 모든 값을 무조건 os.environ에 설정. `_load_file()` 단계에서 이미 우선순위가 결정됨.

## Verification
수정 후 `CLOUDFLARE_API_TOKEN=cfut_fmdyb...` 설정 시 D1 쿼리 정상 동작 확인.
dry-run에서 기사 풀 정상 로드 (이전에는 Authentication error).
