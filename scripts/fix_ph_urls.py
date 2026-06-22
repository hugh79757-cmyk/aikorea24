#!/usr/bin/env python3
"""
기존 툴의 Product Hunt URL을 실제 툴 URL로 수정
"""
import os
import re
import urllib.request
from pathlib import Path

PROJECT_DIR = Path('/Users/twinssn/Projects/aikorea24')
TOOLS_DIR = PROJECT_DIR / 'src' / 'content' / 'tools'


def resolve_url(url: str) -> str:
    """Product Hunt URL → 실제 툴 URL"""
    # 리다이렉트 URL인 경우
    if 'producthunt.com/r/p/' in url:
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'aikorea24-bot/2.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.url
        except Exception as e:
            print(f"  리다이렉트 실패: {e}")
            return url
    
    # Product Hunt 제품 페이지인 경우
    if 'producthunt.com/products/' in url:
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'aikorea24-bot/2.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8')
                # 외부 링크 찾기 (Product Hunt가 아닌 URL)
                external_links = re.findall(
                    r'href="(https?://(?!www\.producthunt\.com)[^"]+)"',
                    html
                )
                # ref=producthunt가 포함된 링크 우선
                for link in external_links:
                    if 'ref=producthunt' in link:
                        return link.split('?')[0]  # 쿼리 파라미터 제거
                # 없으면 첫 번째 외부 링크
                if external_links:
                    return external_links[0].split('?')[0]
        except Exception as e:
            print(f"  페이지 fetch 실패: {e}")
    
    return url


def fix_tool_urls():
    """Product Hunt URL을 가진 툴들의 URL 수정"""
    fixed = 0
    skipped = 0
    
    for md_file in TOOLS_DIR.glob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        
        # frontmatter에서 url 추출
        url_match = re.search(r'^url:\s*"([^"]+)"', content, re.MULTILINE)
        if not url_match:
            continue
        
        url = url_match.group(1)
        
        # Product Hunt URL이 아닌 경우 스킵
        if 'producthunt.com/products/' not in url:
            skipped += 1
            continue
        
        print(f"수정 대상: {md_file.name}")
        print(f"  현재 URL: {url}")
        
        # 리다이렉트 따라가기
        new_url = resolve_url(url)
        
        if new_url == url:
            print(f"  리다이렉트 실패, 스킵")
            skipped += 1
            continue
        
        print(f"  새 URL: {new_url}")
        
        # 파일 수정
        new_content = content.replace(f'url: "{url}"', f'url: "{new_url}"')
        md_file.write_text(new_content, encoding='utf-8')
        fixed += 1
        print(f"  수정 완료")
    
    print(f"\n결과: {fixed}개 수정, {skipped}개 스킵")


if __name__ == '__main__':
    fix_tool_urls()
