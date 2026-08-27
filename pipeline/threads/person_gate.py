#!/usr/bin/env python3
"""person_gate — 인물 게이트 (LLM 단일 호출).

기존 파이프라인(auto_news_selector 선별 → crawler 본문)에 직결:
  crawler 성공 직후 / standalone_extractor 직전에 person_gate 호출.
  pass=True → 기존 extractor(kicker7) 흐름 진입.
  pass=False → 로그 "person_gate: no person story" 후 kicker7 건너뛰기.

판정 조건(3개 모두 만족 시 pass):
  1) 이름 있는 비관료 당사자 존재 (person="이름(역할)")
  2) 그 사람의 직접 인용(본문 따옴표) 존재
  3) 그 사람에게 구체적 대가 존재 (해고/실직/피해/손해/소송/감원/일자리 상실/처벌/형사 charge 등)
"""
import json
import re
import sys
from pathlib import Path

# v3.model_router (무료 LLM 폴백체인) 해상화 — standalone_extractor와 동일 방식
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts" / "threads"))
from v3.model_router import chat_completion  # noqa: E402

GATE_SYSTEM = """당신은 뉴스 기사에서 '이름 있는 비관료 당사자'가 등장하는지 판정하는 인물 게이트다.
비관료 당사자 = 기업 임원/대표/창업자, 정부/공무원, 대변인, 기관, 언론사가 '아닌' 구체적 개인(노동자, 이용자, 피해자, 내부고발자, 일반 시민 등).
세 조건을 모두 만족하면 pass=true:
1. 이름 있는 비관료 당사자 존재 → person 필드에 "이름(역할)" 반환
2. 그 사람의 직접 인용(본문 따옴표 인용)이 존재
3. 그 사람에게 구체적 대가 존재 (해고/실직/피해/손해/소송/감원/일자리 상실/비용 부담/처벌/형사 charge 등)
하나라도 아니면 pass=false. person은 null, reason에 어느 조건이 안 됐는지 명시.
출력은 JSON 펜스(```json) 없이 순수 JSON만 출력하라. 형식: {"pass": bool, "person": "이름(역할) 또는 null", "reason": "한 줄 근거"}"""


def _normalize_json(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    return m.group(0) if m else raw


def person_gate(title: str, body: str, retries: int = 1) -> dict:
    """본문을 LLM에 주고 인물 게이트 판정. 실패 시 항상 탈락(pass=False)."""
    user = f"[제목] {title or '알 수 없음'}\n\n[본문]\n{body[:6000]}"
    msgs = [
        {"role": "system", "content": GATE_SYSTEM},
        {"role": "user", "content": user},
    ]
    last_err = ""
    for attempt in range(retries + 1):
        try:
            raw = chat_completion(
                msgs, max_tokens=400, temperature=0,
                response_format={"type": "json_object"},
            )
            return json.loads(_normalize_json(raw))
        except Exception as ex:  # 파싱/호출 실패
            last_err = str(ex)
            # retries번 재시도 후 그래도 실패하면 탈락 처리
            if attempt == retries:
                return {
                    "pass": False,
                    "person": None,
                    "reason": f"gate_error(final): {last_err[:120]}",
                }
    return {"pass": False, "person": None, "reason": "unreachable"}


if __name__ == "__main__":
    # minimal self-check
    import standalone_extractor as se  # type: ignore
    import sys as _s
    url = _s.argv[1] if len(_s.argv) > 1 else "https://www.404media.co/charges-dropped-against-person-who-clapped-at-a-city-data-center-meeting/"
    b, t, _ = se.crawl(url)
    print(json.dumps(person_gate(t, b), ensure_ascii=False, indent=2))
