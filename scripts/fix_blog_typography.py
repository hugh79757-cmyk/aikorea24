#!/usr/bin/env python3
"""B-6 블로그 타이포그래피 재적용 (git 되돌림 복구용, 멱등).

[...id].astro 의 본문 컨테이너 클래스 블록과 h1 을 /news/ 기준으로 되돌린다.
- 본문 글자 20px (prose-xl)
- h1 빨간 버티컜 시그니처
- 표 테두리/패딩/헤더 음영
"""
import re
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "src/pages/blog/[...id].astro"
t = P.read_text(encoding="utf-8")
orig = t

# 1) 본문 컨테이너 클래스 블록 교체 (첫 클래스 속성만 통째로)
CLS = (
    'prose prose-container prose-xl max-w-none\n'
    '        prose-headings:text-[#111111]\n'
    '        prose-p:text-[#333333]\n'
    '        prose-strong:text-[#111111]\n'
    '        prose-a:text-[#111111] prose-a:underline prose-a:underline-offset-2 hover:prose-a:text-[#E63B2E]\n'
    '        prose-blockquote:text-[#555555] prose-blockquote:border-[#E63B2E]\n'
    '        prose-code:text-[#111111]\n'
    '        prose-pre:bg-[#fafafa]\n'
    '        prose-li:text-[#333333]\n'
    '        prose-img:rounded-xl\n'
    '        prose-hr:border-[#e5e5e5]\n'
    '        prose-th:text-[#111111]\n'
    '        prose-td:text-[#333333]\n'
    '        prose-table:w-full prose-table:my-8 prose-table:text-base prose-table:border-collapse\n'
    '        prose-th:border prose-th:border-[#e5e5e5] prose-th:bg-[#fafafa] prose-th:px-4 prose-th:py-2.5\n'
    '        prose-td:border prose-td:border-[#e5e5e5] prose-td:px-4 prose-td:py-2.5'
)
t = re.sub(r'<div id="prose-body" class="[^"]*">',
           f'<div id="prose-body" class="{CLS}">', t, count=1)

# 2) h1 빨간 버티컜
t = re.sub(
    r'<h1 class="text-3xl md:text-4xl font-bold[^"]*">',
    '<h1 class="text-3xl md:text-4xl font-bold text-[#111111] leading-tight mb-4"'
    ' style="border-left: 6px solid #E63B2E; padding-left: 24px;">',
    t, count=1,
)

P.write_text(t, encoding="utf-8")
print(f"  prose-xl: {t.count('prose prose-container prose-xl')}건")
print(f"  h1 버티컜: {t.count('border-left: 6px solid #E63B2E')}건")
print(f"  표 CSS: {t.count('prose-table:w-full')}건")
print("  변경됨" if t != orig else "  변화 없음")