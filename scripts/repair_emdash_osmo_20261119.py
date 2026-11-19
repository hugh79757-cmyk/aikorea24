#!/usr/bin/env python3
"""2026-11-19 사고 복구 — EmDash 심층글 본문의 '젠슨 황' 오염 제거 (Osmo 편).

사고 경위
  05:30 수집분 news 61940 은 원제목이 "This smell startup says its AI nose is as good
  as a human's"(MIT 테크 리뷰, 오스모)인데, 배치 번역 제목이 한 칸 밀려
  "오픈소스 진영, 젠슨 황의 복귀를 원해" 로 저장됐다. 07:15 심층글 생성기가 그 제목을
  씨앗으로 글을 써서 2·4절이 엔비디아/젠슨 황 이야기로 채워졌고, 에이버리 길버트를
  '상호 운용성 지지자'로 잘못 인용했다. 제목은 2026-11-19 11:35 에 교체됐지만 본문은 그대로였다.

이 스크립트가 하는 일
  · 원문(MIT 테크 리뷰)에서 확인된 사실만으로 2·4절과 도입·마무리를 다시 쓴다.
  · 3절 표를 '확인된 적용'과 '회사의 전망'으로 구분한다.
  · 403 이 나는 패스트컴퍼니 링크를 참고 자료에서 뺀다(원문 링크로 대체 가능한 사실).
  · slug·발행시각은 건드리지 않는다(외부 링크 보존). 본문은 API PUT+publish 로만 쓴다.

사용:
  ../.venv/bin/python3 scripts/repair_emdash_osmo_20261119.py --dry-run
  ../.venv/bin/python3 scripts/repair_emdash_osmo_20261119.py --apply
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emdash_publish as ep  # noqa: E402

SLUG = "오픈소스-진영-젠슨-황의-복귀를-원해-기술-생태계의-변화와-전략"
LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

MIT_URL = "https://www.technologyreview.com/2026/11/18/1148816/smell-startup-osmo-ai-nose-good-as-humans/"
OPENPOM_URL = "https://github.com/biomachinelearning/openpom"
GILBERT_URL = "https://averygilbert.substack.com/p/the-great-and-powerful-osmo"
PRN_URL = ("https://www.prnewswire.com/news-releases/osmo-receives-8-5-million-in-funding-"
           "to-support-advancement-in-ai-enabled-insect-control-301981300.html")

_k = [0]


def key(prefix="r"):
    _k[0] += 1
    return f"{prefix}{_k[0]}"


def span(text, marks=None):
    return {"_type": "span", "_key": key("s"), "text": text, "marks": marks or []}


def para(*parts, style="normal"):
    """parts: str 또는 (str, url). URL 이 있으면 링크 mark 를 붙인다."""
    markdefs, children = [], []
    for part in parts:
        if isinstance(part, tuple):
            text, url = part
            mk = key("l")
            markdefs.append({"_key": mk, "_type": "link", "href": url})
            children.append(span(text, [mk]))
        else:
            children.append(span(part))
    return {"_type": "block", "_key": key("b"), "style": style,
            "markDefs": markdefs, "children": children}


def table(rows):
    rws = []
    for r_i, row in enumerate(rows):
        cells = []
        for c_i, cell in enumerate(row):
            cells.append({
                "_type": "tableCell", "_key": key("c"),
                "isHeader": r_i == 0,
                "content": [span(cell)],
            })
        rws.append({"_type": "tableRow", "_key": key("rw"), "cells": cells})
    return {"_type": "table", "_key": key("t"), "rows": rws}


REPLACEMENTS = {
    0: para(
        "뉴저지주 뉴어크 공항 인근의 실험실에서는 약 30명의 후각 전문가가 매일 냄새를 맡고 "
        "기록합니다. '고소함', '복숭아 향', '바다 향' 같은 이들의 메모는 화학 분석 결과와 "
        "교차 대조됩니다. 이 데이터를 모으는 곳은 2023년 구글 브레인에서 분사한 AI 스타트업 "
        "오스모(Osmo)입니다. 창업자 알렉스 빌트슈코(Alex Wiltschko)가 내건 목표는 "
        "'컴퓨터에 후각을 주는 것'입니다."
    ),
    1: para("1. 냄새를 데이터로 바꾸는 방법", style="h2"),
    2: para(
        ("MIT 테크 리뷰", MIT_URL),
        "에 따르면 오스모는 1,000만 건이 넘는 사람의 냄새 라벨과 8억 개의 '향 토큰"
        "(scent token)'을 자체 구축했습니다. 분광기 같은 화학 센서를 24시간 돌려 과일·꽃·"
        "향신료부터 장기(臟器)까지 분자 구성을 분해하고, 미국과 해외에서 활동하는 약 70명의 "
        "라벨러가 표준화된 향 용어로 냄새를 기록합니다. 오스모는 이 데이터를 '냄새를 위한 "
        "세계 최초의 파운데이션 모델'의 학습 자료로 씁니다. 오스모 이전에는 사람이 쓴 냄새 "
        "설명이 20만 건에 못 미쳤고, 화학 센서는 비쌌으며 향료 업계는 후각 연구를 공개하지 "
        "않았습니다. 회사가 직접 데이터를 만들어야 했던 이유입니다.",
    ),
    3: para(
        "흥미로운 대목은 분자의 배합 비율이 바뀌면 전혀 다른 냄새가 난다는 점입니다. 빌트슈코는 "
        "'갓난아기 냄새를 정의하는 향 토큰과 갓 조리한 스파게티에서 나는 향 토큰이 크게 "
        "겹친다'고 말합니다. 사람이 냄새를 기억하는 방식이 분자 목록만으로 설명되지 않는다는 "
        "뜻이기도 합니다.",
    ),
    4: para("2. '인간 수준'이라는 주장과 그 근거", style="h2"),
    5: para(
        "빌트슈코는 최근 몇 달 사이 모델이 '인간 수준의 후각 지능'에 도달했다고 주장합니다. "
        "회사가 정의한 기준은 두 가지입니다. 냄새를 감별하는 능력은 평균적인 사람과 비슷하고, "
        "새 향을 만드는 능력은 주니어 조향사와 비슷하다는 것입니다. 회사는 지난달 세계 최대 "
        "소비재 기업 중 한 곳에서 자사 AI가 사내 조향사들을 앞섰다고 밝혔습니다. 실험실에는 "
        "버스 크기의 '향 출력 로봇'도 있습니다. 문장으로 주문하면 분자 배합을 설계해 시향 "
        "샘플을 뽑아내는 장비입니다. 리스본 웹서밋에서 기자가 '18~23세 남성을 겨냥한 "
        "포르투갈식 에그타르트 향'을 주문하자, 시스템은 크리미하고 코코넛 같은 과일 향 "
        "프로필 세 가지와 필요한 분자 목록을 제시했습니다."
    ),
    6: para(
        "반론도 만만치 않습니다. 냄새 과학자이자 'What the Nose Knows'의 저자인 에이버리 "
        "길버트(Avery Gilbert)는 ",
        ("자신의 서브스택", GILBERT_URL),
        "에서 오스모를 강하게 비판합니다. 마케팅 주장 가운데 상당 부분이 문서로 뒷받침되지 "
        "않고, 특허 출원 내용을 보면 여전히 AI가 아니라 사람의 관능 평가와 조향사에 의존한다는 "
        "지적입니다. 그는 지난 3월 글에서 최첨단 AI를 내세우는 회사치고는 사람의 감각 판단 "
        "의존도가 지나치게 높다고 썼습니다. 오스모 측은 논평 요청에 답하지 않았습니다. 반면 "
        "신경 연산 분야 교수였고 과거 오스모 자문을 맡았던 마이클 슈무커(Michael Schmuker)는 "
        "기술 자체를 성과로 평가합니다. 그는 동료들과 함께 오스모 2023년 모델을 역설계한 ",
        ("오픈소스 구현(OpenPOM)", OPENPOM_URL),
        "을 공개했습니다. 다만 이후 회사가 쌓은 방대한 데이터는 따라올 수 없다고 말합니다.",
    ),
    7: para("3. 실제로 쓰이는 곳과 아직 먼 곳", style="h2"),
    8: para(
        "원문에서 확인된 적용 분야와 회사의 전망을 구분하면 다음 표와 같습니다."
    ),
    9: table([
        ["분야", "확인된 내용"],
        ["향수·향료", "대형 소비재 기업과 협업, 상용 향료 제조 (회사 발표)"],
        ["해충 기피", "게이츠재단 지원, DEET보다 강한 물질 8종 확인"],
        ["위조품 판별", "스톡엑스(StockX)와 운동화 소재 화학 조성 차이 분석"],
        ["의료 진단·공항 보안", "빌트슈코의 전망 — 센서·모델 개선이 전제"],
    ]),
    10: para(
        "정리하면 데이터가 풍부한 영역(향료)과 화학 조성 차이가 뚜렷한 영역(위조품)에서는 이미 "
        "결과가 나왔습니다. 반면 의료 진단은 '가장 큰 상금'으로 불리지만 아직 검증 단계가 "
        "아닙니다. 게이츠재단이 500만 달러를 투자한 뒤 350만 달러를 추가 지원한 것도, 위조품 "
        "판별 도구가 상용화된 것도 모두 원문에서 확인되는 사실입니다. 향료 고객사 가운데는 "
        "프록터앤드갬블(P&G)도 포함됩니다."
    ),
    11: para("4. 한계 — 냄새에서 맥락은 절반이다", style="h2"),
    12: para(
        "슈무커는 냄새가 맥락에 크게 좌우된다고 지적합니다. 프랑스 치즈(카망베르)에서 나는 "
        "분자의 상당 부분은 사용한 기저귀에서도 나지만, 사람은 맥락 덕분에 둘을 혼동하지 "
        "않습니다. 향료 실험실처럼 통제된 환경에서는 이 문제가 크지 않을 수 있지만, 공장 라인의 "
        "음식 부패 감지나 냄새로 종양을 찾는 수준으로 가려면 센서 성능과 모델이 함께 개선돼야 "
        "합니다. 슈무커는 오스모의 기술이 'AI 세계 모델'의 후각 채널이 되려면 시간이 더 걸린다고 "
        "봅니다."
    ),
    13: para(
        "빌트슈코도 의료 진단이 가장 어려운 목표임을 인정합니다. 그는 그 산봉우리를 정면으로 "
        "공략한 회사들이 비용과 난이도 때문에 성공하지 못한 사례가 많다며, 오스모는 산기슭에서 "
        "기반을 쌓으며 여러 방향으로 탐사를 보내는 중이라고 설명했습니다. 화려한 표현과 별개로, "
        "지금 검증된 것은 향료와 위조품 판별이고 의료·보안은 로드맵에 가깝습니다. 시향 데모와 "
        "향 출력 로봇 같은 성과는 실재하지만, 규제와 임상 검증이 필요한 분야에는 아직 근거가 "
        "부족합니다."
    ),
    15: para(("MIT 테크 리뷰 — 이 냄새 스타트업은 AI 코가 인간만큼 좋다고 말한다", MIT_URL)),
    16: para(("오픈폼(OpenPOM) — 오스모 2023 모델을 역설계한 오픈소스 구현", OPENPOM_URL)),
    17: para(("에이버리 길버트 — 오스모의 마케팅 주장에 대한 비판", GILBERT_URL)),
    19: para(("오스모의 투자 유치 및 해충 방제 사업 소식", PRN_URL)),
    20: para("마무리 — 냄새 AI 기사를 읽을 때 확인할 3가지", style="h2"),
    21: para(
        "냄새 AI 기사는 '인간 수준'이라는 표현 때문에 실제보다 앞서 보이기 쉽습니다. 다음 세 "
        "가지만 확인해도 판단이 달라집니다."
    ),
    22: para(
        "① 기준을 먼저 봅니다 — 오스모의 '인간 수준'은 평균적인 사람의 감별력과 주니어 조향사의 "
        "창작력이라는 회사 자체 정의입니다. 정의가 없는 '인간 수준' 주장은 근거로 삼기 "
        "어렵습니다. 그 정의 밖의 '인간 수준'은 아직 누구도 측정하지 않았습니다."
    ),
    23: para(
        "② 확인된 적용과 전망을 나눕니다 — 향료와 위조품 판별은 실제 사례가 있고, 의료 진단과 "
        "공항 보안은 아직 회사의 전망입니다."
    ),
    24: para(
        "③ 반대 검증을 찾아 읽습니다 — ",
        ("길버트의 비판", GILBERT_URL),
        "과 특허·논문 근거를 함께 보면 주장의 경계가 보입니다.",
    ),
}

DROP_INDEXES = {18}  # 패스트컴퍼니 링크(HTTP 403) — 참고 자료에서 제외


def visible_text(content):
    out = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("_type") == "span" and isinstance(node.get("text"), str):
                out.append(node["text"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(content)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    it = ep.get_post(SLUG)
    item = (it or {}).get("item") or {}
    data = item.get("data") or {}
    content = data.get("content") or []
    if not content:
        raise SystemExit("본문 조회 실패")

    new_content = []
    for i, blk in enumerate(content):
        if i in DROP_INDEXES:
            continue
        new_content.append(REPLACEMENTS.get(i, blk))

    before = visible_text(content)
    after = visible_text(new_content)
    print(f"블록 {len(content)} → {len(new_content)}")
    print(f"본문 가시 글자 {len(before)} → {len(after)}")
    print("젠슨 등장:", after.count("젠슨"), "| 오픈소스 진영:", after.count("오픈소스 진영"))
    assert after.count("젠슨") == 0, "젠슨 황 문구가 남아 있다"
    assert len(after) >= 3000, f"본문이 짧다: {len(after)}자"

    if not a.apply:
        print("\n[DRY-RUN] 새 본문 전문:\n")
        print(after)
        return 0

    os.makedirs(LOGS, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(LOGS, f"backup_emdash_osmo_{ts}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=1)
    print(f"백업: {backup}")

    new_data = dict(data)
    new_data["content"] = new_content
    from emdash04_migrate import api
    pid = item.get("id") or SLUG
    st, d = api(f"/_emdash/api/content/posts/{pid}", "PUT",
                {"collection": "posts", "id": pid, "data": new_data, "_rev": it.get("_rev")})
    print("PUT", st, json.dumps(d, ensure_ascii=False)[:160] if st not in (200, 201) else "ok")
    if st not in (200, 201):
        return 1
    st2, d2 = api(f"/_emdash/api/content/posts/{pid}/publish", "POST", {})
    print("publish", st2, json.dumps(d2, ensure_ascii=False)[:160] if st2 not in (200, 201) else "ok")
    if st2 not in (200, 201):
        return 1

    it3 = ep.get_post(SLUG) or {}
    item3 = (it3.get("item") or {})
    after3 = visible_text((item3.get("data") or {}).get("content") or [])
    print("사후검증 — 젠슨:", after3.count("젠슨"),
          "| slug 보존:", item3.get("slug") == item.get("slug"),
          "| 발행시각 보존:", item3.get("publishedAt") == item.get("publishedAt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
