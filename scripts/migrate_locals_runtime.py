#!/usr/bin/env python3
"""AIK24-MIGRATE-01 Phase 2: Astro.locals.runtime → cloudflare:workers env 일괄 마이그레이션.

Astro 6에서 제거된 Astro.locals.runtime을 쓰던 47개 파일을 정식 경로로 옮긴다.
어댑터의 createLocals()가 runtime을 writable:false로 정의해 두기 때문에
미들웨어 주입/재정의가 모두 불가능하다(측정됨).

치환 규칙 (선언 형태 2종 + 인라인 1종):
  const runtime = (Astro.locals as any).runtime;      → import { env } from 'cloudflare:workers';
  const db = (Astro.locals as any).runtime?.env?.DB;  → const db = env.DB;
  런타임 뒤의 ?.env?.KEY / .env.KEY                   → env.KEY

주의: import.meta.env.DEV/PROD 는 이 패턴과 무관하므로 건드리지 않는다(치환이
.runtime 으로 한정된 문자열만 바꾼다).

사용: python3 scripts/migrate_locals_runtime.py [--dry]
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPORT_LINE = "import { env } from 'cloudflare:workers';"

# .runtime 으로 시작해서 .env 를 거쳐 키까지 가는 표현만 다룬다.
# import.meta.env 는 .runtime 이 없으므로 애초에 매칭되지 않는다.
# (Astro.locals as any) / (context.locals as any) / (locals as any) 세 가지를 모두 커버
_LOCALS = r"\((?:[A-Za-z_$][\w$]*\.)?locals as any\)"
RUNTIME_ENV = re.compile(
    _LOCALS + r"\.runtime(\?)?\.env(\?)?\.([A-Za-z_][A-Za-z0-9_]*)"
)
DECL = re.compile(r"^\s*const (\w+) = " + _LOCALS + r"\.runtime;\s*$", re.M)


def migrate(text: str):
    """(치환 후 텍스트, 적용 여부, 설명) 반환"""
    changed = []
    decl_names = {m.group(1) for m in DECL.finditer(text)}

    # 1) 선언형: const runtime = (... as any).runtime;  →  import 문으로 대체
    if DECL.search(text):
        text = DECL.sub("", text)

    # 2) 인라인/변수 참조형: (... as any).runtime?.env?.KEY → env.KEY
    n_inline = len(RUNTIME_ENV.findall(text))
    text = RUNTIME_ENV.sub(lambda m: f"env.{m.group(3)}", text)

    # 3) 선언변수를 쓰는 나머지 곳: runtime?.env?.KEY / runtime.env.KEY → env.KEY
    n_decl = 0
    for name in decl_names:
        pat = re.compile(rf"\b{re.escape(name)}(\?)?\.env(\?)?\.([A-Za-z_][A-Za-z0-9_]*)")
        n_decl += len(pat.findall(text))
        text = pat.sub(lambda m: f"env.{m.group(3)}", text)

        # 3b) `const env = runtime?.env;` 처럼 .env 뒤에 KEY 없이 끝나는 대입형.
        #     1번에서 runtime 선언은 지워졌으므로 이 줄만 남으면 ReferenceError 가 된다.
        #     (2026-10-11 실제 사고: refresh.ts 가 이 형태로 남아 /api/network/refresh 가 500)
        bare = re.compile(rf"^\s*const\s+\w+\s*=\s*{re.escape(name)}\??\.env;\s*$\n?", re.M)
        text, k = bare.subn("", text)
        if k:
            changed.append(f"bare-env-decl={k}")

    # 안전장치: 선언을 지웠는데 이름이 아직 남아 있으면 파일을 쓰지 않는다.
    leftover = [n for n in decl_names if re.search(rf"\b{re.escape(n)}\b", text)]

    if n_inline or n_decl or decl_names:
        changed.append(f"inline={n_inline} declvar={n_decl} decls={len(decl_names)}")

    # 4) import 추가 (파일 상단 frontmatter/script 블록의 첫 import 옆)
    if changed and IMPORT_LINE not in text:
        m = re.search(r"^import .+?;$", text, re.M)
        if m:
            text = text[: m.start()] + IMPORT_LINE + "\n" + text[m.start():]
        elif text.lstrip().startswith("---"):
            # .astro frontmatter: fence 바로 뒤에 넣어야 바깥 텍스트로 안 취급된다
            fence = re.search(r"^\s*---\s*$", text, re.M)
            pos = fence.end()
            text = text[:pos] + "\n" + IMPORT_LINE + text[pos:]
        else:
            text = IMPORT_LINE + "\n" + text

    if leftover:
        raise RuntimeError(
            f"선언을 제거했는데 {leftover} 참조가 남아 있다 — ReferenceError 위험. 수동 확인 필요."
        )

    return text, bool(changed), ("; ".join(changed) if changed else "")


def main():
    dry = "--dry" in sys.argv
    files = subprocess.run(
        ["grep", "-rl", ".runtime", "src/"], cwd=ROOT, capture_output=True, text=True
    ).stdout.split()

    todo, skipped = [], []
    for rel in files:
        p = ROOT / rel
        src = p.read_text(encoding="utf-8")
        if ".runtime" not in src:
            continue
        new, changed, why = migrate(src)
        if not changed:
            skipped.append(rel)
            continue
        # 검증: .runtime 이 남아 있으면 실패로 본다
        left = len(re.findall(r"\.runtime\b", new))
        if left:
            print(f"  ! {rel}: 치환 후 .runtime {left}건 잔존 — 손대지 않음")
            skipped.append(rel)
            continue
        todo.append((rel, new, why))

    print(f"마이그레이션 대상 {len(todo)}건 / 미적합 {len(skipped)}건 (전체 .runtime 파일 {len(files)}건)\n")
    if not dry:
        for rel, new, _ in todo:
            (ROOT / rel).write_text(new, encoding="utf-8")
        print("기록 완료")
    else:
        for rel, _, why in todo[:10]:
            print(f"  [dry] {rel}  ({why})")
        if len(todo) > 10:
            print(f"  … 외 {len(todo)-10}건")


if __name__ == "__main__":
    main()
