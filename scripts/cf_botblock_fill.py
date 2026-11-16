#!/usr/bin/env python3
"""AIK24-ADSENSE-BOTBLOCK-03 — 기존 커스텀 룰을 건드리지 않고 빈 자리만 채운다.

배경(2026-11-16): informationhot.kr / rotcha.kr / techpawz.com 에는 2026-10-22~23 의
`ADSENSE-BOTBLOCK-01/02` 커스텀 룰이 이미 있다(각 3·5·5개). 무료 플랜 커스텀 룰 상한은 5개라
새 룰을 밀어넣으려면 기존 룰을 지워야 하는데, 그건 이미 실측 근거로 튜닝된 규칙을 파괴한다.
그래서 이 스크립트는 **추가만** 한다.

채우는 것:
  1) Managed Free Ruleset 배포 (커스텀 룰 슬롯을 쓰지 않는다) — 세 존 모두 없음(2026-11-16 실측)
  2) 레이트 리밋 1개 (무료 플랜 1개 상한) — 광고 경로 과다 요청 차단
  3) informationhot.kr 처럼 커스텀 슬롯이 남은 존에 한해, rotcha 에서 이미 검증된
     bot-UA 하드블록 / bare-UA 챌린지를 이식

원칙:
  - 기존 룰 목록을 읽어 그대로 두고 **뒤에 append** 한다(삭제·수정 금지).
  - 같은 description 이 이미 있으면 건너뛴다(멱등).
  - `--dry-run` 기본. 실제 쓰기는 `--apply`.

사용:
  python3 scripts/cf_botblock_fill.py                       # 계획만(전 존)
  python3 scripts/cf_botblock_fill.py --apply               # 실행
  python3 scripts/cf_botblock_fill.py --apply --zone rotcha.kr
"""
import argparse
import json
import os
import sys

import httpx

API = "https://api.cloudflare.com/client/v4"
ENV_FILE = os.path.expanduser("~/.env.common")

# 보호 크롤러 — 이 서명이 있으면 어떤 룰도 건드리지 않는다(기존 룰들과 같은 원칙).
PROTECTED = ("Googlebot", "Mediapartners", "AdsBot", "google.com", "GoogleOther",
             "Google-InspectionTool", "bingbot", "bingpreview", "Yeti", "Daum",
             "facebookexternalhit", "Meta-ExternalFetcher", "Threads", "ClaudeBot",
             "Claude-SearchBot", "Applebot", "PetalBot")

# 브라우저가 절대 내지 않는 UA — rotcha ADSENSE-BOTBLOCK-02 룰2 와 동일 목록.
SERVER_UA = ("curl/", "wget/", "python-requests", "Go-http-client", "libwww-perl",
             "Apache-HttpClient", "PostmanRuntime", "node-fetch", "aiohttp",
             "nginx-ssl early hints", "tlm-scanner", "TLM-Audit-Scanner", "l9scan",
             "zgrab", "masscan", "nikto", "sqlmap", "nmap", "SemrushBot", "MJ12bot",
             "DotBot", "AhrefsBot", "DataForSeoBot", "ExaSearchBot", "ShapBot",
             "Hello from Palo Alto Networks")

BARE_UA_MARK = "AppleWebKit/537.36 (KHTML, like Gecko)"
BROWSER_TOKENS = ("Chrome/", "Chromium/", "Safari/", "Firefox/", "Edg/", "Edge/", "OPR/",
                  "SamsungBrowser/", "CriOS/", "FxiOS/", "UCBrowser/", "YaBrowser/",
                  "Vivaldi/", "Brave/", "Silk/", "Electron/", "Cobalt/", "Version/")

MANAGED_FREE_NAME = "Cloudflare Managed Free Ruleset"

# 레이트 리밋: 정적 자산은 제외하고, IP+콜로케이션당 10초에 40회까지.
# 무료 플랜은 레이트 리밋 식에서 `matches`(정규식) 연산자를 못 쓴다 — 실측 오류:
#   "the use of operator Matches is not allowed, an higher Advanced Rate Limiting plan is required"
# 그래서 정적 자산 디렉터리만 starts_with 로 제외하고, 임계값을 정상 사용자에게 안 걸리는
# 수준(100회/10초 = 10req/s)으로 둔다.
RL_EXPR = ('(not starts_with(http.request.uri.path, "/_astro/")) and '
           '(not starts_with(http.request.uri.path, "/assets/")) and '
           '(not starts_with(http.request.uri.path, "/static/")) and '
           '(not starts_with(http.request.uri.path, "/images/")) and '
           '(not starts_with(http.request.uri.path, "/fonts/")) and '
           '(not starts_with(http.request.uri.path, "/cdn-cgi/")) and not cf.client.bot')
RL_DESC = "adg: 광고 경로 과다 요청 차단 (IP 100회/10초)"


def load_env():
    if not os.path.exists(ENV_FILE):
        return
    for line in open(ENV_FILE, encoding="utf-8"):
        k, _, v = line.strip().partition("=")
        k = k.strip()
        if k and not k.startswith("#") and k not in os.environ:
            os.environ[k] = v.strip().strip('"').strip("'")


class CF:
    def __init__(self, tok):
        self.c = httpx.Client(base_url=API, timeout=30,
                              headers={"Authorization": "Bearer %s" % tok})

    def call(self, m, p, body=None):
        r = self.c.request(m, p, json=body)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"errors": [{"message": r.text[:150]}]}

    def ok(self, m, p, body=None):
        st, d = self.call(m, p, body)
        if not d.get("success"):
            raise RuntimeError("%s %s → %s %s" % (m, p, st, json.dumps(d.get("errors"))[:220]))
        return d.get("result")


def _any(field, values):
    return " or ".join('(%s contains "%s")' % (field, v) for v in values)


def bot_ua_rule(prefix):
    return {
        "action": "block", "enabled": True,
        "description": "%s-bot-UA-block" % prefix,
        "expression": "(%s) and (not cf.client.bot) and (not (%s))"
                      % (_any("http.user_agent", SERVER_UA), _any("http.user_agent", PROTECTED)),
    }


def bare_ua_rule(prefix):
    return {
        "action": "managed_challenge", "enabled": True,
        "description": "%s-bare-UA-challenge" % prefix,
        "expression": '(%s) and (not (%s)) and (not cf.client.bot) and (not (%s))'
                      % ('http.user_agent contains "%s"' % BARE_UA_MARK,
                         _any("http.user_agent", BROWSER_TOKENS),
                         _any("http.user_agent", PROTECTED)),
    }


def entrypoint(cf, zid, phase):
    st, d = cf.call("GET", "/zones/%s/rulesets/phases/%s/entrypoint" % (zid, phase))
    return (d.get("result") or {}) if d.get("success") else None


def fill_custom(cf, zid, prefix, dry, max_rules=5):
    ep = entrypoint(cf, zid, "http_request_firewall_custom")
    rules = list((ep or {}).get("rules") or [])
    have = {(r.get("description") or "") for r in rules}
    print("   커스텀 룰: %d/%d" % (len(rules), max_rules))
    for r in rules:
        print("      = %s" % (r.get("description") or "")[:60])
    if len(rules) >= max_rules:
        print("   · 슬롯 없음 — 추가 없음(기존 룰 보존)")
        return
    for rule in (bot_ua_rule(prefix), bare_ua_rule(prefix)):
        if rule["description"] in have:
            print("   = 이미 있음: %s" % rule["description"])
            continue
        if len(rules) >= max_rules:
            print("   ! 슬롯 부족 — %s 건너뜀" % rule["description"])
            continue
        if dry:
            print("   ~ 추가 예정: %s [%s]" % (rule["description"], rule["action"]))
            rules.append(rule)
            continue
        rules.append(rule)
        cf.ok("PUT", "/zones/%s/rulesets/phases/http_request_firewall_custom/entrypoint" % zid,
              {"rules": rules})
        print("   ✓ 추가: %s [%s]" % (rule["description"], rule["action"]))
    if not dry:
        got = (entrypoint(cf, zid, "http_request_firewall_custom") or {}).get("rules") or []
        print("   → 최종 커스텀 룰 %d개" % len(got))


def fill_managed(cf, zid, dry):
    ep = entrypoint(cf, zid, "http_request_firewall_managed")
    if ep and (ep.get("rules") or []):
        print("   = 관리 규칙셋 이미 배포(%d)" % len(ep["rules"]))
        return
    rs = cf.ok("GET", "/zones/%s/rulesets?per_page=50" % zid) or []
    free = next((r for r in rs if r.get("name") == MANAGED_FREE_NAME), None)
    if not free:
        print("   ! %s 없음" % MANAGED_FREE_NAME)
        return
    rule = {"action": "execute", "enabled": True, "expression": "true",
            "description": "adg: %s" % MANAGED_FREE_NAME,
            "action_parameters": {"id": free["id"]}}
    if dry:
        print("   ~ 관리 규칙셋 배포 예정 (%s)" % free["id"])
        return
    cf.ok("PUT", "/zones/%s/rulesets/phases/http_request_firewall_managed/entrypoint" % zid,
          {"rules": [rule]})
    got = (entrypoint(cf, zid, "http_request_firewall_managed") or {}).get("rules") or []
    print("   ✓ 관리 규칙셋 배포 (entrypoint 규칙 %d개)" % len(got))


def fill_ratelimit(cf, zid, dry):
    ep = entrypoint(cf, zid, "http_ratelimit")
    if ep and (ep.get("rules") or []):
        print("   = 레이트 리밋 이미 있음(%d)" % len(ep["rules"]))
        return
    rule = {"action": "block", "enabled": True, "description": RL_DESC,
            "expression": RL_EXPR,
            "ratelimit": {"characteristics": ["ip.src", "cf.colo.id"], "period": 10,
                          "requests_per_period": 100, "mitigation_timeout": 10}}
    if dry:
        print("   ~ 레이트 리밋 추가 예정 (100회/10초)")
        return
    st, d = cf.call("PUT", "/zones/%s/rulesets/phases/http_ratelimit/entrypoint" % zid,
                    {"rules": [rule]})
    if not d.get("success"):
        print("   ! 레이트 리밋 실패: %s" % json.dumps(d.get("errors"))[:160])
        return
    print("   ✓ 레이트 리밋 추가 (100회/10초)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--zone", default="")
    ap.add_argument("--token-env", default="CF_DNS_TOKEN")
    a = ap.parse_args()
    dry = not a.apply

    load_env()
    tok = os.environ.get(a.token_env, "").strip()
    if not tok:
        sys.exit("%s 없음" % a.token_env)
    cf = CF(tok)
    zones = {z["name"]: z["id"] for z in (cf.ok("GET", "/zones?per_page=50") or [])}
    targets = {a.zone: zones[a.zone]} if a.zone else zones
    print("토큰: %s (값 비출력) | %s" % (a.token_env, "DRY-RUN" if dry else "APPLY"))
    for name, zid in targets.items():
        print("\n══ %s" % name)
        fill_custom(cf, zid, "ADSENSE-BOTBLOCK-03", dry)
        fill_managed(cf, zid, dry)
        fill_ratelimit(cf, zid, dry)


if __name__ == "__main__":
    main()
