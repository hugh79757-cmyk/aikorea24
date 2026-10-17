#!/usr/bin/env python3
"""[비활성] 판관 재채점 도구 — AIK24-EVAL-JUDGE-04 로 폐지됨.

판관 모델이 폐지되고 문항별 **결정적 채점 함수**로 전환했다. 같은 답안은 언제나 같은 점수가
나오므로 "판정이 흔들리는가" 를 재채점으로 측정할 대상이 더 이상 없다.

이 파일은 과거 실행 로그를 해석하는 용도로 남겨 둔다. 실행하면 아래 메시지만 찍고 종료한다.
(재활성화가 필요해지면 그때 되살린다 — 청결하게 지우지 않는 편이 기록에 낫다.)
"""
import sys

def main():
    print("[비활성] eval_variance: 판관 폐지(AIK24-EVAL-JUDGE-04)로 재채점 기능이 제거되었습니다. "
          "판정이 결정적이므로 변동 분석 대상이 없습니다.")
    return 2

if __name__ == "__main__":
    sys.exit(main())

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
    unmeasurable = []

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
        m_stable = m_unstable = m_unmeasurable = 0
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
            distinct = set(judged)
            if not judged:
                # 판관이 한 번도 0/1 을 말하지 못했다 — 이건 "안정"이 아니라 **판정 불가**다.
                # (이전 버그: distinct 가 빈 집합이라 len(distinct)<=1 로 떨어져 "안정"으로 집계됐다)
                m_unmeasurable += 1
                total_q += 1
                unmeasurable.append((model_id, idx, spec["axis"], runs, truncated))
                print(f"   Q{idx:>2}[{spec['axis']}] 측정불가 원채점={d.get('score')} "
                      f"재채점={runs} {'⚠절단' if truncated else ''}")
            elif len(distinct) > 1:
                m_unstable += 1
                total_q += 1
                flipped.append((model_id, idx, spec["axis"], d.get("score"), runs, truncated))
                print(f"   Q{idx:>2}[{spec['axis']}] 불안정 원채점={d.get('score')} "
                      f"재채점={runs} {'⚠절단' if truncated else ''}")
            else:
                m_stable += 1
                stable_q += 1
                total_q += 1
                if len(judged) < len(runs):
                    print(f"   Q{idx:>2}[{spec['axis']}] 안정(일부 결함) 재채점={runs}")
            if truncated:
                skipped += 1
        print(f"   → 안정 {m_stable} · 불안정 {m_unstable} · 측정불가 {m_unmeasurable}")

    print("\n" + "=" * 64)
    judged_only = total_q - len(unmeasurable)
    print(f"재채점 문항 {total_q}건 = 판정가능 {judged_only} · 측정불가 {len(unmeasurable)}")
    if unmeasurable:
        print(f"→ **측정불가 {len(unmeasurable)}건.** 판관이 전 회차 0/1 을 내지 못했다. "
              "이 문항은 '안정'이 아니라 판정 불가로 보고해야 한다 — 분모에서 빼라.")
        for mid, idx, axis, runs, trunc in unmeasurable:
            print(f"     {mid} Q{idx}[{axis}] 재채점={runs}{' (절단본)' if trunc else ''}")
    if flipped:
        print(f"→ **판정이 흔들린다 {len(flipped)}건** "
              f"({100.0 * len(flipped) / max(1, judged_only):.1f}% of 판정가능). "
              "학생 문제가 아니라 채점 신호가 문항마다 다르다.")
    elif judged_only:
        print("→ 판정 가능한 문항 전부 안정적이다. 2회 실행 간 플립은 **학생(모델) 출력 변동** 쪽이다.")
    if not judged_only and not flipped:
        print("→ **판정가능 문항 0건 — 결론을 낼 수 없다.** (측정 불가를 안정으로 오인하지 말 것)")
    print(f"(참고) 1000자 절단 문항 {skipped}건 — 절단본 재채점은 원래 조건과 동등하지 않다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
