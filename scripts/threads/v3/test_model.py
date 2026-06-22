#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""Qwen3 235B 인과관계 테스트"""
import sys, time, os
sys.path.insert(0, '/Users/twinssn/Projects/aikorea24/scripts/threads')
os.chdir('/Users/twinssn/Projects/aikorea24/scripts/threads')
from v3.model_router import load_env, chat_completion

load_env()

test = """
다음 기사를 읽고 핵심 인과관계를 정확히 한 문장으로 요약하라:

기사: "미국 국방부가 Anthropic의 Claude 모델 사용을 제한하는 규제를 
검토 중이다. 이 규제가 시행되면 Anthropic 대신 OpenAI가 미국 정부 
AI 계약을 독점할 가능성이 높다고 전문가들은 분석한다."

핵심 인과관계 (주어-동사-결과 형식으로):
"""

print("=" * 60)
print("테스트 모델: qwen/qwen3-next-80b-a3b-instruct")
print("=" * 60)

start = time.time()
resp = chat_completion([{"role": "user", "content": test}], temperature=0.3, max_tokens=500)
elapsed = time.time() - start

print(f"\n[테스트 결과] ({elapsed:.1f}초)")
print(resp)

# 평가
if resp:
    resp_lower = resp.lower()
    if ("anthropic" in resp_lower and "openai" in resp_lower and 
        ("규제" in resp or "제한" in resp or "금지" in resp) and
        ("독점" in resp or "이득" in resp or "유리" in resp)):
        print(f"\n✅ 통과: 인과관계 정확 (Anthropic 규제 → OpenAI 이득)")
    elif "anthropic" in resp_lower and "openai" in resp_lower:
        print(f"\n⚠️ 부분 통과: 인과관계 서술 확인 필요")
    else:
        print(f"\n❌ 실패: 인과관계 오류")
else:
    print(f"\n❌ 실패: 응답 없음")
