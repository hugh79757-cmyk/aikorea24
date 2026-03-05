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

# ── 색상 ──
BG = (17, 17, 28)
WHITE = (235, 235, 242)
ACCENT = (90, 140, 255)
DIM = (55, 60, 80)
SUB = (100, 106, 125)
LINE = (40, 42, 58)
YELLOW = (255, 214, 70)
LIGHT_GRAY = (180, 183, 195)

W, H = 1080, 1080
ML = 80

def make_bg():
    img = Image.new('RGB', (W, H), BG)
    g1 = Image.new('RGB', (W, H), (0,0,0))
    ImageDraw.Draw(g1).ellipse([-200,-300,500,400], fill=(30,50,120))
    g1 = g1.filter(ImageFilter.GaussianBlur(180))
    g2 = Image.new('RGB', (W, H), (0,0,0))
    ImageDraw.Draw(g2).ellipse([W-500,H-500,W+200,H+100], fill=(50,20,80))
    g2 = g2.filter(ImageFilter.GaussianBlur(200))
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
    draw.text((ML, y), 'AI코리아24', fill=ACCENT, font=ft(24,3))
    ds = f"{now.strftime('%Y.%m.%d')} {wd[now.weekday()]}"
    draw.text((right_x(draw, ds, ft(20)), y+2), ds, fill=SUB, font=ft(20))
    return y + 50

def draw_footer(draw):
    fy = H - 100
    draw.line([(ML, fy), (W-ML, fy)], fill=LINE, width=1)
    b = 'aikorea24.kr'
    draw.text((cx(draw, b, ft(36,5)), fy+25), b, fill=ACCENT, font=ft(36,5))
    s = 'AI, 누구나 쓸 수 있습니다'
    draw.text((cx(draw, s, ft(18)), fy+65), s, fill=SUB, font=ft(18))

def draw_cta(draw, y, color=ACCENT):
    cta = '▶  aikorea24.kr'
    x = cx(draw, cta, ft(30,3))
    bb = draw.textbbox((0,0), cta, font=ft(30,3))
    cw, ch = bb[2]-bb[0], bb[3]-bb[1]
    draw.rounded_rectangle([x-25, y-12, x+cw+25, y+ch+18], radius=12, outline=color, width=2)
    draw.text((x, y), cta, fill=color, font=ft(30,3))


# ── DB 뉴스 ──
def fetch_news(limit=30):
    """브리핑 발행된 뉴스 우선, 없으면 최신 뉴스 폴백"""
    # 1) 오늘 발행된 브리핑 뉴스
    today = datetime.now().strftime('%Y-%m-%d')
    cmd_briefing = ['npx','wrangler','d1','execute','aikorea24-db','--remote','--json','--command',
        f"""SELECT n.title, n.description, n.source, n.category
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
    news_text = '\n'.join([f"- [{n.get('source','')}] {n['title']}: {n.get('description','')[:80]}" for n in news_items])

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
절대 N/A를 사용하지 마세요. 반드시 숫자 또는 키워드를 넣어야 합니다.
각 뉴스마다 제목(12자 이내)과 상세코멘트(80~100자, 존댓말로 구체적인 내용과 배경까지 설명, 예: "~합니다", "~됩니다")를 함께 작성하세요.

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
절대 N/A를 사용하지 마세요. 반드시 숫자 또는 키워드를 넣어야 합니다.

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

    draw.text((ML, y), '오늘의 PICK', fill=SUB, font=ft(20))
    y += 40
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)

    # 큰 번호
    y += 50
    draw.text((ML, y), '01', fill=ACCENT, font=ft(100,5))

    # 제목
    y += 130
    m = data['main']
    draw.text((ML, y), m['title_line1'], fill=WHITE, font=ft(52,5))
    draw.text((ML, y+62), m['title_line2'], fill=WHITE, font=ft(52,5))

    # 요약
    y += 170
    for line in m['summary_lines']:
        draw.text((ML, y), line, fill=LIGHT_GRAY, font=ft(28))
        y += 42

    # 나머지 4개
    y += 45
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)
    y += 30
    draw.text((ML, y), '오늘의 AI 뉴스 4개 더', fill=SUB, font=ft(22))
    y += 35
    for ot in data['others']:
        draw.text((ML+10, y), f'·  {ot}', fill=DIM, font=ft(22))
        y += 32

    # CTA
    y += 35
    draw_cta(draw, y)
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

    draw.text((ML, y), 'AI 뉴스 퀴즈', fill=SUB, font=ft(20))
    y += 40
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)

    # 물음표
    y += 50
    draw.text((cx(draw, '?', ft(160,5)), y), '?', fill=YELLOW, font=ft(160,5))

    # 질문
    y += 210
    q1 = data['question_line1']
    q2 = data['question_line2']
    draw.text((cx(draw, q1, ft(42,3)), y), q1, fill=WHITE, font=ft(42,3))
    draw.text((cx(draw, q2, ft(50,5)), y+58), q2, fill=WHITE, font=ft(50,5))

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

    # 표지: 숫자 강조 스타일 (5개 뉴스 한눈에)
    img = make_bg()
    draw = ImageDraw.Draw(img)
    draw_header(draw)

    subtitle = '오늘의 AI 숫자'
    draw.text((80, 80), subtitle, fill=SUB, font=ft(26))

    items = data['items'][:5]
    y = 120
    item_h = 150
    for i, item in enumerate(items):
        num_val = str(item.get('number', str(i+1)))
        unit_val = item.get('unit', '')
        ctx = item.get('context', item.get('comment', ''))

        # 숫자 (1번 2번만 노란색, 나머지 기존 ACCENT)
        num_color = (255, 200, 50) if i < 2 else ACCENT
        num_str = num_val + (' ' + unit_val if unit_val else '')
        nx = cx(draw, num_str, ft(54, 5))
        draw.text((nx, y), num_val, fill=num_color, font=ft(54, 5))
        if unit_val:
            nb = draw.textbbox((0, 0), num_val, font=ft(54, 5))
            draw.text((nx + nb[2] - nb[0] + 10, y + 18), unit_val, fill=SUB, font=ft(27))

        # 설명
        ctx_short = ctx[:25]
        draw.text((cx(draw, ctx_short, ft(28)), y + 68), ctx_short, fill=LIGHT_GRAY, font=ft(28))

        # 구분선
        if i < 4:
            line_y = y + item_h - 15
            draw.line([(80, line_y), (W - 80, line_y)], fill=(255, 255, 255, 40), width=1)

        y += item_h

    draw_footer(draw)

    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_0cover.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    # 요약 페이지 (5개 뉴스를 1장에 모두)
    items = data['items'][:5]
    img = make_bg()
    draw = ImageDraw.Draw(img)
    draw_header(draw)

    y = 75
    item_h = 185

    for i, item in enumerate(items):
        title = item.get('title', '')
        comment = item.get('comment', '')

        # 번호 + 제목 (가운데 정렬)
        num_text = f'{i+1}'
        max_title = 13
        if len(title) > max_title:
            title = title[:max_title] + '…'
        header_text = f'{num_text}   {title}'
        hx = cx(draw, header_text, ft(44, 5))
        draw.text((hx, y), num_text, fill=(255, 200, 50), font=ft(44, 5))
        nb = draw.textbbox((0, 0), num_text + '   ', font=ft(44, 5))
        draw.text((hx + nb[2] - nb[0], y), title, fill=WHITE, font=ft(44, 5))

        # 코멘트 2줄 (가운데 정렬)
        y += 58
        comment_font = ft(26)
        max_per_line = 26
        if len(comment) <= max_per_line:
            draw.text((cx(draw, comment, comment_font), y), comment, fill=LIGHT_GRAY, font=comment_font)
            y += 34
        else:
            sp = comment.rfind(' ', 0, max_per_line + 1)
            if sp <= 0:
                sp = max_per_line
            l1 = comment[:sp].strip()
            l2 = comment[sp:].strip()
            if len(l2) > max_per_line:
                l2 = l2[:max_per_line - 1] + '…'
            draw.text((cx(draw, l1, comment_font), y), l1, fill=LIGHT_GRAY, font=comment_font)
            draw.text((cx(draw, l2, comment_font), y + 34), l2, fill=LIGHT_GRAY, font=comment_font)
            y += 68
        if False:
            pass

        # 구분선
        if i < len(items) - 1:
            y += 12
            draw.line([(60, y), (W - 60, y)], fill=(255, 255, 255, 40), width=1)
            y += 18

    draw_footer(draw)
    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_1.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    # CTA 장
    img = make_bg()
    draw = ImageDraw.Draw(img)
    draw_header(draw)

    # 챗봇 이미지 삽입 (중앙, 아래로 내림)
    try:
        from PIL import Image as PILImage
        chatbot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'public', 'aikorea24.jpg')
        chatbot = PILImage.open(chatbot_path).convert('RGBA')
        img_size = 300
        chatbot = chatbot.resize((img_size, img_size), PILImage.LANCZOS)
        paste_x = (W - img_size) // 2
        img.paste(chatbot, (paste_x, 120), chatbot if chatbot.mode == 'RGBA' else None)
        draw = ImageDraw.Draw(img)
    except Exception as e:
        print(f'  이미지 삽입 스킵: {e}')

    y = 460
    t1 = '이 카드뉴스,'
    t1b = 'AI에게 말만 했습니다'
    draw.text((cx(draw, t1, ft(52)), y), t1, fill=(255, 200, 50), font=ft(52))
    y += 65
    draw.text((cx(draw, t1b, ft(52, 5)), y), t1b, fill=(255, 200, 50), font=ft(52, 5))

    y += 80
    t2 = '코딩 도구 없이'
    t2b = '대화만으로 모두 가능합니다'
    draw.text((cx(draw, t2, ft(52, 5)), y), t2, fill=WHITE, font=ft(52, 5))
    y += 65
    draw.text((cx(draw, t2b, ft(52, 5)), y), t2b, fill=WHITE, font=ft(52, 5))

    y += 75
    t3 = '뉴스 수집 · 블로그 자동 발행 · 관광지 소개'
    draw.text((cx(draw, t3, ft(30)), y), t3, fill=SUB, font=ft(30))

    y += 45
    t4 = '자격증 · 문화유산 · 키워드 분석 · 메모 동기화'
    draw.text((cx(draw, t4, ft(28)), y), t4, fill=LIGHT_GRAY, font=ft(28))

    y += 70
    t5 = '바이브코딩 무료로 배워보세요'
    draw.text((cx(draw, t5, ft(52, 5)), y), t5, fill=WHITE, font=ft(52, 5))

    y += 80
    draw_footer(draw)

    fp = os.path.join(OUTPUT_DIR, f'card_carousel_{ts}_2cta.png')
    img.save(fp, 'PNG', quality=95)
    files.append(fp)

    return files


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

    draw.text((ML, y), '오늘의 AI 숫자', fill=SUB, font=ft(32))
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
    draw.text((ML, y), f'{period} AI 뉴스', fill=SUB, font=ft(20))
    y += 40
    draw.line([(ML,y),(W-ML,y)], fill=LINE, width=1)
    y += 45

    item_h = 185
    for i, item in enumerate(data['items'][:5]):
        rank_color = ACCENT if i < 2 else DIM
        draw.text((ML, y), f'{i+1}', fill=rank_color, font=ft(44,5))

        tx = ML + 65
        draw.text((tx, y+2), item['title'], fill=WHITE, font=ft(40,3))
        draw.text((tx, y+52), item['teaser'], fill=SUB, font=ft(24))

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
