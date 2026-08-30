import json, sys, os
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from scripts.deep_dive_writer import write_deep_dive
from scripts.weekly_blog_publisher import publish_blog_post

cands = json.load(open("tmp_test/weekly_candidates.json", encoding="utf-8"))
for i in (0, 1):
    c = cands[i]
    print(f"\n=== candidate[{i}] topic={c.get('topic')!r} ===")
    dive = write_deep_dive(c)
    if not dive:
        print("  write_deep_dive returned None")
        continue
    print("  title:", dive["title"])
    print("  verdict:", dive.get("quality_judgment", {}).get("verdict"))
    print("  body_len:", len(dive["body"]))
    path = publish_blog_post(dive)
    print("  saved:", path)
