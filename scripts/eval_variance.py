#!/usr/bin/env python3
"""[진단] 변동원 분리 — 같은 답안을 판관만 N회 재채점한다 (AGENT-EVAL-01 4단계 1번).

왜: 동일 모델을 2회 돌렸는데 점수가 뒤집혔다(Q9·Q11 플립). 원인은 두 가지 중 하나다.
  ① **학생(모델) 문제** — 같은 문항에 다른 답을 냈다.
  ② **판관 문제** — 같은 답을 놓고 판관이 매번 다른 0/1 을 준다.
둘은 비용 없이 분리할 수 있다. 캐시에 저장된 **답안**을 학생 재호출 없이 그대로 판관에
N번 넣고, 판정값이 흔들리는지만 본다. 판관이 흔들리면 그 문항은 채점 신호가 아니라 동전이다.

주의 (이 진단의 한계 — 결과 해석에 반드시 반영):
  - 캐시는 답안을 `ANSWER_STORE_CHARS`(1000) 자에서 잘라 저장한다. 잘린 답안은 원래 판정 때
    본 문장과 다르므로, 절단된 문항의 재채점은 원래 조건과 동등하지 않다(무방향 잡음).
  - 샌드박스 문항의 점수는 기계 판정이라 재채점 대상이 아니다(제외).
  - 미채점(exception, 타임아웃) 문항도 제외 — 판관이 볼 답이 없다.

사용:
    python3 scripts/eval_variance.py --repeats 3
    python3 scripts/eval_variance.py --repeats 3 --qv 2        # 문항 세트만 좁히기
    python3 scripts/eval_variance.py --repeats 3 --model ll-alpha-free
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_eval as me  # noqa: E402


def judge_q_for(spec):
    """eval_model_cli 과 **완전히 동일하게** 판관용 질문문을 조립한다.

    어긋나면 다른 걸 재채점하는 셈이므로 한 군데서만 만든다.
    """
    question = spec["q"]
    seed = spec.get("seed")
    if not seed:
        return question
    return (
        "=== 대화 기록 ===\n"
        + "\n".join(f"{m['role']}: {m['content']}" for m in
                    list(seed) + [{"role": "user", "content": question}])
        + "\n=== 질문 ==="
    )


def judgeable(details):
    """재채점 대상 문항만 뽑는다 (샌드박스·미응답 제외)."""
    out = []
    for d in details or []:
        if d.get("source") != "cli":
            continue
        if d.get("sandbox"):          # 기계 판정 — 재채점 대상 아님
            continue
        if not (d.get("answer") or "").strip():
            continue
        out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default=None)
    ap.add_argument("--qv", type=int, default=None)
    ap.add_argument("--gap", type=float, default=1.0, help="재시도 간 sleep(초)")
    args = ap.parse_args()

    cache = me.cache_load()
    total_q = stable_q = unstable_q = skipped = 0
    flipped = []

    for model_id, entry in sorted(cache.items()):
        if args.model and model_id != args.model:
            continue
        if args.qv is not None and entry.get("qv") != args.qv:
            continue
        specs = {i: s for i, s in enumerate(me.TEST_QUESTIONS, 1)}
        rows = judgeable(entry.get("details"))
        if not rows:
            print(f"[{model_id}] 재채점 대상 0건 (qv={entry.get('qv')}) — 건너뜀")
            continue
        print(f"\n[{model_id}] qv={entry.get('qv')} · 재채점 {len(rows)}문항 × {args.repeats}회")
        m_stable = m_unstable = 0
        for d in rows:
            idx = d["idx"]
            spec = specs.get(idx)
            if spec is None:
                continue
            truncated = len(d["answer"]) >= me.ANSWER_STORE_CHARS
            runs = []
            for k in range(args.repeats):
                if k:
                    time.sleep(args.gap)
                try:
                    runs.append(me.score_response(judge_q_for(spec), spec["expected"], d["answer"]))
                except Exception as e:  # 판관 호출 자체가 죽으면 그건 결함으로 기록
                    runs.append(None)
                    print(f"   예외 {type(e).__name__}")
            judged = [r for r in runs if r is not None]
            tally = Counter(judged)
            distinct = set(judged)
            tag = "안정" if len(distinct) <= 1 else "불안정"
            if len(distinct) > 1:
                m_unstable += 1
                total_q += 1
                flipped.append((model_id, idx, spec["axis"], d.get("score"), runs, truncated))
                print(f"   Q{idx:>2}[{spec['axis']}] {tag} 원채점={d.get('score')} "
                      f"재채점={runs} {'⚠절단' if truncated else ''}")
            else:
                m_stable += 1
                stable_q += 1
                total_q += 1
            if truncated and len(distinct) <= 1:
                skipped += 1
        print(f"   → 안정 {m_stable} · 불안정 {m_unstable}")

    print("\n" + "=" * 64)
    print(f"재채점 문항 {total_q}건 중 판정 흔들림 {len(flipped)}건 "
          f"({100.0 * len(flipped) / max(1, total_q):.1f}%)")
    if flipped:
        print("→ **판관이 흔들린다.** 학생 문제가 아니라 채점 신호가 문항마다 다르고, "
              "점수 비교의 분모가 흔들린다.")
    else:
        print("→ 판정은 안정적이다. 2회 실행 간 플립은 **학생(모델) 출력 변동** 쪽에 있다.")
    print(f"(참고) 1000자 절단 문항 {skipped}건 — 절단본 재채점은 원래 조건과 동등하지 않다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
