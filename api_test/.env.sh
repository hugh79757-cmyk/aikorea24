:qw


:q
#!/bin/bash
# ============================================================
# aikorea24.kr 환경변수 정의
# 사용법: source /Users/twinssn/Projects/aikorea24/api_test/.env.sh
# ============================================================

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [A] 네이버 개발자센터 API
#     발급: https://developers.naver.com/apps/
#     앱 등록 시 "검색" + "데이터랩(검색어트렌드)" 체크
#     ※ 기존 NKP에서 사용 중이면 그대로 복사
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export NAVER_CLIENT_ID=""
export NAVER_CLIENT_SECRET=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [B] 네이버 검색광고 API (키워드도구)
#     발급: https://manage.searchad.naver.com/
#     광고시스템 > 도구 > API 사용 관리
#     ※ 광고 계정 필요 (무료 개설 가능)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export NAVER_AD_API_KEY=""
export NAVER_AD_SECRET=""
export NAVER_AD_CUSTOMER_ID=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [C] OpenAI API
#     발급: https://platform.openai.com/api-keys
#     사용 모델: gpt-4o-mini (뉴스 요약)
#     비용: 입력 $0.15/1M, 출력 $0.60/1M 토큰
#     신규 가입 시 $5 무료 크레딧 제공
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export OPENAI_API_KEY=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [D] 공공데이터포털 인증키
#     발급: https://www.data.go.kr/
#     회원가입 > 마이페이지 > 인증키 발급
#     활용신청 필요 API:
#       1) 보조금통합포털 보조사업현황
#       2) 행정안전부 대한민국 공공서비스(혜택) 정보
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export DATA_GO_KR_KEY=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [E] Instagram Graph API
#     발급: https://developers.facebook.com/
#     필요: 비즈니스/크리에이터 인스타 계정
#          + Facebook 페이지 연결
#          + Meta 앱 생성 + 앱 심사
#     ※ 초기에는 SKIP 가능 (Phase 3에서 연동)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export INSTAGRAM_ACCESS_TOKEN=""
export INSTAGRAM_BUSINESS_ID=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [F] Google Trends API (공식 알파)
#     신청: https://developers.google.com/search/blog/2025/07/trends-api
#     ※ 알파 대기 중이면 빈칸으로 두기
#     ※ pytrends 대신 공식 API 사용 예정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export GOOGLE_TRENDS_API_KEY=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [G] 프로젝트 경로
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export AIKOREA24_HOME="/Users/twinssn/Projects/aikorea24"
export NKP_HOME="/Users/twinssn/Projects/news-keyword-pro"



:q
:wq


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [H] AI허브 API (https://www.aihub.or.kr)
#     회원가입 후 마이페이지 > API 키 발급
#     사용: AI 데이터셋 목록 조회, AI바우처 업체 조회
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export AIHUB_API_KEY=""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [I] 정책브리핑 RSS (키 불필요, 참조용 URL)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export KOREA_KR_RSS_MSIT="https://www.korea.kr/rss/dept_msit.xml"
export KOREA_KR_RSS_POLICY="https://www.korea.kr/rss/policy.xml"
export KOREA_KR_RSS_PRESS="https://www.korea.kr/rss/pressrelease.xml"
