#!/usr/bin/env python3
"""aikorea24 심층글 자동 생성기"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).parent.parent
BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"
KST = timezone(timedelta(hours=9))

# Load API key from .env.common
_env_path = os.path.expanduser("~/.env.common")
_mimo_key = ""
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            if line.startswith("MIMO_API_KEY="):
                _mimo_key = line.split("=", 1)[1].strip()
                break

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5"

DEEP_ANALYSIS_PROMPT = """당신은 AI코리아24(aikorea24.kr)의 AI 뉴스 심층분석 에디터입니다.

## 심층분석 작성 원칙
- 기사의 표면적 팩트를 넘어 배경, 맥락, 영향을 다룬다
- 관련 경쟁사나 유사 사례와의 비교 분석을 포함한다
- 기술적 내용은 비유나 일상적 예시를 들어 일반인도 이해할 수 있게 풀어쓴다
- 한국 사용자에게 미치는 영향을 반드시 다룬다

## SEO 기본 원칙
- title 앞 30자 안에 핵심 검색 키워드 배치
- description 앞 80자 안에 키워드와 글의 가치 포함

## Frontmatter 규칙
---
title: "검색 키워드가 포함된 매력적인 제목"
description: "글의 핵심 내용을 요약한 설명"
date: {date}
draft: false
tags: ["태그1", "태그2"]
category: "뉴스"
---

## 내용 구조 (소제목 형식)
각 항목의 소제목은 레이블 없이 주제만 쓴다:
- 서론 항목: 소제목만 (예: `## 완벽해 보이는 모델의 이면`)
- 본론 항목: 소제목만 (예: `## 부정행위의 배경과 진짜 의미`)
- 마무리 항목: 소제목 앞에 "마무리:" 접두사 (예: `## 마무리: 능력 너머, 통제 가능성의 시대`)
4. 마무리 해시태그

## 규칙
- 표 사용 금지
- 이모티콘 사용 금지
- 볼드체 앞뒤 공백
- 전문 용어에 괄호 설명 병기
- 중국어(한자) 사용 금지. 반드시 순수 한국어로만 작성할 것
"""


def remove_chinese(text):
    """중국어(한자) CJK 통합 한자 블록 제거"""
    # CJK Unified Ideographs (U+4E00–U+9FFF) 및 Extension A (U+3400–U+4DBF) 제거
    # 단, 한국어에서도 쓰이는 일부 한자는 보호하지 않음 — 모든 CJK 문자는 중국어로 간주
    return re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', '', text)


def crawl_article(url):
    """원문 크롤링"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 본문 추출 시도 — 다양한 사이트 대응
        for selector in ["article", "main", ".post-content", ".article-content",
                         ".entry-content", "#content", ".content",
                         ".ArticleBody-articleBody", ".article-body",
                         ".story-body", ".story-text",
                         '[class*="articleBody" i]']:
            elem = soup.select_one(selector)
            if elem:
                for tag in elem.select("script, style, nav, footer, .ad, .advertisement"):
                    tag.decompose()
                text = elem.get_text(strip=True, separator="\n")
                if len(text) > 500:
                    return text[:5000]

        # 최후의 fallback: body 전체
        body = soup.select_one("body")
        if body:
            for tag in body.select("script, style, nav, footer, .ad, .advertisement, header"):
                tag.decompose()
            text = body.get_text(strip=True, separator="\n")
            if len(text) > 500:
                return text[:5000]

        return None
    except Exception as e:
        print(f"  크롤링 에러: {e}")
        return None


def generate_deep_article(title, content, url):
    """MiMo API로 심층분석 글 생성"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    prompt_template = DEEP_ANALYSIS_PROMPT.replace("{date}", today)

    prompt = (
        "You are a text generation system. Your ONLY task is to output the requested markdown content. "
        "Do NOT describe what you're doing. Do NOT offer suggestions. Output ONLY the blog post.\n\n"
        f"{prompt_template}\n\n"
        f"## 원문 뉴스\n"
        f"제목: {title}\n"
        f"URL: {url}\n\n"
        f"## 원문 내용\n"
        f"{content[:3000]}\n\n"
        f"위 뉴스를 바탕으로 심층분석 블로그 포스팅을 작성해줘.\n"
        f"마크다운 형식으로, 프론트매터 포함.\n"
        f"결과물만 출력하고 다른 말은 하지마.\n"
        f"[중요] 중국어(한자)를 절대 사용하지 마라. 순수 한국어로만 작성하라."
    )

    try:
        resp = requests.post(
            f"{MIMO_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_mimo_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MIMO_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "temperature": 0.5,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"  API 오류 ({resp.status_code}): {resp.text[:200]}")
            return None
        data = resp.json()
        article = data["choices"][0]["message"]["content"].strip()
        if not article:
            return None
        # 중국어 문자 제거 (안전망)
        cleaned = remove_chinese(article)
        if cleaned != article:
            removed = len(article) - len(cleaned)
            print(f"  ⚠️ 중국어 문자 {removed}개 제거됨")
        return cleaned
    except Exception as e:
        print(f"  API 예외: {e}")
        return None


def inject_frontmatter_image(markdown_content, image_path):
    """프론트매터에 image: 필드가 없으면 주입 + draft: 오류 보정"""
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---', markdown_content, re.DOTALL)
    if not frontmatter_match:
        return markdown_content  # 프론트매터 없음 → 패스

    fm = frontmatter_match.group(1)

    # draft: 값을 false로 보정 (AI가 \x01 같은 깨진 값 생성 시)
    fm = re.sub(r'^draft:\s*\x01', 'draft: false', fm, flags=re.MULTILINE)
    fm = re.sub(r'^draft:\s*[^\w].*$', 'draft: false', fm, flags=re.MULTILINE)

    if re.search(r'^image:', fm, re.MULTILINE):
        return markdown_content.replace(frontmatter_match.group(1), fm, 1)

    # draft: 뒤에 image: 삽입 (정렬 맞춤)
    fm_updated = re.sub(
        r'^draft:\s*(.*)$',
        f'draft: \\1\nimage: "{image_path}"',
        fm,
        count=1,
        flags=re.MULTILINE,
    )
    if fm_updated == fm:
        # draft: 줄이 없으면 마지막 줄 앞에 삽입
        fm_updated = fm.rstrip() + f'\nimage: "{image_path}"\n'

    return markdown_content.replace(fm, fm_updated, 1)


def save_article(markdown_content, title):
    """마크다운 파일 저장 (프론트매터에 image: 자동 주입)"""
    slug = re.sub(r'[^a-z0-9가-힣]+', '-', title.lower())[:60]
    slug = slug.strip('-')
    thumbnail_path = f"/images/{slug}/thumbnail.webp"

    # 프론트매터에 image: 필드 자동 주입
    markdown_content = inject_frontmatter_image(markdown_content, thumbnail_path)

    today = datetime.now(KST).strftime("%Y-%m-%d")
    filename = f"{today}-{slug}.md"
    filepath = BLOG_DIR / filename

    BLOG_DIR.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return filepath


def main():
    print("=== aikorea24 심층글 자동 생성 ===\n")

    test_article = {
        "title": "AI 에이전트 스트레스 테스트의 중요성",
        "url": "https://techcrunch.com/2026/06/25/patronus-ai-lands-50m-to-build-digital-worlds-that-stress-test-ai-agents/",
        "source": "TechCrunch AI"
    }

    print(f"기사: {test_article['title']}")
    print(f"URL: {test_article['url']}\n")

    print("[1/3] 원문 크롤링 중...")
    content = crawl_article(test_article["url"])
    if not content:
        print("  크롤링 실패")
        return
    print(f"  크롤링 완료: {len(content)}자\n")

    print("[2/3] 심층분석 글 생성 중...")
    article = generate_deep_article(test_article["title"], content, test_article["url"])
    if not article:
        print("  글 생성 실패")
        return
    print(f"  생성 완료: {len(article)}자\n")

    print("[3/3] 파일 저장 중...")
    filepath = save_article(article, test_article["title"])
    print(f"  저장 완료: {filepath}\n")

    print("=== 심층글 생성 완료 ===")


if __name__ == "__main__":
    main()
