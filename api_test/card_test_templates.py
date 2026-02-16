#!/usr/bin/env python3
"""
카드뉴스 템플릿 테스트 — 아이디어 1번 & 2번 샘플
더미 데이터로 틀만 확인
"""
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

OUTPUT_DIR = '/Users/twinssn/Projects/aikorea24/api_test/card_output'
os.makedirs(OUTPUT_DIR, exist_ok=True)
FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'

def f(size, idx=0):
    try: return ImageFont.truetype(FONT, size, index=idx)
    except: return ImageFont.truetype(FONT, size, index=0)

# 색상
BG = (17, 17, 28)
WHITE = (235, 235, 242)
ACCENT = (90, 140, 255)
DIM = (55, 60, 80)
SUB = (100, 106, 125)
LINE = (40, 42, 58)
YELLOW = (255, 214, 70)

def make_bg(W, H):
    img = Image.new('RGB', (W, H), BG)
    g1 = Image.new('RGB', (W, H), (0,0,0))
    ImageDraw.Draw(g1).ellipse([-200,-300,500,400], fill=(30,50,120))
    g1 = g1.filter(ImageFilter.GaussianBlur(180))
    g2 = Image.new('RGB', (W, H), (0,0,0))
    ImageDraw.Draw(g2).ellipse([W-500,H-500,W+200,H+100], fill=(50,20,80))
    g2 = g2.filter(ImageFilter.GaussianBlur(200))
    img = ImageChops.add(img, g1)
    img = ImageChops.add(img, g2)
    return img

def center_x(draw, text, font, W):
    bb = draw.textbbox((0,0), text, font=font)
    return (W - (bb[2]-bb[0])) // 2

# ========================================
# 아이디어 1: "1개만 깊게" 카드
# ========================================
def template_1_deep_single():
    W, H = 1080, 1350
    img = make_bg(W, H)
    draw = ImageDraw.Draw(img)
    ML = 80

    now = datetime.now()
    weekdays = ['월','화','수','목','금','토','일']

    # 상단
    y = 55
    draw.text((ML, y), 'AI코리아24', fill=ACCENT, font=f(24,3))
    ds = f"{now.strftime('%Y.%m.%d')} {weekdays[now.weekday()]}"
    db = draw.textbbox((0,0), ds, font=f(20))
    draw.text((W-80-(db[2]-db[0]), y+2), ds, fill=SUB, font=f(20))

    y += 50
    draw.text((ML, y), '오후 AI 뉴스 · 오늘의 PICK', fill=SUB, font=f(20))
    y += 40
    draw.line([(ML,y),(W-80,y)], fill=LINE, width=1)

    # 큰 숫자
    y += 50
    draw.text((ML, y), '01', fill=ACCENT, font=f(100,5))

    # 제목 (크게)
    y += 130
    title = 'AI기본법 시행,'
    title2 = '무엇이 바뀌나'
    draw.text((ML, y), title, fill=WHITE, font=f(52,5))
    draw.text((ML, y+62), title2, fill=WHITE, font=f(52,5))

    # 요약 (3줄, 읽을거리)
    y += 170
    lines = [
        '2월부터 시행되는 AI기본법은 고위험 AI에',
        '대한 안전 의무를 부과합니다. 의료·채용·',
        '금융 분야 AI는 사전 영향평가가 필수이며...'
    ]
    for line in lines:
        draw.text((ML, y), line, fill=(180,183,195), font=f(28))
        y += 42

    # "나머지 4개는" 유도
    y += 50
    draw.line([(ML,y),(W-80,y)], fill=LINE, width=1)
    y += 35

    draw.text((ML, y), '오늘의 AI 뉴스 4개 더 보기', fill=SUB, font=f(24))
    y += 35

    others = [
        '· 솔트룩스, 다이퀘스트 152억 투자유치',
        '· LG·SKT AI 인재 양성 확대',
        '· AI로 학습 격차 줄인다',
        '· 효돌이 노인돌봄 로봇 1만 가구 보급',
    ]
    for ot in others:
        draw.text((ML+10, y), ot, fill=DIM, font=f(22))
        y += 32

    # CTA
    y += 30
    cta_text = '▶  aikorea24.kr/news'
    cx = center_x(draw, cta_text, f(30,3), W)
    # CTA 배경 박스
    ctb = draw.textbbox((0,0), cta_text, font=f(30,3))
    cw = ctb[2]-ctb[0]
    ch = ctb[3]-ctb[1]
    draw.rounded_rectangle(
        [cx-25, y-12, cx+cw+25, y+ch+18],
        radius=12, fill=(90,140,255,40), outline=ACCENT, width=1
    )
    draw.text((cx, y), cta_text, fill=ACCENT, font=f(30,3))

    # 하단
    footer_y = H - 100
    draw.line([(ML, footer_y), (W-80, footer_y)], fill=LINE, width=1)
    brand = 'aikorea24.kr'
    bx = center_x(draw, brand, f(36,5), W)
    draw.text((bx, footer_y+25), brand, fill=ACCENT, font=f(36,5))
    slogan = 'AI, 누구나 쓸 수 있습니다'
    sx = center_x(draw, slogan, f(18), W)
    draw.text((sx, footer_y+65), slogan, fill=SUB, font=f(18))

    fp = os.path.join(OUTPUT_DIR, 'template_1_deep_single.png')
    img.save(fp, 'PNG', quality=95)
    print(f'[템플릿1] 저장: {fp}')
    return fp


# ========================================
# 아이디어 2: "퀴즈형" 카드
# ========================================
def template_2_quiz():
    W, H = 1080, 1350
    img = make_bg(W, H)
    draw = ImageDraw.Draw(img)
    ML = 80

    now = datetime.now()
    weekdays = ['월','화','수','목','금','토','일']

    # 상단
    y = 55
    draw.text((ML, y), 'AI코리아24', fill=ACCENT, font=f(24,3))
    ds = f"{now.strftime('%Y.%m.%d')} {weekdays[now.weekday()]}"
    db = draw.textbbox((0,0), ds, font=f(20))
    draw.text((W-80-(db[2]-db[0]), y+2), ds, fill=SUB, font=f(20))

    y += 50
    draw.text((ML, y), '오후 AI 뉴스 퀴즈', fill=SUB, font=f(20))
    y += 40
    draw.line([(ML,y),(W-80,y)], fill=LINE, width=1)

    # 큰 물음표
    y += 60
    qx = center_x(draw, '?', f(180,5), W)
    draw.text((qx, y), '?', fill=YELLOW, font=f(180,5))

    # 질문
    y += 230
    q1 = '오늘 AI 뉴스 중'
    q2 = '가장 큰 금액은?'
    qx1 = center_x(draw, q1, f(44,3), W)
    qx2 = center_x(draw, q2, f(52,5), W)
    draw.text((qx1, y), q1, fill=WHITE, font=f(44,3))
    draw.text((qx2, y+60), q2, fill=WHITE, font=f(52,5))

    # 보기
    y += 170
    choices = [
        ('A', '52억 원'),
        ('B', '152억 원'),
        ('C', '3,000억 원'),
    ]
    for letter, text in choices:
        # 보기 박스
        box_w = W - ML*2
        draw.rounded_rectangle(
            [ML, y, ML+box_w, y+70],
            radius=14, fill=(30,32,48), outline=LINE, width=1
        )
        draw.text((ML+25, y+18), letter, fill=ACCENT, font=f(28,5))
        draw.text((ML+70, y+20), text, font=f(28,3), fill=WHITE)
        y += 90

    # 정답 유도
    y += 30
    hint = '정답과 해설은 👇'
    hx = center_x(draw, hint, f(26), W)
    draw.text((hx, y), hint, fill=SUB, font=f(26))

    # CTA
    y += 55
    cta = '▶  aikorea24.kr/news'
    cx = center_x(draw, cta, f(30,3), W)
    ctb = draw.textbbox((0,0), cta, font=f(30,3))
    cw = ctb[2]-ctb[0]
    ch = ctb[3]-ctb[1]
    draw.rounded_rectangle(
        [cx-25, y-12, cx+cw+25, y+ch+18],
        radius=12, outline=YELLOW, width=2
    )
    draw.text((cx, y), cta, fill=YELLOW, font=f(30,3))

    # 하단
    footer_y = H - 100
    draw.line([(ML, footer_y), (W-80, footer_y)], fill=LINE, width=1)
    brand = 'aikorea24.kr'
    bx = center_x(draw, brand, f(36,5), W)
    draw.text((bx, footer_y+25), brand, fill=ACCENT, font=f(36,5))
    slogan = 'AI, 누구나 쓸 수 있습니다'
    sx = center_x(draw, slogan, f(18), W)
    draw.text((sx, footer_y+65), slogan, fill=SUB, font=f(18))

    fp = os.path.join(OUTPUT_DIR, 'template_2_quiz.png')
    img.save(fp, 'PNG', quality=95)
    print(f'[템플릿2] 저장: {fp}')
    return fp


if __name__ == '__main__':
    print('카드뉴스 템플릿 샘플 생성\n')
    template_1_deep_single()
    template_2_quiz()
    print('\n모두 완료!')
