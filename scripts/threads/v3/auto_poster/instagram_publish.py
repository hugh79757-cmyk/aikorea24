from __future__ import annotations
import asyncio
import aiohttp
import json
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

# ──────────────────────────────────────────────
# Instagram Graph API Publisher
# ──────────────────────────────────────────────

@dataclass
class PublishResult:
    success: bool
    media_id: Optional[str] = None
    permalink: Optional[str] = None
    error: Optional[str] = None


class InstagramPublisher:
    """Instagram Graph API 래퍼 (Carousel + Reels)"""
    
    def __init__(
        self,
        access_token: str,
        instagram_business_account_id: str,
        base_url: str = "https://graph.facebook.com/v18.0",
    ):
        self.access_token = access_token
        self.ig_account_id = instagram_business_account_id
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict = None,
        params: dict = None,
    ) -> dict:
        """Graph API 요청"""
        url = f"{self.base_url}/{endpoint}"
        params = params or {}
        params["access_token"] = self.access_token
        
        async with self.session.request(method, url, json=data, params=params) as resp:
            result = await resp.json()
            if resp.status >= 400:
                raise RuntimeError(f"Graph API Error: {result}")
            return result
    
    # ──────────────────────────────────────────────
    # Carousel 발행
    # ──────────────────────────────────────────────
    async def upload_carousel_item(
        self,
        image_path: str,
        caption: str = "",
    ) -> str:
        """단일 캐러셀 아이템 업로드 → container_id 반환"""
        with open(image_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("image", f, filename="slide.png", content_type="image/png")
            data.add_field("is_carousel_item", "true")
            data.add_field("caption", caption)
            data.add_field("access_token", self.access_token)
            
            async with self.session.post(
                f"{self.base_url}/{self.ig_account_id}/media",
                data=data,
            ) as resp:
                result = await resp.json()
                if "id" not in result:
                    raise RuntimeError(f"Carousel item upload failed: {result}")
                return result["id"]
    
    async def publish_carousel(
        self,
        image_paths: list[str],
        caption: str = "",
        hashtags: list[str] = None,
    ) -> PublishResult:
        """캐러셀 포스트 발행"""
        try:
            # 1. 각 슬라이드 업로드 → container_id 수집
            container_ids = []
            for i, img_path in enumerate(image_paths):
                cid = await self.upload_carousel_item(
                    img_path, 
                    caption=f"Slide {i+1}"  # 개별 슬라이드 캡션 (선택적)
                )
                container_ids.append(cid)
            
            # 2. 부모 컨테이너 생성
            children = ",".join(container_ids)
            parent = await self._request(
                "POST",
                f"{self.ig_account_id}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": children,
                    "caption": caption,
                },
            )
            parent_id = parent["id"]
            
            # 3. 발행
            publish = await self._request(
                "POST",
                f"{self.ig_account_id}/media_publish",
                data={"creation_id": parent_id},
            )
            
            return PublishResult(
                success=True,
                media_id=publish.get("id"),
                permalink=f"https://www.instagram.com/p/{publish.get('id')}/",
            )
            
        except Exception as e:
            return PublishResult(success=False, error=str(e))
    
    # ──────────────────────────────────────────────
    # Reels 발행
    # ──────────────────────────────────────────────
    async def upload_reels_video(self, video_path: str) -> str:
        """Reels 비디오 업로드 → container_id 반환"""
        with open(video_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("video", f, filename="reel.mp4", content_type="video/mp4")
            data.add_field("media_type", "REELS")
            data.add_field("access_token", self.access_token)
            
            async with self.session.post(
                f"{self.base_url}/{self.ig_account_id}/media",
                data=data,
            ) as resp:
                result = await resp.json()
                if "id" not in result:
                    raise RuntimeError(f"Reels upload failed: {result}")
                return result["id"]
    
    async def publish_reels(
        self,
        video_path: str,
        caption: str = "",
        hashtags: list[str] = None,
    ) -> PublishResult:
        """Reels 비디오 발행"""
        try:
            container_id = await self.upload_reels_video(video_path)
            
            full_caption = caption
            if hashtags:
                full_caption += "\n\n" + " ".join(f"#{tag}" for tag in hashtags)
            
            publish = await self._request(
                "POST",
                f"{self.ig_account_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "caption": full_caption,
                },
            )
            
            return PublishResult(
                success=True,
                media_id=publish.get("id"),
                permalink=f"https://www.instagram.com/reel/{publish.get('id')}/",
            )
            
        except Exception as e:
            return PublishResult(success=False, error=str(e))
    
    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────
    async def get_media_insights(self, media_id: str) -> dict:
        """게시물 인사이트 조회"""
        return await self._request(
            "GET",
            f"{media_id}/insights",
            params={"metric": "impressions,reach,engagement,video_views"},
        )
    
    async def check_media_status(self, container_id: str) -> dict:
        """컨테이너 상태 확인 (비디오 처리 완료 대기용)"""
        return await self._request("GET", container_id)


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────
async def publish_carousel(
    image_paths: list[str],
    caption: str,
    access_token: str,
    ig_account_id: str,
    hashtags: list[str] = None,
) -> PublishResult:
    """캐러셀 발행 편의 함수"""
    async with InstagramPublisher(access_token, ig_account_id) as publisher:
        return await publisher.publish_carousel(image_paths, caption, hashtags)


async def publish_reels(
    video_path: str,
    caption: str,
    access_token: str,
    ig_account_id: str,
    hashtags: list[str] = None,
) -> PublishResult:
    """Reels 발행 편의 함수"""
    async with InstagramPublisher(access_token, ig_account_id) as publisher:
        return await publisher.publish_reels(video_path, caption, hashtags)


# ──────────────────────────────────────────────
# 환경 변수에서 설정 로드
# ──────────────────────────────────────────────
def load_instagram_config() -> tuple[str, str]:
    """환경 변수에서 Instagram 설정 로드"""
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    ig_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not access_token or not ig_account_id:
        raise RuntimeError(
            "INSTAGRAM_ACCESS_TOKEN과 INSTAGRAM_BUSINESS_ACCOUNT_ID 환경 변수 필요"
        )
    return access_token, ig_account_id


# ──────────────────────────────────────────────
# 테스트/디버그용
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    async def test():
        if len(sys.argv) < 2:
            print("Usage: python instagram_publish.py <video_path> [caption]")
            return
        
        video_path = sys.argv[1]
        caption = sys.argv[2] if len(sys.argv) > 2 else "Test Reel #AI #Tech"
        
        access_token, ig_account_id = load_instagram_config()
        
        result = await publish_reels(video_path, caption, access_token, ig_account_id)
        if result.success:
            print(f"✅ Reels 발행 성공: {result.permalink}")
        else:
            print(f"❌ 발행 실패: {result.error}")
    
    import asyncio
    asyncio.run(test())