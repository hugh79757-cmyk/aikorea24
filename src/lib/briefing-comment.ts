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
 * 수집기가 제목 앞에 붙이는 내부 표식 (AIK24-PIPE-05 §제목 표시 교정).
 *
 * news.title 은 선정기·로그가 쓰는 기계 표식으로 시작한다:
 *   · "[제외] cat-jam-free — OpenCode Zen 무료 목록에서 제외"
 *   · "[신규 무료] reflection/beam-free — Kilo Free Models 무료 목록에 추가"
 *   · "[무료 LLM] beam-free — OpenCode Zen 무료 티어"
 * 이 문자열이 그대로 브리핑 카드 제목이 되어 독자에게 "무료 목록에서 제외" 같은
 * 라벨이 노출됐다(2026-10-18 브리핑 #item-1·#item-2). 카드 제목은 문장이어야 하므로
 * 표식을 문장으로 바꾼다. 표식 자체는 선정기 배제 필터(EXCLUDED_TITLE_PREFIXES)와
 * 수집 로그가 계속 쓰므로 DB 값을 바꾸지 않고 표시 단계에서만 정리한다.
 *
 * 여기서 다루지 않는 대괄호 접두어([게시판]·[속보]·[전남광주] 등)는 언론사가 붙인
 * 실제 제목의 일부이므로 손대지 않는다. 내부 표식 3종만 대상이다.
 */
const INTERNAL_TITLE_TAG = /^\s*\[(?:제외|신규 무료|무료 LLM)\]\s*/;

export function cleanBriefingTitle(title: string | null | undefined): string {
  if (!title) return '';
  const t = String(title).trim();

  // "[제외] {모델} — {제공사} 무료 목록에서 제외"
  const removed = t.match(/^\[제외\]\s*(.+?)\s*—\s*(.+?)\s*무료 목록에서\s*제외$/);
  if (removed) return `${removed[2]} 무료 목록에서 ${removed[1]} 모델이 제외되었습니다`;

  // "[신규 무료] {모델} — {제공사} 무료 목록에 추가"
  const added = t.match(/^\[신규 무료\]\s*(.+?)\s*—\s*(.+?)\s*무료 목록에\s*추가$/);
  if (added) return `${added[2]} 무료 목록에 ${added[1]} 모델이 추가되었습니다`;

  // "[무료 LLM] {모델} — {제공사} 무료 티어"
  const tier = t.match(/^\[무료 LLM\]\s*(.+?)\s*—\s*(.+?)\s*무료 티어$/);
  if (tier) return `${tier[2]} 무료 티어에 ${tier[1]} 모델이 포함되어 있습니다`;

  // 위 3종에 해당하지 않는 내부 표식은 떼어낸다 (표식이 독자 화면에 남지 않게)
  return t.replace(INTERNAL_TITLE_TAG, '');
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
