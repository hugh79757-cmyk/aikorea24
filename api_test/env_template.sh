#!/bin/bash
# ============================================
# aikorea24.kr API 키 설정 템플릿
# 이 파일을 .env.sh로 복사 후 실제 키 입력
# cp env_template.sh .env.sh
# ============================================

# [1] 네이버 개발자센터 (https://developers.naver.com/apps/)
# - 사용 API: 검색(뉴스,블로그), 데이터랩(검색어트렌드)
export NAVER_CLIENT_ID="YOUR_NAVER_CLIENT_ID"
export NAVER_CLIENT_SECRET="YOUR_NAVER_CLIENT_SECRET"

# [2] 네이버 검색광고 API (https://manage.searchad.naver.com/)
# - 사용 API: 키워드도구 (월간검색량)
export NAVER_AD_API_KEY="YOUR_AD_API_KEY"
export NAVER_AD_SECRET="YOUR_AD_SECRET"
export NAVER_AD_CUSTOMER_ID="YOUR_CUSTOMER_ID"

# [3] OpenAI API (https://platform.openai.com/api-keys)
# - 사용 모델: gpt-4o-mini (뉴스 요약)
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

# [4] 공공데이터포털 (https://www.data.go.kr/)
# - 사용 API: 보조금통합포털, 공공서비스(혜택)
export DATA_GO_KR_KEY="YOUR_DATA_GO_KR_KEY"

# [5] Instagram Graph API (https://developers.facebook.com/)
# - 사용: 카드뉴스 자동 게시
export INSTAGRAM_ACCESS_TOKEN="YOUR_IG_TOKEN"
export INSTAGRAM_BUSINESS_ID="YOUR_IG_BUSINESS_ID"
