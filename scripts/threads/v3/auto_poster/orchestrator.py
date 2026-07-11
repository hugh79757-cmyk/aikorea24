from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum

# ──────────────────────────────────────────────
# 설정 및 상태
# ──────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class SNSJob:
    """SNS 발행 작업"""
    job_id: str
    mode: str  # "carousel" | "reels"
    format_d_cards: list[str]  # Format D 6카드 리스트
    status: JobStatus = JobStatus.PENDING
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    retry_count: int = 0
    carousel_media_id: str = ""
    reel_media_id: str = ""
    carousel_url: str = ""
    reel_url: str = ""


# ──────────────────────────────────────────────
# 오케스트레이터
# ──────────────────────────────────────────────

class AutoPosterOrchestrator:
    """SNS 자동화 파이프라인 오케스트레이터"""
    
    def __init__(self, db_path: str = "sns_jobs.db"):
        self.db_path = Path(db_path)
        self.setup_logging()
        self.init_db()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        self.logger = logging.getLogger("auto_poster")
    
    def init_db(self):
        """SQLite DB 초기화 (D1 대신 로컬 SQLite 사용)"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sns_jobs (
                    job_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    format_d_cards TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    carousel_media_id TEXT,
                    reel_media_id TEXT,
                    carousel_url TEXT,
                    reel_url TEXT
                )
            """)
    
    def create_job(self, mode: str, format_d_cards: list[str]) -> str:
        """새 작업 생성"""
        import uuid
        job_id = f"sns_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        import sqlite3, json, uuid
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sns_jobs (job_id, mode, format_d_cards, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, "carousel", json.dumps([]), "pending", datetime.now().isoformat()))
            # 실제로는 carousel/reels 각각 생성
        
        self.logger.info(f"Job created: {job_id}")
        return job_id
    
    def get_pending_jobs(self, mode: str = None) -> list[dict]:
        """대기 중인 작업 조회"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if mode:
                rows = conn.execute(
                    "SELECT * FROM sns_jobs WHERE status = 'pending' AND mode = ? ORDER BY created_at",
                    (mode,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sns_jobs WHERE status = 'pending' ORDER BY created_at"
                ).fetchall()
            return [dict(row) for row in rows]
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """작업 상태 업데이트"""
        import sqlite3
        updates = [f"{k} = ?" for k in kwargs]
        values = list(kwargs.values())
        
        if status:
            updates.append("status = ?")
            values.append(status)
        
        values.append(job_id)
        
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE sns_jobs SET {', '.join(updates)} WHERE job_id = ?",
                values
            )
    
    def get_job(self, job_id: str) -> dict | None:
        """작업 조회"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sns_jobs WHERE job_id = ?", (job_id,)).fetchone()
            return dict(row) if row else None


# ──────────────────────────────────────────────
# 파이프라인 실행기
# ──────────────────────────────────────────────

class PipelineRunner:
    """전체 파이프라인 실행 (Format D → Carousel/Reels → 발행)"""
    
    def __init__(self, orchestrator: AutoPosterOrchestrator):
        self.orchestrator = orchestrator
        self.logger = logging.getLogger("pipeline_runner")
    
    async def run_carousel_pipeline(self, format_d_cards: list[str]) -> dict:
        """Carousel 파이프라인 실행"""
        # 1. 콘텐츠 변환
        from pipeline.instagram.content_converter import convert_format_d_to_carousel
        slides = convert_format_d_to_carousel(format_d_cards)
        
        # 2. HTML → PNG
        from .html_to_png import render_cards_to_png
        png_paths = await render_cards_to_png(slides)
        
        # 3. TTS + SRT
        from .tts_generator import generate_narration_batch
        tts_texts = [slide.body for slide in slides]
        await generate_narration_batch(tts_texts, output_dir="tts")
        
        # 4. 비디오 생성 (Carousel은 MP4로 변환하여 발행)
        from .video_builder import build_carousel_video
        video_path = await build_carousel_video(png_paths)
        
        return {"video_path": video_path, "slide_count": len(slides)}
    
    async def run_reels_pipeline(self, format_d_cards: list[str]) -> dict:
        """Reels 파이프라인 실행"""
        from pipeline.instagram.content_converter import convert_format_d_to_reel_script
        scenes = convert_format_d_to_reel_script(format_d_cards)
        
        # 이미지 생성 (Reels용 세로)
        from .html_to_png import render_reels_scenes
        png_paths = await render_reels_scenes(scenes)
        
        # TTS
        from .tts_generator import generate_narration_batch
        texts = [scene.text for scene in scenes]
        await generate_narration_batch(texts, output_dir="tts")
        
        # 비디오 빌드
        from .video_builder import build_reels_video
        video_path = await build_reels_video(png_paths)
        
        return {"video_path": video_path, "scene_count": len(scenes)}


# ──────────────────────────────────────────────
# 메인 실행기
# ──────────────────────────────────────────────

async def run_carousel_job(format_d_cards: list[str]) -> dict:
    """캐러셀 단일 작업 실행"""
    from pipeline.instagram.content_converter import convert_format_d_to_carousel
    from scripts.threads.v3.auto_poster.html_to_png import render_cards_to_png
    from scripts.threads.v3.auto_poster.video_builder import build_carousel_video
    from scripts.threads.v3.auto_poster.tts_generator import generate_narration_batch
    from scripts.threads.v3.auto_poster.instagram_publish import publish_carousel
    from pipeline.instagram.content_converter import convert_format_d_to_carousel
    import os
    
    # 1. 변환
    slides = convert_format_d_to_carousel(format_d_cards)
    
    # 2. 이미지 생성
    png_paths = await render_cards_to_png(slides)
    
    # 3. TTS
    texts = [slide.body for slide in slides]
    await generate_narration_batch(texts)
    
    # 4. 비디오 빌드
    video_path = await build_carousel_video(png_paths)
    
    # 5. 발행 (환경변수 설정 필요)
    # result = await publish_carousel(png_paths, caption="...", hashtags=["AI", "Tech"])
    
    return {"video_path": "output_reel.mp4", "slides": len(png_paths)}


async def run_reels_job(format_d_cards: list[str]) -> dict:
    """Reels 단일 작업 실행"""
    from pipeline.instagram.content_converter import convert_format_d_to_reel_script
    from scripts.threads.v3.auto_poster.html_to_png import render_reels_scenes
    from scripts.threads.v3.auto_poster.video_builder import build_reels_video
    from scripts.threads.v3.auto_poster.tts_generator import generate_narration_batch
    from scripts.threads.v3.auto_poster.instagram_publish import publish_reels
    
    # 1. 변환
    scenes = convert_format_d_to_reel_script(format_d_cards)
    
    # 2. 이미지 생성
    png_paths = await render_reels_scenes(scenes)
    
    # 3. TTS
    texts = [scene.text for scene in scenes]
    await generate_narration_batch(texts)
    
    # 4. 비디오 빌드
    video_path = await build_reels_video(png_paths)
    
    # 5. 발행
    # result = await publish_reels(video_path, caption="...", hashtags=["AI", "Tech"])
    
    return {"video_path": "output_reel.mp4", "scenes": len(scenes)}


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

async def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Instagram Carousel + Shorts/Reels 자동화")
    parser.add_argument("--mode", choices=["carousel", "reels", "both"], default="both")
    parser.add_argument("--cards", nargs="+", help="Format D 카드들 (6개)")
    parser.add_argument("--dry-run", action="store_true", help="발행 없이 생성만")
    
    args = parser.parse_args()
    
    if not args.cards or len(args.cards) < 6:
        print("❌ Format D 카드 6개 필요")
        return
    
    print(f"🎬 모드: {args.mode}")
    print(f"📝 카드 수: {len(args.cards)}")
    
    if args.mode in ("carousel", "both"):
        result = await run_carousel_job(args.cards)
        print(f"✅ Carousel 완료: {result}")
    
    if args.mode in ("reels", "both"):
        result = await run_reels_job(args.cards)
        print(f"✅ Reels 완료: {result}")


if __name__ == "__main__":
    asyncio.run(main())