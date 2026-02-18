path = "/Users/twinssn/Projects/aikorea24/api_test/news_collector.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

old = """def save_to_d1(articles):
    sql_lines = []
    skipped = 0"""

new = """def save_to_d1(articles):
    existing = get_existing()
    sql_lines = []
    skipped = 0"""

if old in code:
    code = code.replace(old, new, 1)
    print("✅ existing = get_existing() 추가")
else:
    print("⚠️ 못 찾음")

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
