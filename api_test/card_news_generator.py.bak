#!/usr/bin/env python3
"""
AI코리아24 카드뉴스 자동 생성기 v4.0
5가지 템플릿 랜덤 — 실전 버전
"""
import os, json, subprocess, random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from openai import OpenAI

# ── 환경 ──
def load_env(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or '=' not in line: continue
            line = line.replace('export ', '')
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env('/Users/twinssn/Projects/aikorea24/api_test/.env.sh')
PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'api_test', 'card_output')
os.makedirs(OUTPUT_DIR, exist_ok=True)
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'

def ft(size, idx=0):
    try: return ImageFont.truetype(FONT, size, index=idx)
    except: return ImageFont.truetype(FONT, size, index=0)

def ft_thin(size): return ft(size, 10)
def ft_light(size): return ft(size, 8)
def ft_reg(size): return ft(size, 0)
def ft_med(size): return ft(size, 2)
def ft_semi(size): return ft(size, 4)
def ft_bold(size): return ft(size, 6)

# ── 색상 (연갈색 골드) ──
BG = (28, 22, 18)
WHITE = (245, 238, 225)
ACCENT = (215, 175, 100)
DIM = (80, 68, 55)
SUB = (140, 125, 105)
LINE = (55, 48, 38)
YELLOW = (245, 210, 110)
LIGHT_GRAY = (195, 182, 165)

W, H = 1080, 1080
ML = 80

def make_bg():
    img = Image.new('RGB', (W, H), BG)
    g1 = Image.new('RGB', (W, H), (0,0,0))
    ImageDraw.Draw(g1).ellipse([-200,-300,600,500], fill=(60,40,15))
    g1 = g1.filter(ImageFilter.GaussianBlur(140))
    g2 = Image.new('RGB', (W, H), (0,0,0))
    ImageDraw.Draw(g2).ellipse([W-400,H-400,W+300,H+200], fill=(50,30,10))
    g2 = g2.filter(ImageFilter.GaussianBlur(150))
    return ImageChops.add(ImageChops.add(img, g1), g2)

def cx(draw, text, font):
    bb = draw.textbbox((0,0), text, font=font)
    return (W - (bb[2]-bb[0])) // 2

def right_x(draw, text, font):
    bb = draw.textbbox((0,0), text, font=font)
    return W - ML - (bb[2]-bb[0])

def draw_header(draw):
    now = datetime.now()
    wd = ['월','화','수','목','금','토','일']
    y = 55
    draw.text((ML, y), 'AI코리아24', fill=ACCENT, font=ft_bold(28))
    ds = f"{now.strftime('%Y.%m.%d')} {wd[now.weekday()]}"
    draw.text((right_x(draw, ds, ft_reg(22)), y+2), ds, fill=SUB, font=ft_reg(22))
    return y + 50

def draw_footer(draw):
    fy = H - 95
    draw.line([(ML, fy), (W-ML, fy)], fill=LINE, width=1)
    b = 'aikorea24.kr'
    draw.text((cx(draw, b, ft_bold(38)), fy+18), b, fill=ACCENT, font=ft_bold(38))
    s = 'AI, 누구나 쓸 수 있습니다'
    draw.text((cx(draw, s, ft_light(19)), fy+60), s, fill=SUB, font=ft_light(19))

def draw_cta(draw, y, color=ACCENT):
    cta = '▶  aikorea24.kr'
    x = cx(draw, cta, ft_semi(34))
    bb = draw.textbbox((0,0), cta, font=ft_semi(34))
    cw, ch = bb[2]-bb[0], bb[3]-bb[1]
    draw.rounded_rectangle([x-30, y-14, x+cw+30, y+ch+20], radius=14, outline=color, width=2)
    draw.text((x, y), cta, fill=color, font=ft_semi(34))


# ── DB 뉴스 ──
def fetch_news(limit=30):
    """브리핑 발행된 뉴스 우선, 없으면 최신 뉴스 폴백"""
    # 1) 오늘 발행된 브리핑 뉴스
    today = datetime.now().strftime('%Y-%m-%d')
    cmd_briefing = ['npx','wrangler','d1','execute','aikorea24-db','--remote','--json','--command',
        f"""SELECT n.title, n.description, n.source, n.category, bi.comment
            FROM briefing_items bi
            JOIN briefings b ON b.id = bi.briefing_id
            JOIN news n ON n.id = bi.news_id
            WHERE b.date = '{today}'
            ORDER BY bi.sort_order ASC"""]
    try:
        r = subprocess.run(cmd_briefing, capture_output=True, text=True, cwd=PROJECT_DIR, timeout=30)
        data = json.loads(r.stdout)
        if isinstance(data, list) and len(data) > 0 and 'results' in data[0]:
            results = data[0]['results']
            if len(results) >= 3:
                print(f'  브리핑 뉴스 {len(results)}건 사용')
                return results
    except: pass

    # 2) 폴백: 최신 뉴스
    print('  브리핑 없음 → 최신 뉴스 폴백')
    cmd_latest = ['npx','wrangler','d1','execute','aikorea24-db','--remote','--json','--command',
        f"""SELECT title, description, source, category FROM news
            WHERE created_at >= datetime('now', '-1 days')
            ORDER BY created_at DESC LIMIT {limit}"""]
    try:
        r = subprocess.run(cmd_latest, capture_output=True, text=True, cwd=PROJECT_DIR, timeout=30)
        data = json.loads(r.stdout)
        if isinstance(data, list) and len(data) > 0 and 'results' in data[0]:
            return data[0]['results']
    except: pass
    return []


# ── AI 큐레이션 (템플릿별 프롬프트) ──
def curate(news_items, template_type):
    news_text = '\n'.join([
        f"- [{n.get('source','')}] {n['title']}: {n.get('description','')[:200]}"
        + (f"\n  [참고] {n['comment']}" if n.get('comment') else '')
        for n in news_items
    ])

    prompts = {
        'deep': f"""아래 AI 뉴스 전부를 사용하세요. 가장 임팩트 있는 1개를 골라 깊게 분석하고,
나머지는 제목만 짧게. 제공된 뉴스 외에 다른 내용을 추가하지 마세요.

{news_text}

JSON으로 응답:
{{
  "main": {{
    "title_line1": "제목 첫줄 (10자 이내)",
    "title_line2": "제목 둘째줄 (10자 이내)",
    "summary_lines": ["요약 1줄 (25자)", "요약 2줄 (25자)", "요약 3줄 (끝에 ... 붙여서 궁금증 유발)"]
  }},
  "others": ["나머지 뉴스1 (15자)", "나머지 뉴스2", "나머지 뉴스3", "나머지 뉴스4"]
}}""",

        'quiz': f"""아래 AI 뉴스에서 퀴즈를 만드세요.
뉴스 속 숫자, 기업명, 기술명 등에서 퀴즈를 출제하세요.
정답은 뉴스에 나온 사실이어야 합니다.

{news_text}

JSON으로 응답:
{{
  "question_line1": "질문 첫줄 (12자 이내)",
  "question_line2": "질문 둘째줄 (12자 이내, 핵심)",
  "choices": [
    {{"letter": "A", "text": "오답 (8자 이내)"}},
    {{"letter": "B", "text": "정답 (8자 이내)"}},
    {{"letter": "C", "text": "오답 (8자 이내)"}}
  ],
  "answer": "B",
  "hint": "힌트 한 줄 (20자 이내)"
}}""",

        'carousel_cover': f"""아래 AI 뉴스 전부를 빠짐없이 사용하세요. 절대 다른 뉴스를 추가하지 마세요.
각 뉴스에서 인상적인 숫자를 뽑으세요. 숫자가 없으면 핵심 키워드(예: "GPT-5", "오픈소스", "국방부")를 number에 넣으세요.
절대 N/A, '용어미정', 'TBD' 등 placeholder를 사용하지 마세요. 반드시 숫자 또는 키워드(기업명, 기술명, 기관명 등)를 넣어야 합니다.
각 뉴스마다 제목(12자 이내)과 상세코멘트(80~100자, 존댓말로 구체적인 내용과 배경까지 설명, 예: "~합니다", "~됩니다")를 함께 작성하세요.
comment에 "에디터 코멘트 반영" 같은 메타 문구를 절대 포함하지 마세요. 뉴스 내용만 설명하세요.

{news_text}

JSON으로 응답:
{{
  "items": [
    {{"number": "152억", "unit": "원", "context": "다이퀘스트 IPO 투자유치 규모", "title": "12자 이내 제목", "comment": "존댓말로 구체적 설명 80~100자"}},
    {{"number": "GPT-5", "unit": "", "context": "오픈AI 차세대 모델 공개", "title": "12자 이내 제목", "comment": "존댓말로 구체적 설명 80~100자"}},
    ...5개
  ]
}}""",

        'number': f"""아래 AI 뉴스 전부를 빠짐없이 사용하세요. 절대 다른 뉴스를 추가하지 마세요.
각 뉴스에서 인상적인 숫자를 뽑으세요. 숫자가 없으면 핵심 키워드(예: "GPT-5", "오픈소스", "국방부")를 number에 넣으세요.
절대 N/A, '용어미정', 'TBD' 등 placeholder를 사용하지 마세요. 반드시 숫자 또는 키워드(기업명, 기술명, 기관명 등)를 넣어야 합니다.
comment에 "에디터 코멘트 반영" 같은 메타 문구를 절대 포함하지 마세요. 뉴스 내용만 설명하세요.

{news_text}

JSON으로 응답:
{{
  "items": [
    {{"number": "152억", "unit": "원", "context": "다이퀘스트 IPO 투자유치 규모"}},
    {{"number": "클로드", "unit": "", "context": "앤트로픽 AI 모델 업데이트"}},
    ...5개
  ]
}}""",

        'list5': f"""아래 AI 뉴스 전부를 빠짐없이 사용하세요. 제공된 뉴스 외에 다른 내용을 추가하지 마세요.
각 뉴스: 제목(12자 이내), 부연(20자 이내, 말줄임표로 끝나서 궁금증 유발)

{news_text}

JSON으로 응답:
{{
  "items": [
    {{"title": "12자 이내", "teaser": "20자 이내..."}},
    ...5개
  ]
}}"""
    }

    system = ('AI 전문 뉴스 에디터. AI/인공지능 관련 뉴스만 선별. '
              '암호화폐·부동산·정치·스포츠 절대 제외. JSON만 응답.')

    response = client.chat.completions.create(
        model='gpt-5-nano',
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompts[template_type]}
        ],
        max_completion_tokens=4000,
        reasoning_effort="minimal",
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError(f"GPT 빈 응답. finish_reason={response.choices[0].finish_reason}, tokens={response.usage.completion_tokens}")
    content = content.strip()
    if '```' in content:
        content = content.split('```')[1]
        if content.startswith('json'): content = content[4:]
    return json.loads(content)


# ══════════════════════════════════════
# 템플릿 1: 1개만 깊게
# ══════════════════════════════════════
def render_deep(data):
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    draw.text((ML, y), '오늘의 PICK', fill=YELLOW, font=ft_semi(24))
    y += 42
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)

    y += 40
    draw.text((ML, y), '01', fill=ACCENT, font=ft_bold(120))

    y += 145
    m = data['main']
    draw.text((ML, y), m['title_line1'], fill=WHITE, font=ft_bold(62))
    y += 78
    draw.text((ML, y), m['title_line2'], fill=WHITE, font=ft_bold(62))

    y += 95
    for line in m['summary_lines']:
        draw.text((ML, y), line, fill=LIGHT_GRAY, font=ft_reg(32))
        y += 48

    y += 35
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)
    y += 28
    draw.text((ML, y), '오늘의 AI 뉴스 4개 더', fill=SUB, font=ft_med(24))
    y += 40
    for ot in data['others']:
        draw.text((ML+10, y), f'·  {ot}', fill=LIGHT_GRAY, font=ft_reg(26))
        y += 38

    draw_footer(draw)

    fp = os.path.join(OUTPUT_DIR, f'card_deep_{datetime.now().strftime("%Y%m%d_%H%M")}.png')
    img.save(fp, 'PNG', quality=95)
    return fp


# ══════════════════════════════════════
# 템플릿 2: 퀴즈형
# ══════════════════════════════════════
def render_quiz(data):
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    draw.text((ML, y), 'AI 뉴스 퀴즈', fill=YELLOW, font=ft_semi(24))
    y += 40
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)

    # 물음표
    y += 50
    draw.text((cx(draw, '?', ft_bold(180)), y), '?', fill=YELLOW, font=ft_bold(180))

    # 질문
    y += 210
    q1 = data['question_line1']
    q2 = data['question_line2']
    draw.text((cx(draw, q1, ft_semi(48)), y), q1, fill=WHITE, font=ft_semi(48))
    draw.text((cx(draw, q2, ft_bold(56)), y+66), q2, fill=WHITE, font=ft_bold(56))

    # 보기
    y += 160
    answer = data.get('answer', 'B')
    for c in data['choices']:
        box_w = W - ML*2
        is_answer = (c['letter'] == answer)
        outline = YELLOW if is_answer else LINE
        draw.rounded_rectangle([ML, y, ML+box_w, y+70], radius=14, fill=(30,32,48), outline=outline, width=2 if is_answer else 1)
        draw.text((ML+25, y+18), c['letter'], fill=YELLOW if is_answer else ACCENT, font=ft(28,5))
        draw.text((ML+70, y+20), c['text'], font=ft(28,3), fill=WHITE)
        y += 90

    # 힌트
    y += 20
    hint = f"💡 {data.get('hint', '정답은 웹사이트에서!')}"
    draw.text((cx(draw, hint, ft(24)), y), hint, fill=SUB, font=ft(24))

    y += 50
    draw_cta(draw, y, YELLOW)
    draw_footer(draw)

    fp = os.path.join(OUTPUT_DIR, f'card_quiz_{datetime.now().strftime("%Y%m%d_%H%M")}.png')
    img.save(fp, 'PNG', quality=95)
    return fp


# ══════════════════════════════════════
# 템플릿 3: 캐러셀 (표지 + 5장 + CTA)
# ══════════════════════════════════════
def render_carousel(data):
    files = []
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M")
    items = data['items'][:5]
    main = items[0]
    rest = items[1:5]

    # ── 1장: 헤드라인 후킹 (1개 뉴스만 크게) ──
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    draw.text((ML, y), 'TODAY', fill=YELLOW, font=ft_bold(34))
    y += 48
    draw.line([(ML, y), (W - ML, y)], fill=LINE, width=1)

    y += 70
    draw.text((ML, y), '01', fill=ACCENT, font=ft_bold(160))
    y += 190

    title = main.get('title', '')
    if len(title) <= 8:
        draw.text((ML, y), title, fill=WHITE, font=ft_bold(88))
        y += 110
    elif len(title) <= 16:
        mid = len(title) // 2
        sp = title.rfind(' ', 0, mid + 2)
        if sp <= 0:
            sp = mid
        l1 = title[:sp].strip()
        l2 = title[sp:].strip()
        draw.text((ML, y), l1, fill=WHITE, font=ft_bold(78))
        y += 95
        draw.text((ML, y), l2, fill=WHITE, font=ft_bold(78))
        y += 110
    else:
        t1 = title[:12].strip()
        t2 = title[12:24].strip()
        draw.text((ML, y), t1, fill=WHITE, font=ft_bold(70))
        y += 88
        draw.text((ML, y), t2, fill=WHITE, font=ft_bold(70))
        y += 100

    comment = main.get('comment', '')
    if comment:
        y += 15
        c1 = comment[:32]
        draw.text((ML, y), c1, fill=LIGHT_GRAY, font=ft_reg(34))
        y += 48
        if len(comment) > 32:
            c2 = comment[32:64]
            if len(comment) > 64:
                c2 = c2[:29] + '...'
            draw.text((ML, y), c2, fill=LIGHT_GRAY, font=ft_reg(34))
            y += 48

    y += 25
    swipe = '→  밀어서 자세히 보기'
    sx = cx(draw, swipe, ft_semi(30))
    bb = draw.textbbox((0, 0), swipe, font=ft_semi(30))
    sw, sh = bb[2] - bb[0], bb[3] - bb[1]
    draw.rounded_rectangle([sx - 20, y - 10, sx + sw + 20, y + sh + 14], radius=10, outline=ACCENT, width=2)
    draw.text((sx, y), swipe, fill=ACCENT, font=ft_semi(30))

    draw_footer(draw)
    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_1hook.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    # ── 2장: 1번 뉴스 브리핑 상세 ──
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    draw.text((ML, y), 'BRIEFING', fill=YELLOW, font=ft_bold(30))
    y += 42
    draw.line([(ML, y), (W - ML, y)], fill=LINE, width=1)
    y += 55

    title = main.get('title', '')
    if len(title) <= 14:
        draw.text((ML, y), title, fill=WHITE, font=ft_bold(68))
        y += 85
    else:
        mid = len(title) // 2
        sp = title.rfind(' ', 0, mid + 2)
        if sp <= 0:
            sp = mid
        l1 = title[:sp].strip()
        l2 = title[sp:].strip()
        draw.text((ML, y), l1, fill=WHITE, font=ft_bold(62))
        y += 78
        draw.text((ML, y), l2, fill=WHITE, font=ft_bold(62))
        y += 85

    y += 10
    draw.line([(ML, y), (ML + 80, y)], fill=ACCENT, width=3)
    y += 22

    comment = main.get('comment', '')
    context = main.get('context', comment)
    text = context if len(context) > len(comment) else comment
    lines = []
    max_ch = 22
    while text:
        if len(text) <= max_ch:
            lines.append(text)
            break
        sp = text.rfind(' ', 0, max_ch + 1)
        if sp <= 0:
            sp = max_ch
        lines.append(text[:sp].strip())
        text = text[sp:].strip()

    for line in lines[:12]:
        draw.text((ML, y), line, fill=LIGHT_GRAY, font=ft_reg(38))
        y += 54

    y += 15
    more = f'+ 나머지 {len(rest)}개 뉴스 →'
    mx = cx(draw, more, ft_semi(30))
    bb = draw.textbbox((0, 0), more, font=ft_semi(30))
    mw, mh = bb[2] - bb[0], bb[3] - bb[1]
    draw.rounded_rectangle([mx - 20, y - 10, mx + mw + 20, y + mh + 14], radius=10, outline=ACCENT, width=2)
    draw.text((mx, y), more, fill=ACCENT, font=ft_semi(30))

    draw_footer(draw)
    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_2brief.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    # ── 3장: 나머지 4개 리스트 ──
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    draw.text((ML, y), 'MORE NEWS', fill=YELLOW, font=ft_bold(28))
    y += 45
    draw.line([(ML, y), (W - ML, y)], fill=LINE, width=1)
    y += 40

    item_h = 190
    for i, item in enumerate(rest):
        rank = f'0{i+2}'
        title = item.get('title', '')
        comment = item.get('comment', '')

        rank_color = ACCENT if i < 2 else SUB
        draw.text((ML, y), rank, fill=rank_color, font=ft_bold(50))

        tx = ML + 85
        if len(title) > 14:
            title = title[:13] + '…'
        draw.text((tx, y + 2), title, fill=WHITE, font=ft_semi(42))

        if comment:
            cmt1 = comment[:30]
            draw.text((tx, y + 55), cmt1, fill=SUB, font=ft_reg(26))
            if len(comment) > 30:
                cmt2 = comment[30:60]
                if len(comment) > 60:
                    cmt2 = cmt2[:27] + '...'
                draw.text((tx, y + 85), cmt2, fill=SUB, font=ft_reg(26))

        if i < len(rest) - 1:
            draw.line([(tx, y + item_h - 20), (W - ML, y + item_h - 20)], fill=LINE, width=1)

        y += item_h

    draw_footer(draw)
    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_3list.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    # ── 4장: CTA ──
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    try:
        from PIL import Image as PILImage
        cta_img_path = '/Users/twinssn/Projects/aikorea24/public/A0dOS6Jf.jpeg'
        cta_img = PILImage.open(cta_img_path).convert('RGB')
        iw, ih = cta_img.size
        target_w = W - ML * 2
        ratio = target_w / iw
        target_h = int(ih * ratio)
        if target_h > 400:
            target_h = 400
            ratio = target_h / ih
            target_w = int(iw * ratio)
        cta_img = cta_img.resize((target_w, target_h), PILImage.LANCZOS)
        paste_x = (W - target_w) // 2
        img.paste(cta_img, (paste_x, y + 20))
        draw = ImageDraw.Draw(img)
        y += target_h + 50
    except Exception as e:
        print(f'  CTA 이미지 스킵: {e}')
        y += 100

    t1 = 'AI 뉴스, 매일 새롭게'
    draw.text((cx(draw, t1, ft_bold(56)), y), t1, fill=WHITE, font=ft_bold(56))
    y += 75

    t2 = 'aikorea24.kr'
    draw.text((cx(draw, t2, ft_bold(64)), y), t2, fill=ACCENT, font=ft_bold(64))
    y += 90

    t3 = '브리핑 · 도구 · 용어 · 연대기'
    draw.text((cx(draw, t3, ft_reg(30)), y), t3, fill=SUB, font=ft_reg(30))

    draw_footer(draw)
    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_4cta.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    return files


# ══════════════════════════════════════
# 템플릿 4: 숫자 강조
# ══════════════════════════════════════
# 템플릿 4: 숫자 강조
# ══════════════════════════════════════
def render_numbers(data):
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    items = data['items']
    count = len(items)

    # 동적 크기 계산 - 아이템 수에 따라 카드 꽉 채우기
    available_h = 1700 - y - 120  # 헤더/푸터 제외 가용 높이
    title_area = 70  # 제목 + 구분선

    if count <= 3:
        num_size = 130
        unit_size = 56
        ctx_size = 48
        num_weight = 5
        unit_offset_y = 45
        ctx_offset_y = 140
        item_h = (available_h - title_area) // count
    elif count <= 5:
        num_size = 100
        unit_size = 48
        ctx_size = 42
        num_weight = 5
        unit_offset_y = 38
        ctx_offset_y = 110
        item_h = (available_h - title_area) // count
    else:
        num_size = 80
        unit_size = 40
        ctx_size = 36
        num_weight = 4
        unit_offset_y = 30
        ctx_offset_y = 90
        item_h = (available_h - title_area) // count

    draw.text((ML, y), '오늘의 AI 숫자', fill=YELLOW, font=ft_semi(34))
    y += 30
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)
    y += 40

    for i, item in enumerate(items):
        num_text = str(item['number'])
        unit = item.get('unit', '')
        context = item.get('context', '')

        color = YELLOW if i < 2 else ACCENT
        draw.text((ML, y), num_text, fill=color, font=ft(num_size, num_weight))

        nb = draw.textbbox((0,0), num_text, font=ft(num_size, num_weight))
        nw = nb[2] - nb[0]
        if unit:
            draw.text((ML + nw + 12, y + unit_offset_y), unit, fill=SUB, font=ft(unit_size, 3))

        draw.text((ML, y + ctx_offset_y), context, fill=LIGHT_GRAY, font=ft(ctx_size))

        if i < count - 1:
            draw.line([(ML, y + item_h - 15),(W-ML, y + item_h - 15)], fill=LINE, width=1)

        y += item_h

    y += 10
    draw_cta(draw, y)
    draw_footer(draw)

    fp = os.path.join(OUTPUT_DIR, f'card_numbers_{datetime.now().strftime("%Y%m%d_%H%M")}.png')
    img.save(fp, 'PNG', quality=95)
    return fp


# ══════════════════════════════════════
# 템플릿 5: 리스트 5개 + 티저
# ══════════════════════════════════════
def render_list5(data):
    img = make_bg()
    draw = ImageDraw.Draw(img)
    y = draw_header(draw)

    period = '오전' if datetime.now().hour < 12 else '오후'
    draw.text((ML, y), f'{period} AI 뉴스', fill=YELLOW, font=ft_semi(24))
    y += 40
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)
    y += 45

    item_h = 185
    for i, item in enumerate(data['items'][:5]):
        rank_color = ACCENT if i < 2 else DIM
        draw.text((ML, y), f'{i+1}', fill=rank_color, font=ft_bold(48))

        tx = ML + 65
        draw.text((tx, y+2), item['title'], fill=WHITE, font=ft_semi(44))
        draw.text((tx, y+55), item['teaser'], fill=SUB, font=ft_reg(28))

        if i < 4:
            draw.line([(tx, y+item_h-20),(W-ML, y+item_h-20)], fill=LINE, width=1)

        y += item_h

    y += 10
    draw_cta(draw, y)
    draw_footer(draw)

    fp = os.path.join(OUTPUT_DIR, f'card_list5_{datetime.now().strftime("%Y%m%d_%H%M")}.png')
    img.save(fp, 'PNG', quality=95)
    return fp


# ══════════════════════════════════════
# 메인
# ══════════════════════════════════════
TEMPLATES = ['deep', 'quiz', 'carousel_cover', 'number', 'list5']

def generate_card_news(template_type=None):
    now = datetime.now()
    period = '오전' if now.hour < 12 else '오후'

    if template_type is None:
        template_type = 'carousel_cover'

    print('\n' + '=' * 50)
    print(f'카드뉴스 v4 — {now.strftime("%Y-%m-%d %H:%M")} {period}')
    print(f'템플릿: {template_type}')
    print('=' * 50)

    print('\n[1] DB 뉴스 로드...')
    news = fetch_news(30)
    print(f'  {len(news)}건')
    if len(news) < 3:
        print('  부족. 스킵.')
        return None

    print(f'\n[2] AI 큐레이션 ({template_type})...')
    data = curate(news, template_type)
    print(f'  완료')
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])

    print(f'\n[3] 이미지 생성...')
    renderers = {
        'deep': render_deep,
        'quiz': render_quiz,
        'carousel_cover': render_carousel,
        'number': render_numbers,
        'list5': render_list5,
    }
    result = renderers[template_type](data)

    if isinstance(result, list):
        print(f'\n완료! {len(result)}장:')
        for f in result: print(f'  {f}')
    else:
        print(f'\n완료! {result}')

    return result


if __name__ == '__main__':
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else None
    generate_card_news(t)
