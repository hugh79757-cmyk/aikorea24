// 태스크 controlled vocabulary — TypeScript 버전
// Python 버전: scripts/task_config.py
// 두 파일이 항상 동기화되어야 함

export interface TaskInfo {
  title: string;
  kw: string;
}

export const TASKS: Record<string, TaskInfo> = {
  // 문서·텍스트
  "pdf-요약":        { title: "PDF 요약 AI 추천", kw: "PDF 요약 AI" },
  "유튜브-요약":      { title: "유튜브 요약 AI 추천", kw: "유튜브 요약 AI" },
  "글쓰기":           { title: "AI 글쓰기 도구 추천", kw: "AI 글쓰기" },
  "이메일-작성":      { title: "이메일 작성 AI 추천", kw: "AI 이메일 작성" },
  "번역":             { title: "AI 번역기 추천", kw: "AI 번역기" },
  "요약":             { title: "AI 텍스트 요약 추천", kw: "AI 텍스트 요약" },
  "맞춤법-교정":      { title: "맞춤법 교정 AI 추천", kw: "AI 맞춤법" },
  "보고서-작성":      { title: "보고서 작성 AI 추천", kw: "AI 보고서" },
  "이력서":           { title: "AI 이력서 작성 추천", kw: "AI 이력서" },
  "카피라이팅":       { title: "AI 카피라이팅 도구 추천", kw: "AI 카피라이팅" },
  "문서-번역":        { title: "문서 번역 AI 추천", kw: "AI 문서 번역" },
  "자기소개서":       { title: "자기소개서 작성 AI 추천", kw: "AI 자기소개서" },
  "기획서":           { title: "기획서 작성 AI 추천", kw: "AI 기획서" },
  "회의록":           { title: "회의록 작성 AI 추천", kw: "AI 회의록" },
  "프레젠테이션":     { title: "프레젠테이션 AI 추천", kw: "AI 프레젠테이션" },

  // 이미지·디자인
  "이미지-생성-무료": { title: "무료 AI 이미지 생성 추천", kw: "무료 AI 이미지 생성" },
  "이미지-생성":      { title: "AI 이미지 생성 추천", kw: "AI 이미지 생성" },
  "배경-제거":        { title: "배경 제거 AI 추천", kw: "AI 배경 제거" },
  "썸네일-제작":      { title: "썸네일 제작 AI 추천", kw: "AI 썸네일" },
  "로고-디자인":      { title: "로고 디자인 AI 추천", kw: "AI 로고 만들기" },
  "ppt-발표":         { title: "AI PPT 만들기 추천", kw: "AI PPT" },
  "인포그래픽":       { title: "AI 인포그래픽 도구 추천", kw: "AI 인포그래픽" },
  "아이콘-디자인":    { title: "아이콘 디자인 AI 추천", kw: "AI 아이콘" },
  "일러스트":         { title: "AI 일러스트 생성 추천", kw: "AI 일러스트" },
  "UI-디자인":        { title: "UI 디자인 AI 추천", kw: "AI UI 디자인" },
  "웹디자인":         { title: "웹디자인 AI 추천", kw: "AI 웹디자인" },

  // 영상·음성
  "영상-제작":        { title: "AI 영상 제작 추천", kw: "AI 영상 제작" },
  "영상-편집":        { title: "AI 영상 편집 추천", kw: "AI 영상 편집" },
  "자막-생성":        { title: "자막 생성 AI 추천", kw: "AI 자막" },
  "음성-변환":        { title: "AI 음성 변환 추천", kw: "AI 음성 변환" },
  "더빙":             { title: "AI 더빙 도구 추천", kw: "AI 더빙" },
  "음악-생성":        { title: "AI 음악 생성 추천", kw: "AI 음악 만들기" },
  "텍스트-음성":      { title: "텍스트 음성 변환 AI 추천", kw: "AI TTS" },
  "음성-녹음":        { title: "AI 음성 녹음 추천", kw: "AI 녹음" },
  "팟캐스트":         { title: "AI 팟캐스트 추천", kw: "AI 팟캐스트" },
  "배경음악":         { title: "배경음악 생성 AI 추천", kw: "AI 배경음악" },

  // 업무·생산성
  "회의-요약":        { title: "회의 요약 AI 추천", kw: "AI 회의 요약" },
  "일정-관리":        { title: "AI 일정 관리 도구 추천", kw: "AI 일정 관리" },
  "데이터-분석":      { title: "AI 데이터 분석 도구 추천", kw: "AI 데이터 분석" },
  "엑셀-자동화":      { title: "엑셀 자동화 AI 추천", kw: "AI 엑셀" },
  "업무-자동화":      { title: "업무 자동화 AI 추천", kw: "AI 업무 자동화" },
  "챗봇-구축":        { title: "AI 챗봇 만들기 추천", kw: "AI 챗봇 구축" },
  "메모-정리":        { title: "AI 메모 정리 추천", kw: "AI 메모" },
  "프로젝트-관리":    { title: "AI 프로젝트 관리 추천", kw: "AI 프로젝트 관리" },
  "자동화-워크플로우": { title: "워크플로우 자동화 AI 추천", kw: "AI 워크플로우" },
  "CRM":              { title: "AI CRM 도구 추천", kw: "AI CRM" },

  // 코딩·개발
  "코딩":             { title: "코딩 AI 추천", kw: "코딩 AI" },
  "코드-리뷰":        { title: "AI 코드 리뷰 도구 추천", kw: "AI 코드 리뷰" },
  "노코드":           { title: "노코드 AI 도구 추천", kw: "노코드 AI" },
  "바이브코딩":       { title: "바이브코딩 AI 추천", kw: "AI 바이브코딩" },
  "API-개발":         { title: "API 개발 AI 추천", kw: "AI API 개발" },
  "디버깅":           { title: "AI 디버깅 추천", kw: "AI 디버깅" },
  "테스트":           { title: "AI 테스트 자동화 추천", kw: "AI 테스트" },

  // 학습·리서치
  "논문-요약":        { title: "논문 요약 AI 추천", kw: "AI 논문 요약" },
  "영어-학습":        { title: "영어 학습 AI 추천", kw: "AI 영어 공부" },
  "리서치":           { title: "AI 리서치 도구 추천", kw: "AI 리서치" },
  "자격증-학습":      { title: "자격증 학습 AI 추천", kw: "AI 자격증" },
  "면접-준비":        { title: "면접 준비 AI 추천", kw: "AI 면접" },
  "제2외국어":        { title: "제2외국어 학습 AI 추천", kw: "AI 외국어" },

  // 마케팅·SNS
  "sns-콘텐츠":       { title: "SNS 콘텐츠 제작 AI 추천", kw: "AI SNS 콘텐츠" },
  "seo-최적화":       { title: "SEO 최적화 AI 도구 추천", kw: "AI SEO" },
  "광고-카피":        { title: "광고 카피 AI 추천", kw: "AI 광고 카피" },
  "블로그-작성":      { title: "블로그 글쓰기 AI 추천", kw: "AI 블로그" },
  "유튜브-편집":      { title: "유튜브 편집 AI 추천", kw: "AI 유튜브 편집" },
  "마케팅-자동화":    { title: "마케팅 자동화 AI 추천", kw: "AI 마케팅 자동화" },
  "콘텐츠-기획":      { title: "콘텐츠 기획 AI 추천", kw: "AI 콘텐츠 기획" },
  "브랜드-네이밍":    { title: "브랜드 네이밍 AI 추천", kw: "AI 브랜드 네이밍" },

  // 전문 분야
  "의료-상담":        { title: "의료 상담 AI 추천", kw: "AI 의료" },
  "법률-검토":        { title: "법률 검토 AI 추천", kw: "AI 법률" },
  "부동산-분석":      { title: "부동산 분석 AI 추천", kw: "AI 부동산" },
  "투자-분석":        { title: "투자 분석 AI 추천", kw: "AI 투자" },
  "회계-경리":        { title: "회계 경리 AI 추천", kw: "AI 회계" },
  "고객-상담":        { title: "고객 상담 AI 추천", kw: "AI 고객 상담" },
};

export const TASK_SLUGS = Object.keys(TASKS);
export const TASK_COUNT = TASK_SLUGS.length;
