#!/usr/bin/env python3
"""AIK24-ADSENSE-GUARD-01 — Cloudflare 존 보안 하드닝 (무효 트래픽 대응).

목적: AdSense 무효클릭/무효노출 제재 대응의 **유입 정화** 단계.
      광고 판정 자체는 AdSense 몫이고, Cloudflare 는 봇·스크래퍼·헤드리스 트래픽을
      광고가 실린 페이지에 도달하지 못하게 막는 역할만 한다.

전제 토큰 권한 (Cloudflare API Token):
  Zone:Read / Zone Settings:Edit / Zone WAF:Edit / Zone Analytics:Read / Bot Management:Edit

사용:
  python3 scripts/cf_adsense_guard.py audit                    # 현재 상태만 출력
  python3 scripts/cf_adsense_guard.py apply --only settings    # https/TLS
  python3 scripts/cf_adsense_guard.py apply --only bot         # Bot Fight Mode
  python3 scripts/cf_adsense_guard.py apply --only waf         # 커스텀 룰 + 관리 규칙셋
  python3 scripts/cf_adsense_guard.py apply --only ratelimit   # 레이트 리밋
  python3 scripts/cf_adsense_guard.py apply --only all
  (--dry-run 을 붙이면 쓰지 않고 계획만 출력)

토큰: 환경변수 CF_STYLEFACTORY9AI_API_TOKEN → CF_ADSENSE_TOKEN → CF_MIGRATE_TOKEN 순으로 찾는다.
       값은 절대 출력하지 않는다.
"""
import argparse
import json
import os
import sys

import httpx

API = "https://api.cloudflare.com/client/v4"
ENV_FILE = os.path.expanduser("~/.env.common")
TOKEN_VARS = ("CF_ADSENSE_TOKEN", "CF_STYLEFACTORY9AI_API_TOKEN", "CF_MIGRATE_TOKEN")

# 관리 규칙셋(무료) — 이름으로 찾는다(하드코딩 id 는 존마다 다를 수 있다).
MANAGED_FREE_NAME = "Cloudflare Managed Free Ruleset"

# ── 차단/챌린지 대상: 독자를 데려오지 않는 자동화 트래픽 ──────────────────
# 근거(2026-11-16 7일 실측, aikorea24.kr): 빈 UA 39,391 / SERankingBacklinksBot 20,900 /
# MJ12bot 17,063 / UA "node" 16,387 / Bytespider 10,887 / HeadlessChrome 6,776.
JUNK_UA = ("MJ12bot", "SERankingBacklinksBot", "Bytespider", "AhrefsBot", "SemrushBot", "DotBot")
HEADLESS_UA = ("HeadlessChrome", "node")

AD_PATHS_RATE = ('(http.request.uri.path eq "/" or starts_with(http.request.uri.path, "/posts") '
                 'or starts_with(http.request.uri.path, "/benefits") '
                 'or starts_with(http.request.uri.path, "/community"))')


def load_env():
    if not os.path.exists(ENV_FILE):
        return
    for line in open(ENV_FILE, encoding="utf-8"):
        k, _, v = line.strip().partition("=")
        k = k.strip()
        if not k or k.startswith("#") or k in os.environ:
            continue
        os.environ[k] = v.strip().strip('"').strip("'")


def token():
    load_env()
    for name in TOKEN_VARS:
        v = os.environ.get(name, "").strip()
        if v:
            return v, name
    sys.exit("토큰 없음 — %s 중 하나를 ~/.env.common 에 둘 것" % ", ".join(TOKEN_VARS))


class CF:
    def __init__(self, tok):
        self.c = httpx.Client(base_url=API, timeout=30,
                              headers={"Authorization": "Bearer %s" % tok})

    def call(self, method, path, body=None):
        r = self.c.request(method, path, json=body)
        try:
            d = r.json()
        except ValueError:
            return r.status_code, {"errors": [{"message": r.text[:200]}]}
        return r.status_code, d

    def ok(self, method, path, body=None):
        st, d = self.call(method, path, body)
        if not d.get("success", False):
            raise RuntimeError("%s %s → %s %s" % (method, path, st,
                                                  json.dumps(d.get("errors"))[:300]))
        return d.get("result")


def zones(cf):
    return {z["name"]: z["id"] for z in (cf.ok("GET", "/zones?per_page=50") or [])}


def get_setting(cf, zid, key):
    return (cf.ok("GET", "/zones/%s/settings/%s" % (zid, key)) or {}).get("value")


def audit(cf, zid, name):
    print("── %s (%s)" % (name, zid))
    for k in ("always_use_https", "min_tls_version", "ssl", "security_level", "waf",
              "browser_check", "challenge_ttl"):
        try:
            print("   %-20s %s" % (k, get_setting(cf, zid, k)))
        except Exception as e:  # noqa: BLE001
            print("   %-20s (조회 불가: %s)" % (k, str(e)[:60]))
    try:
        bm = cf.ok("GET", "/zones/%s/bot_management" % zid) or {}
        print("   %-20s fight_mode=%s js=%s ai_bots=%s"
              % ("bot_management", bm.get("fight_mode"), bm.get("enable_js"),
                 bm.get("ai_bots_protection")))
    except Exception as e:  # noqa: BLE001
        print("   %-20s (조회 불가: %s)" % ("bot_management", str(e)[:60]))
    for phase in ("http_request_firewall_custom", "http_request_firewall_managed", "http_ratelimit"):
        st, d = cf.call("GET", "/zones/%s/rulesets/phases/%s/entrypoint" % (zid, phase))
        rules = ((d.get("result") or {}).get("rules") or []) if d.get("success") else []
        print("   %-28s %s" % (phase, ("%d개 규칙" % len(rules)) if d.get("success") else "없음"))
        for r in rules:
            print("      - %-34s action=%s enabled=%s"
                  % ((r.get("description") or "")[:34], r.get("action"), r.get("enabled")))


def apply_settings(cf, zid, dry):
    """HTTPS 강제 + 최소 TLS. 독자에게 보이는 변화는 http→https 리다이렉트뿐이다."""
    for key, val in (("always_use_https", "on"), ("min_tls_version", "1.2")):
        cur = get_setting(cf, zid, key)
        if str(cur) == str(val):
            print("   = %-18s 이미 %s" % (key, val))
            continue
        if dry:
            print("   ~ %-18s %s → %s (dry-run)" % (key, cur, val))
            continue
        cf.ok("PATCH", "/zones/%s/settings/%s" % (zid, key), {"value": val})
        print("   ✓ %-18s %s → %s" % (key, cur, get_setting(cf, zid, key)))


def apply_bot(cf, zid, dry):
    """Bot Fight Mode. Googlebot 등 검증된 검색봇은 영향 없음(Cloudflare 가 예외 처리)."""
    bm = cf.ok("GET", "/zones/%s/bot_management" % zid) or {}
    if bm.get("fight_mode"):
        print("   = fight_mode 이미 켜짐")
        return
    if dry:
        print("   ~ fight_mode false → true (dry-run)")
        return
    try:
        cf.ok("PATCH", "/zones/%s/bot_management" % zid, {"fight_mode": True})
    except RuntimeError as e:
        # 무료 플랜 + API 토큰에서는 이 엔드포인트가 405(10405) 로 막힌다 — 대시보드 전용.
        print("   ! API 로 전환 불가(%s)" % str(e).split("→")[-1].strip()[:80])
        print("     → 대시보드 수동: Security → Bots → Bot fight mode ON (1회)")
        return
    after = cf.ok("GET", "/zones/%s/bot_management" % zid) or {}
    print("   ✓ fight_mode → %s" % after.get("fight_mode"))


def _expr_any(ua_list):
    return " or ".join('(http.user_agent contains "%s")' % u for u in ua_list)


def custom_rules():
    """커스텀 룰 5개(무료 플랜 상한). 순서가 곧 우선순위다."""
    return [
        {"action": "block", "enabled": True,
         "description": "adg: SEO/스크래퍼 봇 차단 (독자 유입 없음)",
         "expression": _expr_any(JUNK_UA)},
        {"action": "managed_challenge", "enabled": True,
         "description": "adg: 빈 User-Agent 챌린지",
         "expression": '(http.user_agent eq "")'},
        {"action": "managed_challenge", "enabled": True,
         "description": "adg: 헤드리스/스크립트 UA 챌린지",
         "expression": _expr_any(HEADLESS_UA)},
        {"action": "block", "enabled": True,
         "description": "adg: 검색 인덱스 비브라우저 대량 수집 차단",
         "expression": ('(http.request.uri.path eq "/search.json") '
                        'and not (http.user_agent contains "Mozilla")')},
        {"action": "block", "enabled": True,
         "description": "adg: 취약점 스캐너 경로 차단",
         "expression": ('(http.request.uri.path contains "/wp-") or '
                        '(http.request.uri.path contains "/.env") or '
                        '(http.request.uri.path contains "/xmlrpc.php")')},
    ]


def apply_waf(cf, zid, dry):
    rules = custom_rules()
    if dry:
        print("   ~ 커스텀 룰 %d개 PUT (dry-run)" % len(rules))
    else:
        cf.ok("PUT", "/zones/%s/rulesets/phases/http_request_firewall_custom/entrypoint" % zid,
              {"rules": rules})
        got = (cf.ok("GET", "/zones/%s/rulesets/phases/http_request_firewall_custom/entrypoint" % zid)
               or {}).get("rules") or []
        print("   ✓ 커스텀 룰 %d개 반영" % len(got))
        for r in got:
            print("      - %-34s action=%s enabled=%s" % ((r.get("description") or "")[:34],
                                                          r.get("action"), r.get("enabled")))
    # 관리 규칙셋(무료) 배포
    rs = cf.ok("GET", "/zones/%s/rulesets?per_page=50" % zid) or []
    free = next((r for r in rs if r.get("name") == MANAGED_FREE_NAME), None)
    if not free:
        print("   ! %s 없음 — 관리 규칙셋 배포 생략" % MANAGED_FREE_NAME)
        return
    managed_rule = {
        "action": "execute", "enabled": True,
        "description": "adg: %s" % MANAGED_FREE_NAME,
        "expression": "true",
        "action_parameters": {"id": free["id"]},
    }
    if dry:
        print("   ~ 관리 규칙셋 %s 배포 (dry-run)" % free["id"])
        return
    cf.ok("PUT", "/zones/%s/rulesets/phases/http_request_firewall_managed/entrypoint" % zid,
          {"rules": [managed_rule]})
    got = (cf.ok("GET", "/zones/%s/rulesets/phases/http_request_firewall_managed/entrypoint" % zid)
           or {}).get("rules") or []
    print("   ✓ 관리 규칙셋 배포 반영 (%d 규칙)" % len(got))


def apply_ratelimit(cf, zid, dry):
    """광고 실린 경로에 IP당 레이트 리밋.

    무료 플랜 제약(2026-11-16 실측, 오류 20155·period·mitigation):
      - characteristics 에 `cf.colo.id` 필수, `ip.src` 단독 불가
      - period 는 10초만 허용, mitigation_timeout 도 10만 허용
    정상 독자는 10초에 40회를 누르지 않으므로 임계값은 40회/10초(=4req/s)로 둔다.
    """
    body = {"rules": [{
        "action": "block",
        "enabled": True,
        "description": "adg: 광고 경로 과다 요청 차단 (IP 40회/10초)",
        "expression": "%s and not cf.client.bot" % AD_PATHS_RATE,
        "ratelimit": {"characteristics": ["ip.src", "cf.colo.id"], "period": 10,
                      "requests_per_period": 40, "mitigation_timeout": 10},
    }]}
    if dry:
        print("   ~ 레이트 리밋 1개 PUT (dry-run)")
        return
    try:
        cf.ok("PUT", "/zones/%s/rulesets/phases/http_ratelimit/entrypoint" % zid, body)
    except RuntimeError as e:
        print("   ! 레이트 리밋 실패(플랜 제한 가능): %s" % str(e)[:200])
        return
    got = (cf.ok("GET", "/zones/%s/rulesets/phases/http_ratelimit/entrypoint" % zid)
           or {}).get("rules") or []
    print("   ✓ 레이트 리밋 반영 (%d 규칙)" % len(got))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["audit", "apply"])
    ap.add_argument("--only", default="all",
                    choices=["all", "settings", "bot", "waf", "ratelimit"])
    ap.add_argument("--zone", default="", help="기본: 접근 가능한 전 존")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    tok, name = token()
    print("토큰: %s (값 비출력)" % name)
    cf = CF(tok)
    all_zones = zones(cf)
    if not all_zones:
        sys.exit("접근 가능한 존 없음 — 토큰 권한 확인")
    target = {a.zone: all_zones[a.zone]} if a.zone else all_zones
    for zname, zid in target.items():
        print("\n══ %s" % zname)
        if a.cmd == "audit":
            audit(cf, zid, zname)
            continue
        steps = ["settings", "bot", "waf", "ratelimit"] if a.only == "all" else [a.only]
        for step in steps:
            print(" [%s]" % step)
            {"settings": apply_settings, "bot": apply_bot,
             "waf": apply_waf, "ratelimit": apply_ratelimit}[step](cf, zid, a.dry_run)
        print(" ── 적용 후 상태")
        audit(cf, zid, zname)


if __name__ == "__main__":
    main()
