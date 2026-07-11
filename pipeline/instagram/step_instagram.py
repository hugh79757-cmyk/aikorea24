"""
pipeline/instagram/step_instagram.py — Instagram 파이프라인 실행 스텝

Content Converter → HTML Renderer → TTS Generator → Video Renderer → Instagram Publisher

PipelineStep 프로토콜을 따르며, orchestrator에 등록하여 실행.
모든 파이프라인 모듈 import는 lazy (run() 내부) — 환경 변수 의존성 때문에.
"""

from pipeline.infra.config import project_root
from pipeline.infra.logger import get_pipeline_logger

PROJECT_DIR = project_root()


class StepRunInstagramCarousel:
    """Instagram Carousel 생성 + 발행 파이프라인 스텝

    Pipeline: D1 → content_converter → html_renderer → instagram_publisher
    """

    name: str = "instagram_carousel"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._log = get_pipeline_logger("step.instagram.carousel")

    def run(self) -> int:
        """Carousel 파이프라인 실행

        Returns:
            0 = success, 1 = failure
        """
        try:
            # 1. Load latest Format D cards from D1
            from pipeline.instagram.content_converter import convert_format_d_to_carousel
            from pipeline.infra.d1_client import d1_query

            rows = d1_query(
                "SELECT content FROM threads_posts ORDER BY created_at DESC LIMIT 1"
            )
            if not rows:
                self._log.warning("No Format D content found in D1 — skipping")
                return 0

            cards = rows[0]["content"].split("\n---\n")
            slides = convert_format_d_to_carousel(cards)
            self._log.info(f"Converted {len(cards)} cards → {len(slides)} slides")

            # 2. Render slides as PNG
            from pipeline.instagram.html_renderer import render_full_carousel

            result = render_full_carousel(slides)
            self._log.info(
                f"Rendered {len(result['slides'])} slides to {result['output_dir']}"
            )

            if self.dry_run:
                self._log.info("[DRY RUN] Skipping Instagram publish")
                return 0

            # 3. Publish Carousel
            from pipeline.instagram.instagram_publisher import publish_carousel

            caption = slides[0].title
            if len(slides) > 4:
                caption += f"\n\n{slides[4].body}"

            pub_result = publish_carousel(
                [str(p) for p in result["slides"]],
                caption=caption,
            )
            self._log.info(f"Published carousel: {pub_result.get('media_id', 'unknown')}")
            return 0

        except Exception as e:
            self._log.exception(f"Carousel step failed: {e}")
            return 1


class StepRunInstagramReel:
    """Instagram Reel 생성 + 발행 파이프라인 스텝

    Pipeline: D1 → content_converter → html_renderer → tts_generator → video_renderer → instagram_publisher
    """

    name: str = "instagram_reel"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._log = get_pipeline_logger("step.instagram.reel")

    def run(self) -> int:
        """Reel 파이프라인 실행

        Returns:
            0 = success, 1 = failure
        """
        try:
            # 1. Load latest Format D cards from D1
            from pipeline.instagram.content_converter import (
                convert_format_d_to_carousel,
                convert_format_d_to_reel_script,
            )
            from pipeline.infra.d1_client import d1_query

            rows = d1_query(
                "SELECT content FROM threads_posts ORDER BY created_at DESC LIMIT 1"
            )
            if not rows:
                self._log.warning("No Format D content found in D1 — skipping")
                return 0

            cards = rows[0]["content"].split("\n---\n")

            # 2. Convert to carousel slides (for PNG rendering) + reel scenes (for TTS/video)
            slides = convert_format_d_to_carousel(cards)
            scenes = convert_format_d_to_reel_script(cards)
            self._log.info(
                f"Converted {len(cards)} cards → {len(slides)} slides, {len(scenes)} scenes"
            )

            # 3. Render slides as PNG (video input)
            from pipeline.instagram.html_renderer import (
                batch_render_carousel,
                render_reel_thumbnail,
            )
            from pipeline.instagram.utils import create_run_directory

            output_dir = create_run_directory("instagram-reel-output")
            png_paths = batch_render_carousel(slides, output_dir)
            self._log.info(f"Rendered {len(png_paths)} slides to {output_dir}")

            # Also render reel thumbnail (cover)
            thumbnail = render_reel_thumbnail(slides)
            if thumbnail:
                self._log.info(f"Reel thumbnail: {thumbnail}")

            if self.dry_run:
                self._log.info("[DRY RUN] Skipping TTS + video + publish")
                return 0

            # 4. Generate TTS audio from scenes
            from pipeline.instagram.tts_generator import generate_reel_audio

            tts_dir = create_run_directory("tts")
            tts_result = generate_reel_audio(
                scenes=[{"text": s.text, "scene_index": s.scene_index} for s in scenes],
                output_dir=tts_dir,
            )
            audio_path = tts_result["audio_path"]
            srt_path = tts_result["srt_path"]
            self._log.info(
                f"TTS generated: audio={audio_path}, srt={srt_path}, "
                f"duration={tts_result.get('total_duration', 0):.1f}s"
            )

            # 5. Render reel video
            from pipeline.instagram.video_renderer import render_reel_video

            video_dir = create_run_directory("instagram-reel-output")
            video_path = render_reel_video(
                slides=png_paths,
                audio=audio_path,
                subtitles_srt=srt_path,
                output_dir=video_dir,
                scenes=scenes,
            )
            self._log.info(f"Reel video rendered: {video_path}")

            # 6. Publish Reel
            from pipeline.instagram.instagram_publisher import publish_reel

            pub_result = publish_reel(str(video_path))
            self._log.info(f"Published reel: {pub_result.get('media_id', 'unknown')}")
            return 0

        except Exception as e:
            self._log.exception(f"Reel step failed: {e}")
            return 1


if __name__ == "__main__":
    import sys

    carousel = StepRunInstagramCarousel(dry_run=True)
    print(f"Running step: {carousel.name}")
    exit_code = carousel.run()
    print(f"Step completed with exit code: {exit_code}")
    sys.exit(exit_code)
