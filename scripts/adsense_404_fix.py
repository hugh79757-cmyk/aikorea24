#!/usr/bin/env python3
"""AIK24-ADSENSE-404FIX — 광고 실린 404 페이지를 광고 없는 최소 페이지로 바꾸고 배포한다.

배경(2026-11-16): 7일 404 실측 informationhot 40,017 / aikorea24 27,659 / rotcha 19,832.
Hugo 테마의 404 는 `{{ define "main" }}` 만 정의해 baseof 를 상속하고, 그 head 에서
광고 partial 이 로드된다 → 봇이 아무 URL 이나 때리면 콘텐츠 없는 페이지에서 광고 요청이 발생.
AdSense 무효 노출의 직접적 원인.

수정: repo 루트에 **standalone** `layouts/404.html`(define 없음, noindex, 광고 없음)을 둔다.
그러면 테마 baseof 를 타지 않는다. 검증: etf-hugo 빌드에서 adsbygoogle 1 → 0, 852바이트.

사용:
  python3 scripts/adsense_404_fix.py --dry-run                 # 계획만
  python3 scripts/adsense_404_fix.py --apply --only etf-hugo   # 1개
  python3 scripts/adsense_404_fix.py --apply --limit 10        # 10개씩
  python3 scripts/adsense_404_fix.py --apply --no-deploy       # 템플릿+빌드만

토큰: ~/.wrangler/config/hugh79757.toml 의 OAuth(값 비출력). 배포 직전에
      `wrangler kv namespace list --profile hugh79757` 로 만료 시 자동 갱신한다.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
HUGO = "/opt/homebrew/bin/hugo"
WRANGLER = "/opt/homebrew/bin/wrangler"
THEMES = "/Users/twinssn/Projects/shared-themes"
PROFILE = "hugh79757"
ACCOUNT_ID = "fac9808c757df31d797190c529aaa71a"
STATE = os.path.join(HOME, "Projects/aikorea24/scripts/logs/adsense_404_fix.json")
TARGETS = "/tmp/pages_404_targets.json"

TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>페이지를 찾을 수 없습니다</title>
<style>
  body{margin:0;font-family:system-ui,-apple-system,"Apple SD Gothic Neo",sans-serif;
       display:flex;min-height:100vh;align-items:center;justify-content:center;background:#fff;color:#111}
  .box{text-align:center;padding:24px}
  h1{font-size:4rem;margin:0;line-height:1}
  p{color:#555;margin:12px 0 24px}
  a{display:inline-block;padding:10px 22px;background:#111;color:#fff;border-radius:8px;text-decoration:none}
</style>
</head>
<body>
  <div class="box">
    <h1>404</h1>
    <p>요청하신 페이지를 찾을 수 없습니다.</p>
    <a href="/">홈으로 돌아가기</a>
  </div>
</body>
</html>
"""


def load_toml_token():
    p = os.path.join(HOME, ".wrangler/config/%s.toml" % PROFILE)
    txt = open(p, encoding="utf-8").read()
    return re.search(r'oauth_token\s*=\s*"([^"]+)"', txt).group(1)


def refresh_token():
    """만료 임박해도 wrangler 가 refresh_token 으로 갱신한다(무해한 읽기 명령)."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")}
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    subprocess.run([WRANGLER, "kv", "namespace", "list", "--profile", PROFILE],
                   env=env, capture_output=True, text=True, timeout=120)


def page_projects(token):
    out, page = set(), 1
    while page <= 12:
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/%s/pages/projects?page=%d" % (ACCOUNT_ID, page),
            headers={"Authorization": "Bearer " + token})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError:
            break
        res = d.get("result") or []
        if not res:
            break
        out |= {x["name"] for x in res}
        if len(res) < 10:
            break
        page += 1
    return out


def ads_count(path):
    if not os.path.exists(path):
        return None
    t = open(path, encoding="utf-8", errors="ignore").read()
    return t.count("adsbygoogle") + t.count("ca-pub-")


def run(cmd, cwd=None, env=None, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fix_site(site, name, domains, deploy, token):
    repo = site["path"]
    tpl = os.path.join(repo, "layouts/404.html")
    rec = {"name": name, "repo": repo, "domains": domains, "steps": {}}

    # 1) 템플릿
    if os.path.exists(tpl):
        old = open(tpl, encoding="utf-8", errors="ignore").read()
        if "adsbygoogle" in old or "ca-pub-" in old:
            shutil.copy2(tpl, tpl + ".bak.20261116")
            rec["steps"]["template"] = "기존 템플릿에 광고 → 백업 후 교체"
        else:
            rec["steps"]["template"] = "이미 광고 없는 템플릿(유지)"
    else:
        rec["steps"]["template"] = "새로 생성"
    if not os.path.exists(tpl) or "adsbygoogle" in open(tpl, encoding="utf-8", errors="ignore").read():
        os.makedirs(os.path.dirname(tpl), exist_ok=True)
        open(tpl, "w", encoding="utf-8").write(TEMPLATE)

    # 2) 빌드
    env = dict(os.environ)
    env["HUGO_THEMESDIR"] = THEMES
    rc, out = run([HUGO, "--gc", "--minify"], cwd=repo, env=env, timeout=600)
    if rc != 0:
        # ETAP 34개 사이트는 layouts/_default/single.html 이 partial "disclaimer.html" 을
        # 호출하는데 그 partial 이 저장소에 없다(2026-11-16 실측, michelin/nomad 에만 존재).
        # 빌드가 원래 깨져 있으므로, 이미 배포된 public/ 은 건드리지 않고 404.html 만 교체한다.
        rec["steps"]["build"] = "실패(기존 결함) → public/404.html 직접 교체"
        rec["build_error"] = (out.strip().splitlines() or ["?"])[-1][:160]
        pub404 = os.path.join(repo, "public/404.html")
        if not os.path.exists(pub404):
            rec["error"] = "빌드 실패 + public/404.html 없음"
            return rec
        open(pub404, "w", encoding="utf-8").write(TEMPLATE)
        rec["steps"]["built_404_ads"] = ads_count(pub404)
        if rec["steps"]["built_404_ads"] != 0:
            rec["error"] = "폴백 후에도 광고 잔존"
            return rec
        if not deploy:
            rec["steps"]["deploy"] = "생략(--no-deploy)"
            return rec
        # 이 아래 배포는 공통 경로를 그대로 탄다.
    else:
        rec["steps"]["build"] = "성공"

    # 3) 빌드 산출물 검증
    n = rec["steps"].get("built_404_ads")
    if n is None:
        n = ads_count(os.path.join(repo, "public/404.html"))
        rec["steps"]["built_404_ads"] = n
    if n is None:
        rec["error"] = "public/404.html 없음"
        return rec
    if n != 0:
        rec["error"] = "빌드 404 에 광고 %d건 잔존" % n
        return rec

    if not deploy:
        rec["steps"]["deploy"] = "생략(--no-deploy)"
        return rec

    # 4) 배포
    # OAuth 토큰을 주입하지 않고 wrangler --profile 에 맡긴다.
    # (2026-11-16 실측: 토큰을 직접 넣으면 중간에 9109 로 무효화되지만 --profile 은 자동 갱신된다)
    denv = {k: v for k, v in os.environ.items()
            if k not in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")}
    denv["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    rc, out = run([WRANGLER, "pages", "deploy", "public", "--project-name", name,
                   "--commit-dirty=true", "--profile", PROFILE], cwd=repo, env=denv, timeout=900)
    if rc != 0:
        rec["steps"]["deploy"] = "실패"
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        pick = next((ln for ln in lines if "9109" in ln or "ERROR" in ln), lines[-1] if lines else "?")
        rec["error"] = pick[:200]
        return rec
    m = re.search(r"https://([0-9a-f]+\.%s\.pages\.dev)" % re.escape(name), out)
    rec["steps"]["deploy"] = "성공"
    if m:
        rec["deploy_url"] = m.group(1)
    return rec


def live_check(domains):
    """배포 후 실제 404 응답에 광고가 없는지 (첫 커스텀 도메인 기준)."""
    for d in domains or []:
        if d.endswith(".pages.dev"):
            continue
        url = "https://%s/definitely-not-a-real-page-zz9" % d
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
        try:
            r = urllib.request.urlopen(req, timeout=25)
            code, body = r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read().decode("utf-8", "ignore")
        except Exception as e:
            return {"domain": d, "error": type(e).__name__}
        n = body.count("adsbygoogle") + body.count("ca-pub-")
        if n:  # Pages 반영 지연(수십 초) — 한 번만 재확인
            time.sleep(20)
            try:
                r = urllib.request.urlopen(req, timeout=25)
                code, body = r.status, r.read().decode("utf-8", "ignore")
            except urllib.error.HTTPError as e:
                code, body = e.code, e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            n = body.count("adsbygoogle") + body.count("ca-pub-")
        return {"domain": d, "status": code, "ads": n, "bytes": len(body)}
    return {"error": "커스텀 도메인 없음"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-done", action="store_true",
                    help="STATE 로그에서 배포까지 성공한 사이트는 건너뛴다(중단 후 재개용)")
    a = ap.parse_args()

    targets = json.load(open(TARGETS, encoding="utf-8"))
    if a.skip_done and os.path.exists(STATE):
        done = {r["name"] for r in json.load(open(STATE, encoding="utf-8"))
                if r.get("steps", {}).get("deploy") == "성공" and not r.get("error")
                and (r.get("live") or {}).get("ads") == 0}
        before = len(targets)
        targets = [t for t in targets if t["name"] not in done]
        print("이미 완료 %d개 건너뜀 (남은 %d)" % (before - len(targets), len(targets)))
    if a.only:
        wanted = {x.strip() for x in a.only.split(",")}
        targets = [t for t in targets if t["name"] in wanted]
    if a.limit:
        targets = targets[:a.limit]

    print("대상 %d개 | %s" % (len(targets), "APPLY" if a.apply else "DRY-RUN"))
    if not a.apply:
        for t in targets:
            print("  · %-24s %s" % (t["name"], ",".join(t["domains"])[:50]))
        return

    token = ""
    have = set()
    try:
        token = load_toml_token()
        have = page_projects(token)
    except Exception:
        have = set()
    if not have:
        print("! 프로젝트 목록 조회 실패 — 필터 없이 진행(배포 단계에서 판정)")
    else:
        missing = [t["name"] for t in targets if t["name"] not in have]
        if missing:
            print("! 접근 불가 프로젝트 %d개: %s" % (len(missing), ", ".join(missing[:6])))
        targets = [t for t in targets if t["name"] in have]

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    hist = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    ok = fail = 0
    for i, t in enumerate(targets, 1):
        print("\n[%d/%d] %s" % (i, len(targets), t["name"]), flush=True)
        try:
            rec = fix_site(t, t["name"], t["domains"], not a.no_deploy, token)
        except Exception as e:  # noqa: BLE001
            rec = {"name": t["name"], "error": "%s: %s" % (type(e).__name__, str(e)[:150])}
        rec["ts"] = time.time()
        if not a.no_deploy and rec.get("steps", {}).get("deploy") == "성공":
            rec["live"] = live_check(t["domains"])
            print("   live:", json.dumps(rec["live"], ensure_ascii=False)[:120])
        if rec.get("error"):
            fail += 1
            print("   ✗", rec["error"])
        else:
            ok += 1
            print("   ✓", rec.get("steps", {}))
        hist.append(rec)
        json.dump(hist, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n완료: 성공 %d / 실패 %d (로그 %s)" % (ok, fail, STATE))


if __name__ == "__main__":
    main()
