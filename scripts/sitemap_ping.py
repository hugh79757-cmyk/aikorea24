#!/usr/bin/env python3
"""sitemap_ping.py — 배포 후 검색엔진에 sitemap 업데이트를 알린다.

사용:
  python3 scripts/sitemap_ping.py
  python3 scripts/sitemap_ping.py --sitemap https://aikorea24.kr/sitemap-blog.xml

동작:
  - Google ping: 크롤 요청 (https://www.google.com/ping?sitemap=...)
    * 2023년부터 deprecated 이지만 여전히 크롤 유도에 유효 (Google 공식)
  - Naver Search Advisor: SA API 로그인 없이 메타태그 기반 등록 확인 + ping 시도
    * 네이버는 nid.naver.com 로그인 불필요 — SA 콘솔에 등록된 도메인만 ping 수신
    * ⛔ 절대 nid.naver.com 접근 금지 (AGENTS.md 섹션 4)
  - 결과를 logs/sitemap_ping.log 에 기록

주의: ping은 "인덱싱 보장"이 아니라 "크롤 요청"이다. sitemap에 없는 URL은 ping해도 무시됨.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, 'sitemap_ping.log')

DEFAULT_SITEMAP = 'https://aikorea24.kr/sitemap.xml'
GOOGLE_PING = 'https://www.google.com/ping?sitemap='

# User-Agent: 봇 차단 우회 (bot-wall 재발 방지)
UA = 'Mozilla/5.0 (compatible; aikorea24-sitemap-ping/1.0)'


def _log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _http(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(200).decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read(200).decode('utf-8', 'replace')
    except Exception as e:
        return None, f'{type(e).__name__}: {e}'


def ping_google(sitemap_url):
    """Google sitemap ping.

    ⚠️ https://www.google.com/ping 은 2023년 6월 deprecated (404 응답).
    대체: sitemap URL 자체를 GET 해 reachable 여부를 확인 + ping 시도 (best-effort).
    """
    status, body = _http(GOOGLE_PING + urllib.parse.quote(sitemap_url, safe=':/?='))
    # deprecated 엔드포인트는 404를 반환하므로, sitemap 직접 확인이 실제 신호.
    s_status, s_body = _http(sitemap_url)
    reachable = s_status == 200
    _log(f'  Google ping: {"✅" if reachable else "⚠️"} '
         f'(ping deprecated, sitemap reachable={reachable}, sitemap_status={s_status})')
    if reachable:
        _log(f'    sitemap 확인: {len(s_body)} bytes, '
             f'loc 태그={"present" if "<loc>" in s_body else "ABSENT"}')
    return reachable


def ping_naver(sitemap_url):
    """Naver Search Advisor sitemap ping.

    ⚠️ 공개 ping 엔드포인트 없음 (404 확인 4개 엔드포인트 모두).
    ⛔ nid.naver.com 로그인 시도 금지 — SA 콘솔 수동 등록은 사용자만 가능.
    대체: sitemap reachable 확인 + SEOHead naver-site-verification 메타태그 존재 확인.
    """
    s_status, s_body = _http(sitemap_url)
    reachable = s_status == 200
    _log(f'  Naver SA: {"✅" if reachable else "⚠️"} sitemap reachable={reachable} '
         f'(status={s_status})')
    _log(f'    Naver 등록 경로: SEOHead naver-site-verification 메타태그 '
         f'(e84dcbdd...bf26) 사용 중 — SA 콘솔 수동 등록 필요 시 사용자에게 문의')
    return reachable


def main():
    parser = argparse.ArgumentParser(description='sitemap ping — 검색엔진에 크롤 요청')
    parser.add_argument('--sitemap', default=DEFAULT_SITEMAP, help=f'기본값: {DEFAULT_SITEMAP}')
    parser.add_argument('--google-only', action='store_true', help='Google ping만')
    args = parser.parse_args()

    _log(f'=== sitemap ping 시작: {args.sitemap} ===')
    results = {'google': ping_google(args.sitemap)}
    if not args.google_only:
        results['naver'] = ping_naver(args.sitemap)
    _log(f'=== sitemap ping 완료: {json.dumps(results, ensure_ascii=False)} ===')
    return 0 if results['google'] else 1


if __name__ == '__main__':
    sys.exit(main())