from __future__ import annotations
import asyncio
import re
from typing import Optional
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

from pipeline.instagram.content_converter import convert_format_d_to_carousel, convert_format_d_to_reel_script
from pipeline.instagram.models import SlideType, InstagramSlide, InstagramReelScene

# ──────────────────────────────────────────────
# 템플릿 환경 설정
# ──────────────────────────────────────────────
template_env = Environment(
    loader=FileSystemLoader("/Users/twinssn/Projects/aikorea24/scripts/threads/v3/auto_poster/templates"),
    autoescape=True,
)


async def render_cards_to_png(cards: list, output_dir: str = "cards") -> list[str]:
    """Format D 카드 리스트 또는 InstagramSlide 리스트 → PNG 이미지 파일들로 변환"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # 1) Format D 카드 리스트(str)인 경우에만 변환
    from pipeline.instagram.content_converter import convert_format_d_to_carousel
    if cards and isinstance(cards[0], str):
        slides = convert_format_d_to_carousel(cards)
    else:
        # 이미 InstagramSlide 객체 리스트인 경우
        slides = cards
    
    # 2) 각 슬라이드 HTML 렌더링 → PNG 저장
    png_paths = []
    carousel_template = template_env.get_template("carousel.html")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})
        
        for i, slide in enumerate(slides):
            html = carousel_template.render(slide=slide)
            await page.set_content(html, wait_until="networkidle")
            await page.wait_for_timeout(300)  # 폰트/이미지 로딩 대기
            
            png_path = f"slide_{i+1}.png"
            png_full = f"/Users/twinssn/Projects/aikorea24/{output_dir}/{png_path}"
            await page.screenshot(path=png_full, full_page=True)
            png_paths.append(png_full)
            print(f"✅ PNG 생성: {png_full}")
        
        await browser.close()
    
    return png_paths


async def render_reels_html(reel_scenes: list) -> str:
    """Reels용 HTML 전체 렌더링 (씬 전체를 한 페이지에)"""
    from pipeline.instagram.models import InstagramReelScene
    
    template = template_env.get_template("reels.html")
    
    # 씬 타입별 이모지/색상
    type_colors = {
        "hook": ("#3b82f6", "🔥"),
        "conflict": ("#ef4444", "⚠️"),
        "twist": ("#a855f7", "⚡"),
        "expansion": ("#3b82f6", "📊"),
        "cta": ("#22c55e", "🎯"),
        "link": ("#f97316", "🔗"),
    }
    
    scenes_with_colors = []
    for i, scene in enumerate(reel_scenes):
        scene_type = ["hook", "conflict", "twist", "expansion", "cta", "link"][scene.scene_index % 6]
        color, emoji = scene_colors.get(scene_type, ("#3b82f6", "📌"))
        scenes_with_colors.append({
            **scene.__dict__,
            "scene_index": i,
            "emoji": emoji,
            "color": color,
        })
    
    html = template.render(
        scenes=scenes_with_colors,
        scene_colors=dict(scenes_with_colors),
    )
    return html


async def render_reels_to_png(reel_scenes: list, output_path: str = "reels_scene.png") -> str:
    """Reels HTML → 단일 PNG (디버깅/프리뷰용)"""
    import os
    os.makedirs("/Users/twinssn/Projects/aikorea24/instagram-reel-output", exist_ok=True)
    
    html = await render_reels_html(reel_scenes)
    output_path = f"/Users/twinssn/Projects/aikorea24/instagram-reel-output/{output_path}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.screenshot(path=output_path, full_page=True)
        await browser.close()
    
    return output_path


async def main():
    """테스트용"""
    test_cards = [
        "틱톡이 감원한다던 667명의 정체, 공식 발표는 300명이지만 내부 문건엔 2배 넘는 숫자.",
        "자살 챌린지 영상 올리는 놈들은 알고리즘 피하는 데 도가 텄다. 유해 콘텐츠는 계속 바뀌기 때문에 AI도 사람이 계속 업데이트해줘야 한다.",
        "노조는 말한다: AI는 핑계일 뿐, 싼 나라로 일자리 빼돌리려는 것이다.",
        "장관도 경고했다: AI가 만드는 파괴적 영향이 얼마나 불확실한지 그대로 보여준다.",
        "최악을 막아주던 사람이 사라진 자리에 계속 놓치는 AI가 들어올 때, 당신 피드는 더 안전해질까.",
        "원문: thejournal.ie/tiktok-layoffs..."
    ]
    
    from pipeline.instagram.content_converter import convert_format_d_to_carousel
    slides = convert_format_d_to_carousel([
        "틱톡이 감원한다던 667명의 정체, 공식 발표는 300명이지만 내부 문건엔 2배 넘는 숫자.",
        "자살 챌린지 영상 올리는 놈들은 알고리즘 피하는 데 도가 텄다. 유해 콘텐츠는 계속 바뀌기 때문에 AI도 사람이 계속 업데이트해줘야 한다.",
        "노조는 말한다: AI는 핑계일 뿐, 싼 나라로 일자리 빼돌리려는 것이다.",
        "장관도 경고했다: AI가 만드는 파괴적 영향이 얼마나 불확실한지 그대로 보여준다.",
        "최악을 막아주던 사람이 사라진 자리에 계속 놓치는 AI가 들어올 때, 당신 피드는 더 안전해질까.",
        "원문: thejournal.ie/tiktok-layoffs..."
    ])
    
    print(f"Generated {len(slides)} slides")
    for i, slide in enumerate(slides):
        print(f"  {i+1}. {slide.slide_type.value}: {slide.title} / {slide.body[:30]}...")

if __name__ == "__main__":
    asyncio.run(main())