"""AIK24-ADSBLANK-02 회귀 — 미들웨어 CSP 가 애드센스 광고 스택을 막아
두 번째 광고 유닛 요청이 죽던 결함(2026-10-18 실측)의 재발 방지.

배경(실측 근거):
  · 현행 CSP        → /tools/ 단위 슬롯 요청 1건(상단 ady=81)만 발생, 하단 슬롯은
                      data-adsbygoogle-status=done 인데도 요청 0건, 280×280 빈 공간.
  · fundingchoicesmessages.google.com 를 script-src 에 허용
                    → 단위 슬롯 요청 2건(ady=81 + ady=4285), 하단 슬롯 unfill-optimized 전환.
  · ep2.adtrafficquality.google / tpc.googlesyndication.com 추가는 요청 건수에 영향 없음.

따라서 이 테스트는 "광고 스택 호스트가 CSP 에 있는지"만 고정한다(문자열 계약).
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MIDDLEWARE = ROOT / "src" / "middleware.ts"


def _csp() -> str:
    src = MIDDLEWARE.read_text(encoding="utf-8")
    m = re.search(r"'Content-Security-Policy':\s*\"([^\"]+)\"", src)
    assert m, "src/middleware.ts 에서 Content-Security-Policy 문자열을 찾지 못했다"
    return m.group(1)


def _directive(csp: str, name: str) -> str:
    for part in csp.split(";"):
        t = part.strip()
        if t == name or t.startswith(name + " "):
            return t
    return ""


def test_script_src_allows_fundingchoicesmessages():
    """이 호스트가 빠지면 2번째 광고 유닛 요청이 나가지 않는다(2026-10-18 실측)."""
    script_src = _directive(_csp(), "script-src")
    assert "https://fundingchoicesmessages.google.com" in script_src, (
        "script-src 에 fundingchoicesmessages.google.com 이 없다 — 하단 광고 슬롯 요청이 죽는다"
    )


def test_script_src_allows_adsense_loader():
    script_src = _directive(_csp(), "script-src")
    assert "https://pagead2.googlesyndication.com" in script_src, "애드센스 로더 호스트가 CSP 에 없다"


def test_frame_src_allows_ad_iframes():
    frame_src = _directive(_csp(), "frame-src")
    for host in ("https://googleads.g.doubleclick.net", "https://pagead2.googlesyndication.com"):
        assert host in frame_src, f"frame-src 에 {host} 가 없다 — 광고 iframe 이 차단된다"


def test_connect_src_allows_ad_request_host():
    connect_src = _directive(_csp(), "connect-src")
    assert "https://googleads.g.doubleclick.net" in connect_src, (
        "connect-src 에 googleads.g.doubleclick.net 이 없다 — 광고 요청(/pagead/ads)이 차단된다"
    )


def test_csp_keeps_default_deny_baseline():
    """기존 보안 기준선(default-src 'self')은 유지되어야 한다."""
    csp = _csp()
    assert _directive(csp, "default-src") == "default-src 'self'", "default-src 기준선이 바뀌었다"
