"""aikorea24 푸터에 뉴스 키워드 인사이트 Pro 추가"""

filepath = "/Users/twinssn/Projects/aikorea24/src/layouts/Layout.astro"

with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

old = '            <li><a href="https://cert.aikorea24.kr" target="_blank" class="hover:text-gray-900 dark:hover:text-white transition-colors">AI 자격증</a></li>'

new = '''            <li><a href="https://cert.aikorea24.kr" target="_blank" class="hover:text-gray-900 dark:hover:text-white transition-colors">AI 자격증</a></li>
            <li><a href="https://8.informationhot.kr" target="_blank" class="hover:text-gray-900 dark:hover:text-white transition-colors">뉴스 키워드 인사이트 Pro</a></li>'''

if old in code:
    code = code.replace(old, new, 1)
    print("✅ 푸터에 뉴스 키워드 인사이트 Pro 추가")
else:
    print("⚠️ 삽입 위치 못 찾음")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)
