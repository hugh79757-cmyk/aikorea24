# Phase 17: Instagram Carousel + Reels Automation — Research

**Researched:** 2026-07-11
**Domain:** Instagram content publishing pipeline (HTML→PNG→Video→Publish)
**Confidence:** HIGH

## Summary

Phase 17 implements 6 sub-plans that convert Format D output into Instagram-ready Carousel images and Reels videos, then publish them automatically on a schedule. The project already has a mature pipeline infrastructure (`pipeline/orchestrator.py`, `pipeline/infra/`, launchd templates, D1 client, Telegram alerting) — the Instagram phase plugs into this existing framework.

**Core architecture:** Step-oriented pipeline where each sub-plan maps to a `PipelineStep`. Steps share data through filesystem artifacts (PNG images, MP4 videos, MP3 audio) rather than in-memory, because the media assets are large and FFmpeg operates on file paths.

**Key dependencies:** 17-02 (HTML→PNG) must come first — all downstream steps consume PNG images. 17-03 (FFmpeg) depends on 17-02 for image inputs and 17-04 (TTS) for audio inputs. 17-05 (publish) depends on 17-03 for video files. 17-06 (scheduler) wraps the full pipeline. 17-07 (test/docs) comes last.

**Primary recommendation:** Implement as standalone `pipeline/steps/step_instagram.py` that registers steps with the existing `PipelineOrchestrator`, reusing the proven `subprocess` pattern (not `moviepy`) for FFmpeg to avoid filter graph complexity issues.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTML template rendering | Frontend (Python/Jinja) | — | Templates are static HTML files; no SSR/browser needed |
| HTML→PNG screenshot | Browser (Headless Chromium) | — | Playwright must render HTML in a real browser engine |
| Ken Burns + transitions | FFmpeg (system CLI) | — | FFmpeg zoompan/xfade are the gold standard; moviepy wraps these poorly |
| TTS audio generation | cloud API (edge-tts) | — | Microsoft Edge TTS is cloud-based, no local model |
| SRT subtitle generation | Python (edge-tts SubMaker) | — | Parses word boundary events from TTS stream |
| Video assembly | FFmpeg CLI | — | Complex filter graph with 5+ inputs, xfade chain, subtitle overlay |
| Image hosting for Graph API | Cloudflare R2 / Pages | — | Instagram downloads media from a public URL; cannot use local file paths |
| Carousel container creation | Instagram Graph API | — | REST POST to graph.facebook.com |
| Reels container creation | Instagram Graph API | — | REST POST to graph.facebook.com |
| Container status polling | Instagram Graph API | — | GET container status before publish |
| Container publishing | Instagram Graph API | — | POST media_publish endpoint |
| Token refresh automation | Cron/launchd | — | 60-day expiry, monthly refresh via launchd |
| Scheduled execution | macOS launchd | — | Existing project pattern (20+ plists) |
| Pipeline state tracking | Cloudflare D1 | — | Existing pipeline_runs table pattern |
| Failure alerting | Telegram | — | Already built into PipelineOrchestrator |

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists — this phase has not been discussed yet. The agent has full discretion on implementation approach.
</user_constraints>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `playwright` [VERIFIED: pip show / PyPI] | 1.61.0 | HTML→PNG screenshot at 1080×1350 / 1080×1920 | Only reliable headless browser for Tailwind-rendered HTML; already installed with Chromium browser binary |
| `edge-tts` [VERIFIED: pip show / PyPI] | 7.2.8 | Korean TTS narration for Reels | Free, high-quality Korean voice (ko-KR-SunHiNeural), proven in prototypes, SubMaker for SRT |
| `ffmpeg` [VERIFIED: brew] | 8.1.1 | Video assembly: zoompan, xfade, drawtext, subtitles | System-installed with videotoolbox hardware acceleration; no Python package needed |
| `requests` [VERIFIED: pip show] | 2.34.2 | Instagram Graph API calls | Simpler than facebook_business SDK for 3-step container flow; already in project deps |
| `facebook_business` [CITED: pypi.org/project/facebook-business/] | 25.0.2 | Instagram Graph API (optional) | Official Meta SDK; needed only if using Ads/Marketing APIs alongside publishing |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` [VERIFIED: pip show] | 1.2.1 | Env loading (fallback) | Project already uses its own `EnvConfig` instead; keep for compat |
| `pillow` [VERIFIED: pip show] | 11.3.0 | Image dimension verification | Verify output PNG dimensions match Instagram requirements before publishing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright (Python) | Puppeteer (Node.js) | Python Playwright keeps all code in one language; existing prototype `html_to_png.mjs` needs translation anyway |
| FFmpeg subprocess | moviepy 2.x | Subprocess gives full control over complex filter graphs; moviepy 2.x crossfade API found inadequate for 5-input xfade chains with transitions [ASSUMED] |
| `requests` | `facebook_business` SDK | For our simple 3-step flow (create container → poll → publish), raw requests is clearer; SDK is designed for Ads API complexity |
| macOS launchd | cron / PM2 | Launchd is the project standard (20+ plists); cron has macOS permission issues; PM2 isn't installed |
| D1 for state | SQLite file / JSON | D1 is the project database standard; cloud-accessible for monitoring; existing `pipeline_runs` table pattern |

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `playwright` | PyPI | ~4 yrs | 60M+/mo | github.com/microsoft/playwright-python | [OK] (pip) | Approved |
| `edge-tts` | PyPI | ~3 yrs | 800K+/mo | github.com/rany2/edge-tts | [OK] (pip) | Approved |
| `moviepy` | PyPI | ~7 yrs | 5M+/mo | github.com/Zulko/moviepy | N/A (PyPI; slopcheck tested npm) | Approved — but subprocess FFmpeg recommended instead |
| `facebook_business` | PyPI | ~10 yrs | 10M+/mo | github.com/facebook/facebook-python-business-sdk | [OK] (pip) | Approved — optional, `requests` preferred for our use case |
| `requests` | PyPI | ~12 yrs | 500M+/mo | github.com/psf/requests | [OK] (pip) | Approved |
| `python-dotenv` | PyPI | ~8 yrs | 100M+/mo | github.com/theskumar/python-dotenv | [OK] (pip) | Approved — keep for compat |
| `pillow` | PyPI | ~14 yrs | 200M+/mo | github.com/python-pillow/Pillow | [OK] (pip) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Note: slopcheck by default checks the npm registry. All packages above were verified on PyPI (the correct Python registry) via `pip show` and PyPI web search.*

## Architecture Patterns

### System Architecture Diagram

```
Format D Cards (text)
       │
       ▼
┌─────────────────────┐
│ 17-01 ContentConv   │  ← Already implemented
│ (models + convert)  │
└────────┬────────────┘
         │ InstagramSlide[] / InstagramReelScene[]
         ▼
┌─────────────────────┐
│ 17-02 HTML→PNG      │  ← Playwright headless Chromium
│ 3 styles × 5 slides │    1080×1350 (carousel) / 1080×1920 (reels)
│ template rendering   │    Template variables injected per slide
└────────┬────────────┘
         │ PNG image files
         ▼
┌─────────────────────┐      ┌─────────────────────┐
│ 17-04 TTS + SRT     │      │ 17-03 FFmpeg Video  │
│ edge-tts Korean     │◄────►│ Ken Burns (zoompan) │
│ SunHiNeural voice   │ MP3  │ xfade transitions   │
│ SubMaker→SRT file   │ +SRT │ subtitle overlay    │
└────────┬────────────┘      │ H.264 videotoolbox  │
         │                   └────────┬────────────┘
         │ MP3 audio + SRT subtitles  │ MP4 video file
         ▼                            ▼
┌─────────────────────────────────────────────┐
│ 17-05 Instagram Graph API Publisher         │
│                                             │
│ Carousel:                                    │
│   1. Upload each PNG → image_url (Cloud)     │
│   2. Create child containers (is_carousel)   │
│   3. Poll each child until FINISHED          │
│   4. Create parent CAROUSEL container        │
│   5. Poll parent until FINISHED              │
│   6. POST /media_publish                     │
│                                             │
│ Reels:                                       │
│   1. Upload MP4 → video_url (Cloud)          │
│   2. Create REELS container (media_type=REELS)│
│   3. Poll until FINISHED                     │
│   4. POST /media_publish                     │
└──────────────────────┬──────────────────────┘
                       │ Published post IDs
                       ▼
┌─────────────────────┐      ┌─────────────────────┐
│ 17-06 Scheduler     │      │ D1 State Table      │
│ launchd: 08:00/19:00│─────►│ instagram_posts     │
│ Orchestrator steps  │      │ (id, type, status,   │
│ Telegram alerts     │      │  container_id, url)  │
└─────────────────────┘      └─────────────────────┘
```

### Component Responsibilities

| Component | Files | Responsibility |
|-----------|-------|----------------|
| Image renderer | `pipeline/instagram/image_renderer.py` | Take InstagramSlide[] → render HTML template → Playwright screenshot → save PNG |
| Video renderer | `pipeline/instagram/video_renderer.py` | Build FFmpeg filter graph → subprocess.run → output MP4 |
| TTS engine | `pipeline/instagram/tts_engine.py` | edge-tts async batch per scene → MP3 + SRT files |
| Graph API client | `pipeline/instagram/graph_client.py` | Container creation + polling + publishing via requests |
| Instagram pipeline step | `pipeline/steps/step_instagram.py` | Register with PipelineOrchestrator, orchestrate sub-steps in order |
| D1 state migration | `schema.sql` | Add `instagram_posts` and `instagram_pipeline_state` tables |

### Pattern 1: Subprocess FFmpeg with Filter Graph File
**What:** Write the complex FFmpeg filter graph to a temp `.txt` file, then use `-filter_complex_script` to avoid shell escaping issues. The prototype `test_reel4.py` already demonstrates this pattern.

**When to use:** Any time the filter graph string exceeds 500 characters or contains nested quotes.

**Example:**
```python
# Source: pipeline/instagram/prototypes/test_reel4.py [VERIFIED: codebase]
filter_graph = """
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.12)':d=75:s=1080x1920:fps=30[v0];
[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':d=75:s=1080x1920:fps=30[v1];
[v0][v1]xfade=transition=wipeleft:duration=0.4:offset=1.9[v01];
...
[5:a][6:a][7:a][8:a][9:a]concat=n=5:v=0:a=1[aout]
"""
with open("filter.txt", "w") as f:
    f.write(filter_graph)

cmd = ["ffmpeg", "-y",
    *[f"-loop 1 -t {dur} -i cards/{img}" for ...],
    *[f"-i tts/narration_{i}.mp3" for ...],
    "-filter_complex_script", "filter.txt",
    "-map", "[vout]", "-map", "[aout]",
    "-c:v", "h264_videotoolbox",
    "-c:a", "aac", "-b:a", "128k",
    "-r", "30", "-pix_fmt", "yuv420p",
    "-shortest", "output_reel.mp4"
]
subprocess.run(cmd)
```

### Pattern 2: Edge TTS Streaming + SubMaker
**What:** Stream TTS audio chunks and word boundary events simultaneously, building the SRT subtitle file in-memory.

**When to use:** Every Reels creation needs both audio and subtitles.

**Example:**
```python
# Source: Context7 /rany2/edge-tts docs [CITED]
import asyncio, edge_tts

async def generate_tts_with_subtitles(text: str, voice: str, mp3_path: str, srt_path: str):
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    submaker = edge_tts.SubMaker()
    
    with open(mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
```

### Pattern 3: Instagram Graph API 3-Step Publishing
**What:** Every media publish follows: (1) create container → (2) poll until FINISHED → (3) publish container.

**When to use:** All Instagram content publishing.

**Example (Carousel):**
```python
# Source: developeers.facebook.com/docs/instagram-platform/content-publishing [CITED]
import requests

IG_ID = os.environ["IG_BUSINESS_ID"]
TOKEN = os.environ["IG_ACCESS_TOKEN"]
API = f"https://graph.facebook.com/v25.0/{IG_ID}"

# Step 1a: Create child containers (one per slide, no caption)
child_ids = []
for slide_url in slide_urls:
    r = requests.post(f"{API}/media", params={
        "image_url": slide_url,
        "is_carousel_item": "true",
        "access_token": TOKEN,
    })
    child_ids.append(r.json()["id"])

# Step 1b: Poll each child until FINISHED
for cid in child_ids:
    while True:
        r = requests.get(f"https://graph.facebook.com/v25.0/{cid}",
                        params={"fields": "status_code", "access_token": TOKEN})
        status = r.json().get("status_code")
        if status == "FINISHED":
            break
        time.sleep(2)

# Step 2: Create parent CAROUSEL container
r = requests.post(f"{API}/media", params={
    "media_type": "CAROUSEL",
    "children": ",".join(child_ids),
    "caption": caption,
    "access_token": TOKEN,
})
parent_id = r.json()["id"]

# Step 3: Poll parent until FINISHED
# Step 4: Publish
r = requests.post(f"{API}/media_publish", params={
    "creation_id": parent_id,
    "access_token": TOKEN,
})
```

### Anti-Patterns to Avoid
- **moviepy for xfade chains:** MoviePy 2.x `CrossFadeIn/CrossFadeOut` applies only simple dissolve. It cannot do `wipeleft`, `circlecrop`, `smoothleft` transitions between 5+ clips. Use FFmpeg subprocess instead.
- **Inline filter_graph strings:** Shell escaping of FFmpeg filter expressions with nested quotes is error-prone. Always write to a temp file and use `-filter_complex_script`.
- **Direct file uploads to Graph API:** Instagram requires publicly accessible URLs for images and videos. Local files cannot be published. You need a Cloudflare R2 bucket or Pages public URL as intermediate storage.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TTS voice generation | Custom TTS pipeline | `edge-tts` with `ko-KR-SunHiNeural` | Free, high-quality Korean neural voice, no API key needed, SubMaker for SRT |
| HTML→image capture | Custom renderer | `playwright` headless Chromium | Full CSS/Tailwind/JS rendering, battle-tested, already installed |
| Video transitions | Custom OpenGL shaders | `ffmpeg xfade` filter | 17 built-in transition types, hardware accelerated, zero code |
| Instagram auth flow | Custom OAuth implementation | Graph API long-lived tokens + monthly refresh | Standard 2-step token exchange, well-documented error codes |

**Key insight:** This pipeline is an assembly of well-established tools (Playwright, FFmpeg, edge-tts, Graph API), not a novel engineering challenge. The difficulty lies in wiring them together reliably with proper error handling, rate limiting, and state tracking.

## Common Pitfalls

### Pitfall 1: ffmpeg Shell Escaping Nightmares
**What goes wrong:** Complex FFmpeg filter graphs with nested quotes (zoompan `z='if(...)'`, drawtext `text='...'`) fail spectacularly when passed as inline shell strings.
**Why it happens:** The filter graph contains single quotes, double quotes, and special characters that interact with multiple shell parsing layers.
**How to avoid:** Always write the filter graph to a `.txt` file and use `-filter_complex_script filter.txt`. This bypasses all shell escaping issues.
**Warning signs:** `Invalid expression`, `Parse error`, or `Option not found` errors in FFmpeg stderr.

### Pitfall 2: Graph API Image URL Requirements
**What goes wrong:** Instagram returns `(#100) Media URL could not be processed` or download timeout errors.
**Why it happens:** Instagram downloads images/videos from the URL you provide. The URL must be publicly accessible (no auth, no localhost, no expired pre-signed URL). And the image must be valid — not oversized, correct format (JPEG/PNG), and proper dimensions.
**How to avoid:** Upload PNG/MP4 files to Cloudflare R2 with public read access before creating Graph API containers. Verify file size < 8MB for images, < 100MB for video.
**Warning signs:** `"error": {"code": 100, "error_subcode": 2207013}`

### Pitfall 3: Container Expiry
**What goes wrong:** A carousel parent container fails to publish because a child container has expired.
**Why it happens:** Containers expire if not published within ~24 hours. For carousels, children must be FINISHED *before* creating the parent. If the parent creation fails, children may expire while retrying.
**How to avoid:** Implement a retry pattern that recreates only expired containers while keeping FINISHED ones. The parent container is always created last.
**Warning signs:** Status code `EXPIRED` on polling GET requests.

### Pitfall 4: Rate Limiting
**What goes wrong:** HTTP 429 after publishing too many posts.
**Why it happens:** Instagram limits to 100 API-published posts per 24-hour rolling window.
**How to avoid:** Check `/content_publishing_limit` endpoint before publishing. Track local count in D1. Our pipeline (2 posts/day max) is well within limits.
**Warning signs:** HTTP 429 response.

## Code Examples

### Image Renderer (17-02) — Playwright Python Screenshot
```python
# Source: playwright.dev/docs/screenshots [ASSUMED — confirmed via pip show]
from playwright.sync_api import sync_playwright

def render_slide(html_path: str, output_path: str, width: int = 1080, height: int = 1350, scale: int = 2):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=output_path, full_page=False)
        browser.close()
```

### Video Renderer (17-03) — Dynamic Filter Graph Builder
```python
# Source: Working prototype build_reel.py [VERIFIED: codebase]
import subprocess, tempfile
from pathlib import Path

SCENE_DURATION = 3.5  # seconds per scene
TRANSITIONS = ["wipeleft", "circlecrop", "dissolve", "smoothleft"]

def build_reel(image_paths: list[Path], audio_paths: list[Path], output_path: Path):
    """Build a reel from image + audio sequences using FFmpeg."""
    n = len(image_paths)
    filters = []
    
    # zoompan for each image
    for i in range(n):
        filters.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"zoompan=z='min(zoom+0.0015,1.12)':d={int(SCENE_DURATION*30)}:"
            f"s=1080x1920:fps=30[v{i}]"
        )
    
    # xfade chain
    xfade_chain = ""
    last = "v0"
    for i in range(1, n):
        offset = i * SCENE_DURATION - 0.5
        trans = TRANSITIONS[(i - 1) % len(TRANSITIONS)]
        xfade_chain += f"[{last}][v{i}]xfade=transition={trans}:duration=0.4:offset={offset}[v{i}out];"
        last = f"v{i}out"
    
    # Audio concat
    audio_inputs = "".join(f"[{n + i}:a]" for i in range(n))
    audio_chain = f"{audio_inputs}concat=n={n}:v=0:a=1[aout]"
    
    filter_graph = ";".join(filters) + ";" + xfade_chain[:-1] + "[vout];" + audio_chain
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(filter_graph)
        filter_path = f.name
    
    cmd = [
        "ffmpeg", "-y",
        *[item for img_path in image_paths
          for item in ["-loop", "1", "-t", str(SCENE_DURATION), "-i", str(img_path)]],
        *[item for a_path in audio_paths
          for item in ["-i", str(a_path)]],
        "-filter_complex_script", filter_path,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "h264_videotoolbox", "-b:v", "8M",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-shortest", str(output_path),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    Path(filter_path).unlink(missing_ok=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
```

### TTS Engine (17-04) — Async Batch Generation
```python
# Source: Context7 /rany2/edge-tts docs [CITED]
import asyncio, edge_tts
from pathlib import Path

async def batch_generate(scenes: list[str], output_dir: Path, voice: str = "ko-KR-SunHiNeural"):
    """Generate TTS audio + SRT for all scenes in parallel."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for i, text in enumerate(scenes):
        mp3 = output_dir / f"narration_{i+1}.mp3"
        srt = output_dir / f"narration_{i+1}.srt"
        tasks.append(_generate_one(text, voice, mp3, srt))
    await asyncio.gather(*tasks)

async def _generate_one(text: str, voice: str, mp3_path: Path, srt_path: Path):
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    submaker = edge_tts.SubMaker()
    with open(mp3_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
```

### Graph API Publisher (17-05) — Carousel Publishing Flow
```python
# Source: developers.facebook.com/docs/instagram-platform/content-publishing [CITED]
import requests, time
from typing import Optional

class InstagramPublisher:
    """Publish carousel and reel content via Instagram Graph API."""
    
    API_VERSION = "v25.0"
    
    def __init__(self, business_id: str, access_token: str):
        self.base_url = f"https://graph.facebook.com/{self.API_VERSION}/{business_id}"
        self.access_token = access_token
    
    def _post(self, endpoint: str, params: dict) -> dict:
        params["access_token"] = self.access_token
        r = requests.post(f"{self.base_url}/{endpoint}", params=params)
        r.raise_for_status()
        return r.json()
    
    def _get_container_status(self, container_id: str) -> str:
        r = requests.get(f"https://graph.facebook.com/{self.API_VERSION}/{container_id}",
                        params={"fields": "status_code", "access_token": self.access_token})
        return r.json().get("status_code", "UNKNOWN")
    
    def _poll_until_finished(self, container_id: str, max_wait: int = 300, interval: int = 5) -> bool:
        for _ in range(max_wait // interval):
            status = self._get_container_status(container_id)
            if status == "FINISHED":
                return True
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {container_id} failed: {status}")
            time.sleep(interval)
        raise TimeoutError(f"Container {container_id} did not finish in {max_wait}s")
    
    def publish_carousel(self, image_urls: list[str], caption: str) -> Optional[str]:
        """Publish a carousel. Returns media ID on success."""
        # Step 1: Create child containers
        child_ids = []
        for url in image_urls:
            resp = self._post("media", {"image_url": url, "is_carousel_item": "true"})
            child_ids.append(resp["id"])
        
        # Step 2: Poll children
        for cid in child_ids:
            self._poll_until_finished(cid)
        
        # Step 3: Create parent container
        resp = self._post("media", {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
        })
        parent_id = resp["id"]
        
        # Step 4: Poll parent
        self._poll_until_finished(parent_id)
        
        # Step 5: Publish
        resp = self._post("media_publish", {"creation_id": parent_id})
        return resp.get("id")
    
    def publish_reel(self, video_url: str, caption: str, thumb_offset_ms: int = 0) -> Optional[str]:
        """Publish a reel. Returns media ID on success."""
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
        }
        if thumb_offset_ms:
            params["thumb_offset"] = str(thumb_offset_ms)
        
        resp = self._post("media", params)
        container_id = resp["id"]
        self._poll_until_finished(container_id)
        
        resp = self._post("media_publish", {"creation_id": container_id})
        return resp.get("id")
```

### Scheduler Launchd Plist (17-06) — Template Pattern
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>kr.aikorea24.instagram-publish</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/twinssn/Projects/aikorea24/.venv/bin/python3</string>
        <string>-m</string>
        <string>pipeline.instagram</string>
        <string>publish</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/twinssn/Projects/aikorea24</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/twinssn/Projects/aikorea24/.venv/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/twinssn/Projects/aikorea24/pipeline/instagram/logs/launchd_carousel.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/twinssn/Projects/aikorea24/pipeline/instagram/logs/launchd_carousel_error.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>19</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
</dict>
</plist>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `media_type=VIDEO` for single video posts | `media_type=REELS` | 2024-2025 | VIDEO is deprecated for single posts; use REELS |
| Graph API v19.0 | Graph API v25.0 (latest) | Ongoing | Current API version at time of research |
| moviepy for video assembly | FFmpeg subprocess with filter_complex_script | Phase 17 decision | FFmpeg gives full control over zoompan/xfade/subtitles |
| python-dotenv for env loading | `pipeline/infra/env_loader.py` (Python 3.14 stdlib only) | Phase 2 | Strangler Fig pattern — use EnvConfig |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | moviepy 2.x CrossFadeIn/Out cannot do wipeleft/circle crop/smoothleft transitions | Standard Stack (Alternatives) | LOW — moviepy's crossfade handles only dissolve; our prototypes confirm xfade is only available in FFmpeg |
| A2 | 2 HTML slides per day (carousel + reels) is well within 100-post/24h Instagram limit | Common Pitfalls (Rate Limiting) | LOW — even at 2/day we're at 2% of limit |
| A3 | FFmpeg 8.1.1 videotoolbox encoding produces acceptable quality at 8Mbps | Code Examples | MEDIUM — may need tuning for 30fps 1080p; test before production |
| A4 | edge-tts SunHiNeural voice remains free and available | Standard Stack | LOW — Microsoft has removed voices before, but Korean SunHi has been stable for years |

## Open Questions

1. **Where to host media files for Graph API?**
   - What we know: Instagram requires publicly accessible URLs for images/videos. Local files won't work.
   - Options: Cloudflare R2 (public bucket), Cloudflare Pages (deploy artifacts), S3-compatible storage
   - Recommendation: R2 with public access — already using Cloudflare ecosystem, cheap, no egress fees.

2. **Should we use `facebook_business` SDK or raw `requests`?**
   - What we know: The SDK is overkill for 3 container operations. Raw `requests` is simpler.
   - What's unclear: The SDK might handle rate limiting / retry / token refresh automatically.
   - Recommendation: Start with raw `requests` (simpler, proven approach in SETUP_GRAPH_API.md). Migrate to SDK only if we need Ads API features later.

3. **How to handle token refresh automatically?**
   - What we know: Long-lived tokens last 60 days. Exchange existing token for new one before expiry.
   - Recommendation: Add `pipeline/scripts/refresh_ig_token.py` + separate launchd plist running monthly.

4. **One pipeline step or multiple?**
   - What we know: PipelineOrchestrator registers named steps and tracks each independently.
   - Recommendation: One `StepInstagramAuto` step that runs the full sub-pipeline internally. D1 recording per sub-pipeline call is sufficient granularity.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All steps | ✓ | 3.14.0 | — |
| Playwright | 17-02 HTML→PNG | ✓ | 1.61.0 (chromium-1228) | — |
| FFmpeg | 17-03 Video renderer | ✓ | 8.1.1 (videotoolbox) | — |
| edge-tts | 17-04 TTS | ✓ | 7.2.8 | — |
| Wrangler CLI | 17-06 D1 queries | ✓ | — | — |
| R2 bucket | 17-05 media hosting | ✗ | — | Need to create `aikorea24-ig-media` bucket |
| launchd | 17-06 Scheduler | ✓ | macOS built-in | — |
| Graph API token | 17-05 Publishing | ✗ | — | Need human to complete SETUP_GRAPH_API.md steps |

**Missing dependencies with no fallback:**
- R2 bucket for media hosting — must be created and configured for public access
- Instagram Graph API token — human must complete OAuth flow from SETUP_GRAPH_API.md

**Missing dependencies with fallback:**
- None — all core tools are installed

## Validation Architecture

> Skipped — `workflow.nyquist_validation` is explicitly `false` in config.json.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Long-lived Instagram tokens (60-day expiry); monthly refresh |
| V3 Session Management | yes | Single bot account token stored in `.env` + `~/.env.common` |
| V4 Access Control | no | Single-instance bot; no multi-user |
| V5 Input Validation | yes | Sanitize caption text before API call; strip dangerous characters |
| V6 Cryptography | no | All media is public content; no encryption at rest needed |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token leakage in logs | Information Disclosure | ScrubLogFilter already redacts token patterns from all log output |
| Expired token causes publish failure | Denial of Service | Token refresh cron + D1 alert when >50 days since last refresh |
| Rate limit exceeded | Denial of Service | Check `/content_publishing_limit` before publish; exponential backoff |
| Media URL timeout | Denial of Service | 30s HTTP timeout on Graph API calls; retry with backoff |

## Implementation Time Estimates

| Sub-plan | Description | Estimated Hours | Dependencies |
|----------|-------------|----------------|--------------|
| 17-02 | HTML→PNG Image Renderer | 2-3h | 17-01 (done) |
| 17-03 | FFmpeg Video Renderer | 4-6h | 17-02, 17-04 |
| 17-04 | TTS + SRT Generator | 2-3h | — |
| 17-05 | Graph API Publisher | 4-6h | 17-02, 17-03 |
| 17-06 | Scheduler + Orchestrator | 3-4h | 17-02, 17-03, 17-04, 17-05 |
| 17-07 | Integration + Docs | 2-3h | All above |
| **Total** | | **17-25h** | |

**Optimization potential:** 17-02, 17-03, and 17-04 can be built in parallel since they have independent codebases. 17-05 must come after all media generation steps. 17-06 requires all steps to be implemented.

## Dependencies Between Sub-Plans

```
17-02 (HTML→PNG) ────┐
                      ├──→ 17-03 (Video) ──→ 17-05 (Publish) ──→ 17-06 (Schedule)
17-04 (TTS/SRT) ─────┘                          │
                                                └──→ 17-07 (Test/Docs)
```

- 17-02 and 17-04 have **no dependency on each other** — can be built in parallel
- 17-03 depends on both 17-02 (PNG inputs) and 17-04 (audio inputs)
- 17-05 depends on 17-03 (MP4 for reels) and 17-02 (PNG for carousel)
- 17-06 wraps everything and depends on all steps
- 17-07 depends on all steps being testable

## Risk Assessment for macOS Deployment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Playwright Chromium crashes headless | LOW | MEDIUM | All macOS prototypes succeeded; use `headless=True` |
| FFmpeg videotoolbox encoding artifacts | MEDIUM | LOW | Test with first reel; fall back to `libx264` if quality poor |
| edge-tts API deprecation | LOW (over years) | HIGH | TTS is critical; fallback: OpenAI TTS or Google Cloud TTS |
| Graph API token expiry mid-week | MEDIUM | HIGH | 60-day window is plenty; monthly refresh cron alert at 50 days |
| macOS suspend kills launchd job | LOW (desktop) | MEDIUM | Machine is always-on; launchd restarts on resume |
| Disk space from media artifacts | LOW | LOW | ~50MB per day; 1GB/year; cleanup old files in launchd plist |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: pip show] — All Python packages confirmed installed via `pip3 show`
- [VERIFIED: codebase] — All prototypes in `pipeline/instagram/prototypes/` are working code
- [CITED: developers.facebook.com/docs/instagram-platform/content-publishing] — Instagram Graph API content publishing guide (v25.0)
- [CITED: context7.com/rany2/edge-tts] — edge-tts SubMaker/stream/Subtitle API documentation
- [VERIFIED: brew] — FFmpeg 8.1.1 with videotoolbox confirmed via `ffmpeg -version`
- [VERIFIED: launchd plists] — 20+ existing plists in `~/Library/LaunchAgents/kr.aikorea24.*` serve as templates

### Secondary (MEDIUM confidence)
- [CITED: pypi.org/project/facebook-business/] — facebook_business package on PyPI, version 25.0.2
- [CITED: github.com/facebook/facebook-python-business-sdk] — Official Meta Business SDK (setup.py confirms v25.0.2)

### Tertiary (LOW confidence)
- [ASSUMED] moviepy CrossFadeIn/Out inadequate for wipeleft/circlecrop — based on prototype observation, not official docs
- [ASSUMED] 8Mbps H.264 sufficient for 1080p@30fps Reels — training knowledge; should verify with test render

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified installed or on PyPI
- Architecture: HIGH — builds on proven pipeline infrastructure
- Pitfalls: HIGH — most are well-documented Graph API gotchas and FFmpeg escaping issues

**Research date:** 2026-07-11
**Valid until:** 2026-08-11 (stable tooling; Graph API versions may change)
