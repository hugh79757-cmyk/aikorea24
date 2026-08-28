#!/usr/bin/env python3
import os, sys, json, re, time
from urllib.parse import urlparse

MODEL = os.environ.get("EXTRACTOR_MODEL", "gpt-4o-mini")
MAX_BODY = 12000
TIMEOUT = 20

SYSTEM_PROMPT = """당신은 뉴스 기사에서 사실만 추출하는 추출기다. 요약하지 않는다. 기사 본문에 문자 그대로 존재하는 정보만 아래 스키마로 추출한다.

[출력 스키마 — JSON object]
{
  "A": "사건 핵심 1문장 요약 (50자 이내)",
  "B": [
    {
      "metric": "수치 또는 핵심 사실 (예: 50dB, 400명, 14.99달러)",
      "condition": "한정어 — 출처 기관, 대상, 범위, 기간, 측정 조건. 본문에 명시된 것만. 없으면 null",
      "evidence_sentence": "이 수치가 나온 기사 본문 문장을 문자 그대로 복사"
    }
  ],
  "C": [
    {
      "text": "인용문 — 기사 본문에서 따옴표 안 문자열을 한 글자도 바꾸지 않고 복사",
      "speaker": "화자 이름 또는 직함 (본문 명시분만, 없으면 null)",
      "attribution": "화자의 소속/역할 (본문 명시분만, 없으면 null)",
      "condition": "인용이 나온 맥락 (회의, 인터뷰, 성명서 등). 없으면 null"
    }
  ],
  "D": "배경 맥락 — 이 사건을 이해하는 데 필요한 배경 사실 2~3문장. 본문 기반만.",
  "E": ["핵심 키워드 3개"],
  "F": "사건 시점 — 본문에 명시된 날짜/시각 (예: 오늘 오전 8시 37분). 상대 표현이면 발행일 기준으로 환산하되, 환산 근거를 괄호로 표기. 없으면 '명시되지 않음'"
}

[절대 규칙]
1. B의 수치는 숫자+단위+조건이 세트다. condition을 찾을 수 없는 수치는 B에서 제외한다. metric만 달랑 있는 항목 금지.
2. C의 인용문은 반드시 본문에 따옴표로 표시된 직접 인용만 사용한다. 간접 인용("~라고 밝혔다"만 있는 문장)은 C에 넣지 않는다. 요약·번역 톤 변경·두 문장 합치기 금지.
3. B는 최대 6개, C는 최대 4개까지. 기사에 등장하는 순서대로 배치하고, 그 이후는 버린다.
4. B 최소 1개, C 최소 1개를 만족하지 못하면 추출 실패로 간주하고 {"error": "insufficient_facts", "B": [...], "C": [...]} 형태로 지금까지 모은 것만 반환한다. 없는 사실을 지어내서 개수를 채우는 것은 절대 금지다.
5. 모든 필드는 기사 본문에 근거가 있어야 한다. 일반 지식, 추론, 평가 문구("~구조이다", "~우려된다" 류의 해석)는 어떤 필드에도 넣지 않는다.
6. 날짜와 연도는 본문 명시분과 제공된 발행일만 사용한다. 파라메트릭 지식으로 연도를 추정하지 않는다."""

def eprint(*a, **kw): print(*a, file=sys.stderr, **kw)

def crawl(url):
    body = None; title = None; pub_date = None
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            md = trafilatura.metadata.extract_metadata(downloaded)
            if md:
                title = md.title
                pub_date = md.date
            body = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    except ImportError:
        eprint("trafilatura not installed: pip install trafilatura")
        sys.exit(1)
    except Exception as ex:
        eprint(f"trafilatura error: {ex}")

    if not body or len(body) < 500:
        try:
            import requests
            from bs4 import BeautifulSoup
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            if not title:
                t = soup.find("title")
                if t: title = t.get_text(strip=True)
            if not pub_date:
                m = soup.find("meta", {"property": "article:published_time"})
                if m and m.get("content"): pub_date = m["content"]
                else:
                    m = soup.find("meta", {"property": "og:published_time"})
                    if m and m.get("content"): pub_date = m["content"]
                    else:
                        tt = soup.find("time")
                        if tt and tt.get("datetime"): pub_date = tt["datetime"]
                        elif tt: pub_date = tt.get_text(strip=True)
            candidates = []
            for sel in ["article", "main"]:
                el = soup.find(sel)
                if el:
                    txt = el.get_text("\n", strip=True)
                    if len(txt) > 500: candidates.append(txt)
            if not candidates:
                ps = soup.find_all("p")
                txt = "\n".join(p.get_text(strip=True) for p in ps if len(p.get_text(strip=True))>20)
                if len(txt) > 500: candidates.append(txt)
            if candidates:
                fb = max(candidates, key=len)
                if not body or len(fb) > len(body):
                    body = fb
        except Exception as ex:
            eprint(f"fallback crawl error: {ex}")

    if body and len(body) < 500:
        eprint(f"warning: body too short ({len(body)} chars)")
    # normalize pub_date to YYYY-MM-DD
    pd = None
    if pub_date:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", str(pub_date))
        if m: pd = m.group(1)
        else:
            try:
                from dateutil.parser import parse as dparse
                pd = dparse(str(pub_date)).strftime("%Y-%m-%d")
            except: pd = str(pub_date)[:10]
    return (body or ""), title, pd

def normalize(s): return re.sub(r"\s+", " ", s).strip()

def call_openai(body, title, pub_date):
    snippet = body[:MAX_BODY]
    pub_str = f"기사 발행일: {pub_date}" if pub_date else "기사 발행일: 알 수 없음"
    user_msg = f"기사 제목: {title or '알 수 없음'}\n{pub_str}\n\n기사 본문:\n{snippet}"
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    # 1) try project fallback chain (free LLM chain) — no OpenAI required
    try:
        import pathlib as _pl
        sys.path.insert(0, str(_pl.Path(__file__).resolve().parent / "scripts" / "threads"))
        sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
        from v3.model_router import chat_completion as _cc
        return _cc(msgs, max_tokens=3000, temperature=0.2, response_format={"type": "json_object"})
    except Exception as ex:
        eprint(f"fallback chain failed, trying direct OpenAI: {ex}")
    # 2) direct OpenAI fallback
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        eprint("OPENAI_API_KEY not set and fallback chain unavailable")
        sys.exit(1)
    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": msgs,
    }
    import requests
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(2):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                j = r.json()
                return j["choices"][0]["message"]["content"]
            last_err = f"{r.status_code} {r.text[:500]}"
            eprint(f"openai error: {last_err} (attempt {attempt+1})")
        except Exception as ex:
            last_err = str(ex)
            eprint(f"openai exception: {ex} (attempt {attempt+1})")
        time.sleep(1)
    eprint(f"openai failed after retry: {last_err}")
    sys.exit(1)

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h","--help"):
        eprint("Usage: python standalone_extractor.py <기사_URL> [--output af.json]")
        sys.exit(1)
    url = sys.argv[1]
    out = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx+1 < len(sys.argv): out = sys.argv[idx+1]

    body, title, pub_date = crawl(url)
    if not body:
        eprint("crawl failed: empty body")
        sys.exit(1)

    raw = call_openai(body, title, pub_date)
    try:
        data = json.loads(raw)
    except:
        # try extract json block
        m = re.search(r"\{.*\}", raw, re.S)
        if m: data = json.loads(m.group(0))
        else:
            eprint(f"json parse failed: {raw[:500]}")
            sys.exit(1)

    # if error shape with B/C, keep but still wrap
    if "A" not in data and "error" in data:
        # insufficient_facts case
        result = {
            "title": title,
            "pub_date": pub_date,
            "source_url": url,
            **data,
            "D": data.get("D",""),
            "E": data.get("E",[]),
            "F": data.get("F",""),
        }
    else:
        result = {
            "title": title,
            "pub_date": pub_date,
            "source_url": url,
            "A": data.get("A",""),
            "B": data.get("B",[])[:6],
            "C": data.get("C",[])[:4],
            "D": data.get("D",""),
            "E": data.get("E",[])[:3],
            "F": data.get("F",""),
        }
        if "error" in data:
            result["error"] = data["error"]

    # verification
    norm_body = normalize(body)
    def is_sub(txt):
        if not txt: return False
        return normalize(txt) in norm_body

    b_verified = []
    for b in result.get("B",[]):
        ev = b.get("evidence_sentence","")
        b_verified.append(is_sub(ev) if ev else False)
    c_verified = []
    for c in result.get("C",[]):
        txt = c.get("text","")
        c_verified.append(is_sub(txt) if txt else False)

    # insufficient facts -> error shape per spec (fallback if LLM didnt emit error)
    if "error" not in result and (len(result.get("B",[]))<1 or len(result.get("C",[]))<1):
        result["error"]="insufficient_facts"
    warning = None
    if "error" in result:
        warning = f"insufficient_facts B{len(result.get(chr(66),[]))} C{len(result.get(chr(67),[]))}"
    if len(body) < 500:
        warning = f"short body {len(body)}"
    if any(not v for v in b_verified):
        warning = (warning + "; " if warning else "") + "B evidence not in body"
    if any(not v for v in c_verified):
        warning = (warning + "; " if warning else "") + "C text not in body"

    result["_meta"] = {
        "body_length": len(body),
        "B_count": len(result.get("B",[])),
        "C_count": len(result.get("C",[])),
        "B_verified": b_verified,
        "C_verified": c_verified,
        "warning": warning,
    }

    out_str = json.dumps(result, ensure_ascii=False, indent=2)
    if out:
        open(out, "w", encoding="utf-8").write(out_str)
    else:
        print(out_str)

if __name__ == "__main__":
    main()
