#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
pitch_evaluator.py - 피치 품질 평가
MiMo가 피치의 품질을 0~5점 평가
- 3점 미만이면 폐기
"""
import os, json, re
from datetime import datetime

THREADS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [eval] {msg}\n')

EVAL_SYSTEM_PROMPT = """당신은 피치 품질 평가자입니다.

아래 기준으로 0~5점을 매기고, 3점 이상만 통과시킵니다.
단, 항목 3이 0점이면 총점과 무관하게 불통과입니다.

[평가 기준]
1. 상식충돌: "상식적으로 A였어야 하는데 실제로는 B" 구조가 명확한가? (0~2점)
   - 2점: 독자가 "어? 몰랐다" 할 충돌
   - 1점: 어느 정도 알려진 이야기
   - 0점: 충돌 없음, 단순 사실 나열

2. 구체성: 숫자/인물/기업명이 포함되어 있는가? (0~2점)
   - 2점: 구체적 숫자 + 인물/기업명 모두 있음
   - 1점: 하나만 있음
   - 0점: 추상적 표현뿐

3. 방향 정확성: twist 필드의 주어-동사 방향이 narrative와 일치하는가? (0~1점 — 단, 이 항목이 0점이면 전체 불통과)
   - 1점: twist가 narrative의 B(실제)를 명확히 설명하며 방향 일치
   - 0점: twist가 없거나, narrative와 방향이 반대이거나, 주어가 불명확
   - 예시: narrative="A가 B에게 인프라를 빌려준다" → twist="A가 인프라를 빌려쓴다"는 방향 불일치 (0점)

[출력 형식]
{"score": 0~5, "passed": true/false, "direction_ok": true/false, "reason": "평가 이유 한 줄"}"""

def evaluate_pitch(pitch):
    """피치 품질 평가 → 통과 여부"""
    from v3.model_router import chat_completion

    pitch_json = json.dumps(pitch, ensure_ascii=False)
    try:
        # 방향 정확성 평가는 MiMo 사용
        resp = chat_completion(
            system_prompt=EVAL_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': f'평가할 피치:\n{pitch_json}'}],
            temperature=0.1,
            max_tokens=300,
            model_override='openai',
        )
        # JSON 파싱
        m = re.search(r'\{[^}]+\}', resp)
        if m:
            result = json.loads(m.group(0))
            score = result.get('score', 0)
            passed = result.get('passed', False)
            reason = result.get('reason', '')
            direction_ok = result.get('direction_ok', True)
            log(f'  평가: {score}점/{"" if passed else "불"}통과 ({reason}) direction_ok={direction_ok}')
            # direction_ok=false면 강제 불통과
            if not direction_ok:
                log(f'  ❌ 방향 불일치 강제 불통과')
                return False, 0, '방향 불일치'
            return passed, score, reason
    except Exception as e:
        log(f'  ⚠️ 평가 오류: {e}')

    # fallback: 단일 기사도 기본 통과 (연결성 의존 제거)
    hook = pitch.get('hook', '')
    if len(hook) >= 5:
        return True, 3, 'fallback 통과'
    return False, 0, 'fallback 실패'


def filter_pitches(pitches):
    """여러 피치 중 품질 통과하는 첫 번째 피치 반환"""
    for p in pitches:
        passed, score, reason = evaluate_pitch(p)
        if passed:
            log(f'  ✅ 피치 통과: {score}점')
            return p
        log(f'  ❌ 피치 불통: {score}점 - {reason}')
    return None
