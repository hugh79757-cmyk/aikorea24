# Instagram Graph API 설정 가이드

> Phase 17 — Carousel + Reels 자동 발행을 위한 Graph API 연동

## 1. 전제 조건

| 항목 | 상태 | 비고 |
|------|------|------|
| Meta(Facebook) Developer 계정 | 필요 | https://developers.facebook.com |
| Facebook 페이지 | 필요 | 비즈니스/크리에이터 계정 연결 |
| Instagram 프로페셔널 계정 | 필요 | 크리에이터 또는 비즈니스 |
| Instagram → Facebook 페이지 연결 | 필요 | Instagram 설정 > 계정 > 공유 프로필 |

## 2. Facebook 앱 생성

1. [Meta Developers](https://developers.facebook.com) → **내 앱** → **앱 만들기**
2. **비즈니스** 유형 선택
3. 앱 대시보드 → **제품 추가** → **Instagram Graph API** 추가
4. **제품 추가** → **Instagram Basic Display** (선택사항, 읽기 전용일 때)

## 3. Graph API Explorer로 토큰 발급

1. [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. 앱 선택 → 권한(`token`): `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_manage_posts`
3. **토큰 생성** → 단기 액세스 토큰 발급됨 (1시간)

## 4. 단기 → 장기 토큰 교환

```bash
# 단기토큰 → 60일 장기토큰
GET /oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={APP_ID}
  &client_secret={APP_SECRET}
  &fb_exchange_token={SHORT_LIVED_TOKEN}
```

응답:
```json
{
  "access_token": "EAA... (장기, 60일)",
  "token_type": "bearer",
  "expires_in": 5184000
}
```

## 5. Instagram Business Account ID 조회

```bash
GET /me/accounts
  ?access_token={LONG_LIVED_TOKEN}
# → Page ID 획득

GET /{PAGE_ID}?fields=instagram_business_account
  &access_token={LONG_LIVED_TOKEN}
# → Instagram Business Account ID 획득
```

## 6. .env 설정

`.env`에 추가:

```env
# Instagram Graph API
IG_APP_ID=123456789012345
IG_APP_SECRET=abc123def456...
IG_ACCESS_TOKEN=EAA...
IG_BUSINESS_ID=178414...     # Instagram Business Account ID
IG_PAGE_ID=123456789012345    # Facebook Page ID
```

## 7. API 엔드포인트

### Carousel 발행 (POST)

```bash
POST /{IG_BUSINESS_ID}/media
  ?media_type=CAROUSEL
  &children={MEDIA_IDS}  # 쉼표 구분, 최대 10개
  &caption={CAPTION}
  &access_token={TOKEN}

# → creation_id 반환 → POST /{IG_BUSINESS_ID}/media_publish
```

### Reel 발행 (POST)

```bash
POST /{IG_BUSINESS_ID}/media
  ?media_type=REELS
  &video_url={MP4_URL}
  &caption={CAPTION}
  &thumb_offset={ms}
  &access_token={TOKEN}

# → creation_id 반환 → POST /{IG_BUSINESS_ID}/media_publish
```

### 미디어 상태 확인

```bash
GET /{CREATION_ID}?fields=status_code
  &access_token={TOKEN}
# → EXPIRED / PUBLISHED / IN_PROGRESS / FAILED
```

## 8. Container 발행 상세 플로우 (Publisher가 수행)

### Carousel 발행 (3단계)

```
1단계: 각 슬라이드 이미지 → 개별 Media Container 생성
  POST /{IG_BUSINESS_ID}/media
    ?image_url={공개_이미지_URL}
    &is_carousel_item=true
    &access_token={TOKEN}
  → 각각 {container_id} 반환

2단계: Parent Carousel Container 생성
  POST /{IG_BUSINESS_ID}/media
    ?media_type=CAROUSEL
    &children={container_id_1},{container_id_2},...
    &caption={캡션}
    &access_token={TOKEN}
  → {carousel_container_id} 반환

3단계: Publish (상태가 FINISHED 될 때까지 폴링 후)
  POST /{IG_BUSINESS_ID}/media_publish
    ?creation_id={carousel_container_id}
    &access_token={TOKEN}
  → {media_id} 반환 (발행 완료)
```

**중요**: 이미지 URL은 **공개적으로 접근 가능**해야 함. 로컬 파일 경로(file://)는 동작하지 않음.
→ R2, Cloudflare Images, 또는 Pages에 업로드 후 공개 URL 사용.

### Reels 발행 (2단계)

```
1단계: 비디오 Media Container 생성
  POST /{IG_BUSINESS_ID}/media
    ?media_type=REELS
    &video_url={공개_MP4_URL}
    &caption={캡션}
    &thumb_offset=1000  (선택, 1초 지점 썸네일)
    &access_token={TOKEN}
  → {container_id} 반환

2단계: Publish (상태가 FINISHED 될 때까지 폴링 후)
  POST /{IG_BUSINESS_ID}/media_publish
    ?creation_id={container_id}
    &access_token={TOKEN}
  → {media_id} 반환
```

### Container 상태 폴링
```python
import time, requests

def wait_for_container(container_id: str, token: str, timeout: int = 120) -> dict:
    """Container 상태가 FINISHED가 될 때까지 폴링"""
    url = f"https://graph.facebook.com/v25.0/{container_id}"
    params = {"fields": "status_code", "access_token": token}
    
    for _ in range(timeout // 2):
        resp = requests.get(url, params=params)
        data = resp.json()
        status = data.get("status_code", "UNKNOWN")
        
        if status == "FINISHED":
            return {"status": "FINISHED", "container_id": container_id}
        elif status == "EXPIRED":
            return {"status": "EXPIRED", "error": "Container expired — media URL may be invalid"}
        elif status == "FAILED":
            return {"status": "FAILED", "error": data.get("error_message", "Unknown error")}
        
        time.sleep(2)
    
    return {"status": "TIMEOUT", "error": f"Container did not finish within {timeout}s"}
```

## 9. 미디어 URL 호스팅 (필수)

Graph API는 로컬 파일을 직접 업로드할 수 없음. 이미지/비디오는 **공개 URL**로 접근 가능해야 함.

### 옵션 1: Cloudflare R2 (추천)
```bash
# R2 버킷 생성
npx wrangler r2 bucket create aikorea24-instagram

# 파일 업로드 (publish.py 또는 rclone 사용)
npx wrangler r2 object put aikorea24-instagram/carousel/2026-07-11/slide-1.png --file cards/slide-1.png
```

### 옵션 2: Cloudflare Pages public/
- `public/instagram/` 디렉토리에 미디어 파일 배치
- `https://aikorea24.kr/instagram/slide-1.png` 형태로 접근

## 10. 전체 발행 순서도 (Publisher 로직)

```
1. Format D → content_converter → InstagramSlide[]
2. html_renderer → PNG (1080×1350 / 1080×1920)
3. PNG → R2 업로드 (공개 URL 확보)
4. Carousel:
   a. 각 PNG URL → child container 생성
   b. FINISHED 폴링
   c. parent carousel container 생성
   d. FINISHED 폴링
   e. media_publish
5. Reels (별도 실행):
   a. TTS 생성 (edge-tts)
   b. FFmpeg → MP4 (1080×1920)
   c. MP4 → R2 업로드
   d. REELS container 생성
   e. FINISHED 폴링
   f. media_publish
6. posted.json에 media_id, permalink 기록
```

## 11. 발행 제한

| 제한 | 값 |
|------|-----|
| Carousel 이미지 수 | 2~10장 |
| Reels 길이 | 15~90초 |
| API 호출 | 앱당 200회/시간 |
| 태그 가능 계정 | 게시자만 |
| Container TTL | 생성 후 24시간 이내 Publish 필요 |

## 12. 테스트 (연결 확인)

```python
# pipeline/instagram/test_connection.py
import os
import requests

BUSINESS_ID = os.environ["IG_BUSINESS_ID"]
TOKEN = os.environ["IG_ACCESS_TOKEN"]
API_VERSION = "v25.0"

# 계정 정보 조회
url = f"https://graph.facebook.com/{API_VERSION}/{BUSINESS_ID}"
params = {"fields": "id,name,username,profile_picture_url", "access_token": TOKEN}
resp = requests.get(url, params=params)
data = resp.json()
print(f"✅ Connected: {data.get('name')} (@{data.get('username')})")
print(f"   ID: {data.get('id')}")

# 토큰 만료일 확인
url = f"https://graph.facebook.com/{API_VERSION}/debug_token"
params = {"input_token": TOKEN, "access_token": f"{os.environ['IG_APP_ID']}|{os.environ['IG_APP_SECRET']}"}
resp = requests.get(url, params=params)
expires = resp.json().get("data", {}).get("expires_at", 0)
import datetime
expire_date = datetime.datetime.fromtimestamp(expires)
print(f"   Token expires: {expire_date.strftime('%Y-%m-%d %H:%M:%S')}")
```

## 13. 토큰 갱신 자동화

60일 만료 토큰을 자동 갱신하는 스크립트:

```python
# scripts/refresh_instagram_token.py
import os, requests, json
from pathlib import Path

def refresh_token():
    """장기 토큰 갱신 (60일 연장, 만료 전에만 가능)"""
    long_token = os.environ["IG_ACCESS_TOKEN"]
    app_id = os.environ["IG_APP_ID"]
    app_secret = os.environ["IG_APP_SECRET"]
    
    url = "https://graph.facebook.com/v25.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": long_token,
    }
    
    resp = requests.get(url, params=params)
    data = resp.json()
    
    if "access_token" in data:
        new_token = data["access_token"]
        expires_in = data.get("expires_in", 0)
        print(f"✅ Token refreshed! Expires in {expires_in // 86400} days")
        
        # .env 업데이트
        env_path = Path(".env")
        content = env_path.read_text()
        content = content.replace(
            f"IG_ACCESS_TOKEN={long_token}",
            f"IG_ACCESS_TOKEN={new_token}"
        )
        env_path.write_text(content)
        print(f"   .env updated")
        return new_token
    else:
        print(f"❌ Refresh failed: {data}")
        return None
```

**launchd 등록 (매주 월요일 09:00 실행)**:
```xml
<!-- ~/Library/LaunchAgents/kr.aikorea24.instagram-token-refresh.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>kr.aikorea24.instagram-token-refresh</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/twinssn/Projects/aikorea24/scripts/refresh_instagram_token.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/twinssn/Projects/aikorea24</string>
    <key>StandardOutPath</key>
    <string>/Users/twinssn/Projects/aikorea24/logs/instagram-token-refresh.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/twinssn/Projects/aikorea24/logs/instagram-token-refresh.log</string>
</dict>
</plist>
```

## 14. API 버전 호환성

| 버전 | 상태 | 사용 |
|------|------|------|
| v25.0 | ✅ 최신 (2026-07) | **현재 권장** |
| v22.0 | ⚠️ 지원 종료 예정 | 이전 가이드에서 사용 |
| v19.0 | ❌ 만료 | 사용 금지 |

URL의 `v25.0` 부분을 최신 버전에 맞춰 업데이트 필요.  
확인: https://developers.facebook.com/docs/graph-api/changelog

## 참고 링크

- [Instagram Graph API Overview](https://developers.facebook.com/docs/instagram-api/overview)
- [Content Publishing](https://developers.facebook.com/docs/instagram-api/guides/content-publishing/)
- [Carousel Publishing](https://developers.facebook.com/docs/instagram-api/guides/carousel)
- [Reels Publishing](https://developers.facebook.com/docs/instagram-api/guides/reels)
- [Access Tokens](https://developers.facebook.com/docs/facebook-login/access-tokens/)
- [API Changelog](https://developers.facebook.com/docs/graph-api/changelog)
