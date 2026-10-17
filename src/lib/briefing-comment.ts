/**
 * 브리핑 코멘트에서 화면에 보여줄 설명 문장만 남긴다 (AIK24-PIPE-04 §작업2).
 *
 * briefing_items.comment 에는 LLM 설명 문장과 함께 개발자용 부가정보가 저장된다:
 *   · 12문항 평가 verdict ("12문항 평가 전 — 판단 보류" / "12문항 평가: N/M — ...")
 *   · CLI 접근성 문구 ("(a) OpenCode 모델 선택기에서 바로 선택 가능" /
 *     "(b) 커스텀 프로바이더 설정 후 연결 가능 (API 키 필요)")
 *   · "설정: {...}" JSON 블록
 *   · blog_draft_generator 가 나중에 덧붙이는 "👉 자세한 분석: https://..." 텍스트 링크
 *     (클릭되지 않는 죽은 텍스트이고 카드의 "자세히 보기" 버튼과 중복이다)
 *
 * 카드·상세·이메일에 필요한 것은 설명 문장뿐이므로 위 줄들을 걷어낸다.
 * 규칙은 scripts/auto_email_sender.py 의 clean_comment_for_display() 와 동일하다.
 * 한쪽만 고치면 웹과 이메일 표시가 어긋난다.
 */
const DROP_LINE =
  /^\s*(?:12문항 평가|OpenCode 동작 확인됨|현재 추천 Top 3 대비|\(a\) OpenCode 모델 선택기|\(b\) 커스텀 프로바이더 설정 후 연결|프로바이더:|설정:\s*\{|👉 자세한 분석:|OpenCode에서 무료로 사용 가능|로컬 브리지|모델:\s*https?:\/\/|사용법:\s*Ollama)/;

export function cleanBriefingComment(comment: string | null | undefined): string {
  if (!comment) return '';
  return String(comment)
    .split('\n')
    .filter((line) => !DROP_LINE.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * 같은 정리 규칙을 news.description (한 줄 문자열) 에 적용한다.
 *
 * description 은 comment 와 달리 한 줄 안에서 " · " 로 이어 붙는다:
 *   · "OpenCode Zen 무료 목록에 제외 · 12문항 평가 전 — 판단 보류"
 *     → verdict 조각을 떼고 "OpenCode Zen 무료 목록에 제외" 만 남긴다
 *   · "Beam Free — CLI에서 입출력 모두 무료. 컨텍스트 262,144 토큰.
 *      OpenCode 설정: {\"model\": ...} 프로바이더 갱신일 ..."
 *     → 설정 JSON 블록만 떼고 설명 문장은 남긴다
 * 떼고 남은 구분자(" · ")와 빈 칸을 정리한다.
 *
 * 브리핑 상세의 "오늘의 다른 AI 뉴스" 카드, 뉴스 목록, 글로벌 뉴스 목록이
 * 이 함수를 통과한 값을 표시한다. (AIK24-PIPE-04 §작업2 — 지시서가 열거한
 * verdict·(a)/(b)·설정 JSON·죽은 링크가 독자 화면에 남지 않게 한다)
 */
const DROP_INLINE: RegExp[] = [
  /(\s*·\s*)?12문항 평가[^·]*/g,
  /(\s*·\s*)?OpenCode 설정:\s*\{[^{}]*\}/g,
  /(\s*·\s*)?설정:\s*\{[^{}]*\}/g,
  /(\s*·\s*)?👉?\s*자세한 분석:\s*\S+/g,
];

export function cleanBriefingDescription(description: string | null | undefined): string {
  if (!description) return '';
  let out = String(description);
  for (const re of DROP_INLINE) out = out.replace(re, ' ');
  return out
    .replace(/\s*\n\s*/g, ' ')
    .replace(/\s*·\s*·\s*/g, ' · ') // 떼고 남은 빈 구분자만 접는다 (정상적인 " · " 는 보존)
    .replace(/^\s*·\s*/, '')
    .replace(/\s*·\s*$/, '')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}
