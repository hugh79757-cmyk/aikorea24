"""
태스크 controlled vocabulary v1.0
tools_collector.py, 태스크 페이지, 사이트맵이 모두 이 목록 기준으로 동작한다.
GPT 프롬프트에서 task 슬러그 선택 시 이 목록만 사용한다.

@akai/aikorea24@v2.1
"""

TASKS = {
    # 문서·텍스트
    "pdf-요약":        {"title": "PDF 요약 AI 추천", "kw": "PDF 요약 AI"},
    "유튜브-요약":      {"title": "유튜브 요약 AI 추천", "kw": "유튜브 요약 AI"},
    "글쓰기":           {"title": "AI 글쓰기 도구 추천", "kw": "AI 글쓰기"},
    "이메일-작성":      {"title": "이메일 작성 AI 추천", "kw": "AI 이메일 작성"},
    "번역":             {"title": "AI 번역기 추천", "kw": "AI 번역기"},
    "요약":             {"title": "AI 텍스트 요약 추천", "kw": "AI 텍스트 요약"},
    "맞춤법-교정":      {"title": "맞춤법 교정 AI 추천", "kw": "AI 맞춤법"},
    "보고서-작성":      {"title": "보고서 작성 AI 추천", "kw": "AI 보고서"},
    "이력서":           {"title": "AI 이력서 작성 추천", "kw": "AI 이력서"},
    "카피라이팅":       {"title": "AI 카피라이팅 도구 추천", "kw": "AI 카피라이팅"},

    # 이미지·디자인
    "이미지-생성-무료": {"title": "무료 AI 이미지 생성 추천", "kw": "무료 AI 이미지 생성"},
    "이미지-생성":      {"title": "AI 이미지 생성 추천", "kw": "AI 이미지 생성"},
    "배경-제거":        {"title": "배경 제거 AI 추천", "kw": "AI 배경 제거"},
    "썸네일-제작":      {"title": "썸네일 제작 AI 추천", "kw": "AI 썸네일"},
    "로고-디자인":      {"title": "로고 디자인 AI 추천", "kw": "AI 로고 만들기"},
    "ppt-발표":         {"title": "AI PPT 만들기 추천", "kw": "AI PPT"},
    "인포그래픽":       {"title": "AI 인포그래픽 도구 추천", "kw": "AI 인포그래픽"},

    # 영상·음성
    "영상-제작":        {"title": "AI 영상 제작 추천", "kw": "AI 영상 제작"},
    "영상-편집":        {"title": "AI 영상 편집 추천", "kw": "AI 영상 편집"},
    "자막-생성":        {"title": "자막 생성 AI 추천", "kw": "AI 자막"},
    "음성-변환":        {"title": "AI 음성 변환 추천", "kw": "AI 음성 변환"},
    "더빙":             {"title": "AI 더빙 도구 추천", "kw": "AI 더빙"},
    "음악-생성":        {"title": "AI 음악 생성 추천", "kw": "AI 음악 만들기"},
    "텍스트-음성":      {"title": "텍스트 음성 변환 AI 추천", "kw": "AI TTS"},

    # 업무·생산성
    "회의-요약":        {"title": "회의 요약 AI 추천", "kw": "AI 회의 요약"},
    "일정-관리":        {"title": "AI 일정 관리 도구 추천", "kw": "AI 일정 관리"},
    "데이터-분석":      {"title": "AI 데이터 분석 도구 추천", "kw": "AI 데이터 분석"},
    "엑셀-자동화":      {"title": "엑셀 자동화 AI 추천", "kw": "AI 엑셀"},
    "업무-자동화":      {"title": "업무 자동화 AI 추천", "kw": "AI 업무 자동화"},
    "챗봇-구축":        {"title": "AI 챗봇 만들기 추천", "kw": "AI 챗봇 구축"},

    # 코딩·개발
    "코딩":             {"title": "코딩 AI 추천", "kw": "코딩 AI"},
    "코드-리뷰":        {"title": "AI 코드 리뷰 도구 추천", "kw": "AI 코드 리뷰"},
    "노코드":           {"title": "노코드 AI 도구 추천", "kw": "노코드 AI"},

    # 학습·리서치
    "논문-요약":        {"title": "논문 요약 AI 추천", "kw": "AI 논문 요약"},
    "영어-학습":        {"title": "영어 학습 AI 추천", "kw": "AI 영어 공부"},
    "리서치":           {"title": "AI 리서치 도구 추천", "kw": "AI 리서치"},

    # 마케팅·SNS
    "sns-콘텐츠":       {"title": "SNS 콘텐츠 제작 AI 추천", "kw": "AI SNS 콘텐츠"},
    "seo-최적화":       {"title": "SEO 최적화 AI 도구 추천", "kw": "AI SEO"},
    "광고-카피":        {"title": "광고 카피 AI 추천", "kw": "AI 광고 카피"},
    "블로그-작성":      {"title": "블로그 글쓰기 AI 추천", "kw": "AI 블로그"},
}

# 검증: 모든 슬러그가 유일한지 확인
assert len(TASKS) == 40, f"태스크 수가 40이 아님: {len(TASKS)}"
slugs = list(TASKS.keys())
assert len(slugs) == len(set(slugs)), "중복 슬러그 발견"
print(f"task_config.py 로드 완료: {len(TASKS)}개 태스크")

if __name__ == "__main__":
    for slug, info in TASKS.items():
        print(f"  {slug:20s} → {info['title']}")
