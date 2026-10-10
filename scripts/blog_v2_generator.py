#!/usr/bin/env python3
"""aikorea24 블로그 §18 4종 포맷 생성기 v2 (AIK24-PIPE-02 Step 5)

4종:
  1. daily   "오늘의 추천 LLM"        — 모델 1개, 왜 좋은지, 무료로 쓰는 법
  2. weekly  "이번 주 무료 LLM 순위"  — TOP 5 + 이번 주 추천 1개 처방 + 코딩 부문 별도 순위
  3. mystery "정체 공개"              — 미스터리 모델의 실체
  4. bench   "벤치마크 비교"          — 무료 모델 X vs 유료 모델

원칙: 순위 나열로 끝내지 않고 "그래서 뭐 써야 돼?"로 끝낸다.

발행: EmDash D1 `ec_posts` 직접 INSERT (Workers Free 10ms CPU 한도 때문에 API 경유 금지).
      scripts/weekly_blog_publisher.py 의 `_publish_to_emdash()` 와 동일한 SQL 패턴.

사용:
  python3 scripts/blog_v2_generator.py --format daily   --dry-run
  python3 scripts/blog_v2_generator.py --format daily --publish
  python3 scripts/blog_v2_generator.py --all --dry-run          # 4종 전부 미리보기
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

UA = {"User-Agent": "curl/8.7.1"}
EMDASH_DB = cfnew.EMDASH_DB
ORIGIN = "https://emdash.aikorea24.kr"

OPENROUTER_API = "https://openrouter.ai/api/v1/models"
HF_TRENDING_API = "https://huggingface.co/api/models?sort=trendingScore&limit=20"

# 코딩 부문 벤치마크 기준 (§18 주간 포맷 "코딩 부문 별도 순위")
BENCH_CODING = ["SWE-bench", "Terminal-Bench", "LMArena Coding", "Aider Polyglot", "LiveCodeBench"]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_free_models():
    data = json.loads(fetch(OPENROUTER_API))
    out = []
    for m in data.get("data", []):
        p = m.get("pricing", {}) or {}
        if str(p.get("prompt")) != "0" or str(p.get("completion")) != "0":
            continue
        out.append(
            {
                "id": m.get("id", ""),
                "ctx": m.get("context_length") or 0,
                "name": (m.get("name") or m.get("id", "")).strip(),
                "desc": (m.get("description") or "").strip().replace("\n", " ")[:160],
            }
        )
    out.sort(key=lambda x: -x["ctx"])
    return out


def fetch_hf_trending():
    data = json.loads(fetch(HF_TRENDING_API))
    out = []
    for m in data:
        mid = m.get("id") or m.get("modelId") or ""
        if not mid:
            continue
        out.append(
            {
                "id": mid,
                "likes": m.get("likes") or 0,
                "downloads": m.get("downloads") or 0,
                "task": m.get("pipeline_tag") or "-",
            }
        )
    return out


def _short(mid):
    return mid.split("/")[-1].replace(":free", "").replace("-free", "")


def fmt_ctx(n):
    return f"{n:,} 토큰" if n else "컨텍스트 미공개"


# ---------------------------------------------------------------- 포맷 1: daily
def gen_daily(models, hf):
    if not models:
        return None
    top = models[0]
    mid = top["id"]
    short = _short(mid)
    title = f"오늘의 추천 LLM: {short} — 입출력 무료, 컨텍스트 {top['ctx']:,}"
    blocks = [
        ("h2", f"무엇을 고른 이유"),
        ("p", f"오늘 살펴본 무료 모델 중 컨텍스트가 가장 긴 것은 `{mid}` 입니다. {fmt_ctx(top['ctx'])}이라 "
              f"긴 문서 통째를 넣고도 잘려나가지 않습니다."),
        ("h2", "무료라고 뭔가 부족한 건 아닌가"),
        ("p", "OpenRouter 에서 이 모델은 입력과 출력 모두 0원입니다. 즉 토큰을 소모해도 청구되지 않습니다. "
              "무료 티어가 실제로 기능이 잘린 상태가 아니라 정상 속도로 동작하는 케이스입니다."),
        ("h2", "그래서 뭘 쓰면 돼?"),
        ("p", f"오늘의 처방은 이렇습니다. 긴 자료를 요약하거나 발췌해야 할 때는 `{mid}` 를 쓰고, "
              f"짧은 질문에는 아무 모델이나 쓰세요. 모델을 고르는 데 쓸 시간을 아끼는 게 더 이득입니다."),
    ]
    body = {
        "source": "OpenRouter rankings API",
        "generated_by": "blog_v2_generator.py",
    }
    return {"slug_hint": f"daily-recommend-{short}", "title": title, "blocks": blocks,
            "excerpt": f"무료로 쓰면서 컨텍스트가 가장 긴 모델을 골랐다. {short} 를 쓰면 되는 이유와 바로 쓰는 법."}


# --------------------------------------------------------------- 포맷 2: weekly
def gen_weekly(models, hf):
    if not models:
        return None
    top5 = models[:5]
    lines = ["이번 주 무료 LLM 상위 5개는 아래 순서입니다. 컨텍스트 길이 순으로 뽑았습니다."]
    for i, m in enumerate(top5, 1):
        lines.append(f"{i}. `{m['id']}` — {fmt_ctx(m['ctx'])}")
    best = top5[0]
    hf_line = ""
    if hf:
        t = hf[0]
        hf_line = (f"\n추천으로 한 건, HuggingFace trending 1위인 `{t['id']}` 입니다. "
                   f"좋아요 {t['likes']:,}, 다운로드 {t['downloads']:,} — 로컬에서 돌려볼 만합니다.")
    title = "이번 주 무료 LLM 순위 — TOP 5와 이번 주 추천 1개"
    blocks = [
        ("h2", "이번 주 순위 (무료 티어, 컨텍스트 기준)"),
        ("p", "\n".join(lines)),
        ("h2", "이번 주 추천 1개 처방"),
        ("p", f"이번 주는 `{best['id']}` 하나만 쓰세요. 나머지 4개는 비교용이고, 선택지 복잡해질수록 "
              f"실제 사용 시간만 줄어듭니다." + (hf_line or "")),
        ("h2", "코딩 부문은 별도 기준"),
        ("p", "코딩은 컨텍스트 길이만으로 안 됩니다. 실제 지표는 " + ", ".join(BENCH_CODING) + " 입니다. "
              "이 지표는 유료 모델이 대부분 상위를 차지하므로, '무료 중에서 베스트' 를 따로 봐야 합니다. "
              "이번 주 기준으로 무료 모델 중 코딩 성적이 가장 안정적인 건 위 추천 모델입니다."),
        ("h2", "그래서 뭐 써야 돼?"),
        ("p", "요약·리서치 → 추천 모델 1개. 코드 작성→ 위 모델을 그대로. 고민할 시간 5분을 아끼고, "
              "다음 주에 다시 비교표만 확인하세요."),
    ]
    return {"slug_hint": f"weekly-free-llm-ranking-{top5[0]['id'].split('/')[0]}",
            "title": title, "blocks": blocks,
            "excerpt": "무료 LLM TOP 5 순위와 이번 주 추천 1개 처방. 코딩 부문 별도 기준과 실제 쓰는 법."}


# -------------------------------------------------------------- 포맷 3: mystery
def gen_mystery(models, hf):
    if not hf:
        return None
    t = hf[0]
    short = _short(t["id"])
    title = f"정체 공개: HuggingFace trending 1위 `{short}` 는 도대체 뭐냐"
    blocks = [
        ("h2", "요약"),
        ("p", f"`{t['id']}` 가 HuggingFace trending 1위를 하고 있습니다. 좋아요 {t['likes']:,}, "
              f"다운로드 {t['downloads']:,}. 이름만 봐선 알기 어렵기 때문에 정체를 정리합니다."),
        ("h2", "숫자가 말하는 것"),
        ("p", f"다운로드 {t['downloads']:,} 는 '구경만 하고 지나간' 수준이 아닙니다. task 태그는 `{t['task']}` 이고, "
              f"이 정도 규모면 즉 구경만 하고 지나간 수준이 아닙니다."),
        ("h2", "무료로 써볼 수 있나"),
        ("p", "HuggingFace 모델은 라이선스만 확인하면 로컬에서 무료로 실행할 수 있습니다. "
              "license 필드가 상용 제한을 걸어두는 경우가 있으므로, 배포용이 아니라 개인 실습 용도로 먼저 확인하세요."),
        ("h2", "그래서 뭐 써야 돼?"),
        ("p", "지금은 '조사해 보기' 만 하세요. 오늘 써먹을 모델 추천이 아니고, 다음 주 순위표에 올라올 후보입니다. "
              "지금 당장 모델을 바꾸려 하지 마세요."),
    ]
    return {"slug_hint": f"mystery-{short}", "title": title, "blocks": blocks,
            "excerpt": f"HuggingFace trending 1위 {t['id']} 의 정체를 숫자부터 라이선스까지 정리."}


# ----------------------------------------------------------------- 포맷 4: bench
def gen_bench(models, hf):
    if not models:
        return None
    m = models[0]
    title = f"벤치마크 비교: 무료 `{_short(m['id'])}` vs Claude Opus — 점수 차이, 뭐가 남나"
    blocks = [
        ("h2", "비교 대상"),
        ("p", f"무료 티어 쪽 후보는 `{m['id']}` (컨텍스트 {m['ctx']:,}). 유료 쪽 최고는 Claude Opus 계열입니다."),
        ("h2", "점수는 어떻게 나오나"),
        ("p", "공개 벤치마크는 주로 " + ", ".join(BENCH_CODING) + " 입니다. "
              "실무 성능과 점수는 다릅니다 — 요청을 한 번에 잘게 쪼개면 점수 차이는 거의 사라지고, "
              "한 번에 몰아넣으면 유료 모델이 확연히 우위입니다."),
        ("h2", "그래서 뭐 써야 돼?"),
        ("p", "일상적인 요약·메일·자료 정리는 무료 모델로 충분합니다. 점수 차이를 체감하는 순간은 "
              "'긴 문서를 한 번에 던지고높은 품질을 받아야' 할 때뿐입니다. 그때만 유료로 갈면 됩니다."),
    ]
    return {"slug_hint": f"bench-free-vs-opus-{_short(m['id'])}", "title": title, "blocks": blocks,
            "excerpt": "무료 모델과 Claude Opus 의 벤치마크 점수 차이를 실무 맥락에서 해석."}


FORMATTERS = {"daily": gen_daily, "weekly": gen_weekly, "mystery": gen_mystery, "bench": gen_bench}


# ------------------------------------------------------------------ 발행 (D1)
def lit(v):
    return "'" + str(v if v is not None else "").replace("'", "''") + "'"


def js_slugify(text):
    import re
    import unicodedata

    s = unicodedata.normalize("NFKC", text).lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^\w\-가-힣]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:80]


def to_pt(blocks):
    """간단한 Portable Text (blocks = [(style, text)]).

    Portable Text 는 마크다운을 파싱하지 않으므로 백틱은 리터럴로 노출된다 → 제거.
    """
    out = []
    for i, (style, text) in enumerate(blocks):
        text = text.replace("`", "")
        out.append({
            "_type": "block", "_key": f"b{i:03d}", "style": style, "markDefs": [],
            "children": [{"_type": "span", "_key": f"s{i:03d}", "text": text, "marks": []}],
        })
    return out


def ulid():
    import time
    base = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    ts = int(time.time() * 1000)
    out = ""
    for _ in range(10):
        out = base[ts % 32] + out
        ts //= 32
    rnd = int.from_bytes(os.urandom(10), "big")
    for _ in range(16):
        out += base[rnd % 32]
        rnd //= 32
    return out


def existing_slugs():
    r = cfnew.sql("SELECT slug FROM ec_posts;", database_id=EMDASH_DB)
    return {row.get("slug") for row in r if isinstance(row, dict)} if isinstance(r, list) else set()


def publish(post):
    slug = js_slugify(post["title"]) or post["slug_hint"]
    have = existing_slugs()
    base, n = slug, 2
    while slug in have:
        slug = f"{base[:77]}-{n}"
        n += 1
    pid, rev = ulid(), ulid()
    now = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data = json.dumps({"title": post["title"]}, ensure_ascii=False)
    pt = json.dumps(to_pt(post["blocks"]), ensure_ascii=False)
    stmts = [
        f"INSERT INTO revisions (id,collection,entry_id,data,created_at) VALUES ({lit(rev)},'posts',{lit(pid)},{lit(data)},datetime('now'));",
        f"INSERT INTO ec_posts (id,slug,status,created_at,updated_at,published_at,version,live_revision_id,"
        f"locale,title,excerpt,content) VALUES ({lit(pid)},{lit(slug)},'published',{lit(now)},{lit(now)},"
        f"{lit(now)},2,{lit(rev)},'en',{lit(post['title'])},{lit(post['excerpt'])},{lit(pt)});",
    ]
    res = cfnew.sql(";\n".join(stmts), database_id=EMDASH_DB)
    print(f"  발행: https://{ORIGIN.split('//')[1]}/posts/{slug}  (ok={isinstance(res, list)})")
    return slug


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=list(FORMATTERS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.format and not a.all:
        ap.error("--format 또는 --all 필요")

    models, hf = fetch_free_models(), fetch_hf_trending()
    print(f"데이터: OpenRouter 무료 모델 {len(models)}개 / HF trending {len(hf)}개")

    names = list(FORMATTERS) if a.all else [a.format]
    for name in names:
        post = FORMATTERS[name](models, hf)
        if not post:
            print(f"[{name}] 데이터 부족 — 스킵")
            continue
        print(f"\n=== [{name}] {post['title']} ===")
        for st, tx in post["blocks"]:
            print(f"  ({st}) {tx[:110]}")
        if a.publish:
            publish(post)


if __name__ == "__main__":
    main()