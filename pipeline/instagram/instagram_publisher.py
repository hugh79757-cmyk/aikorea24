"""Instagram Graph API publishing client.

urllib.request only — no requests library dependency.

Carousel workflow:
  1. Each slide PNG → POST /{ig-id}/media (is_carousel_item=true, multipart)
  2. POST /{ig-id}/media (media_type=CAROUSEL, children=[ids])
  3. POST /{ig-id}/media_publish (creation_id=container_id)

Reels workflow:
  1. POST /{ig-id}/media (media_type=REELS, multipart video upload)
  2. POST /{ig-id}/media_publish (creation_id=container_id)
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from pipeline.instagram.config import (
    ACCESS_TOKEN,
    API_VERSION,
    CAROUSEL_CAPTION_TEMPLATE,
    DEFAULT_HASHTAGS,
    GRAPH_API_BASE,
    INSTAGRAM_ACCOUNT_ID,
    MAX_IMAGE_SIZE_MB,
    MAX_PUBLISH_PER_HOUR,
    MAX_VIDEO_SIZE_MB,
    PUBLISH_LOG_FILE,
    REEL_CAPTION_TEMPLATE,
    RETRY_DELAYS_SECONDS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InstagramAPIError(Exception):
    """Instagram Graph API error with structured response data."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_body: dict | None = None,
        fb_trace_id: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}
        self.fb_trace_id = fb_trace_id


# ---------------------------------------------------------------------------
# Low-level API transport (urllib.request)
# ---------------------------------------------------------------------------


def _api_request(
    method: str,
    endpoint: str,
    data: dict[str, Any] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> dict[str, Any]:
    """Send a request to the Instagram Graph API.

    Args:
        method: HTTP method (GET, POST).
        endpoint: API path segment after /{API_VERSION}/
            e.g. "17841400123456789/media"
        data: JSON-encodable form data (for POST).
        files: Multipart files — {field_name: (filename, bytes, mime_type)}.

    Returns:
        Parsed JSON response body.

    Raises:
        InstagramAPIError: On API errors (non-2xx or error in response).
    """
    url = f"{GRAPH_API_BASE}/{API_VERSION}/{endpoint}"

    if files:
        # --- Multipart/form-data upload (local file → Graph API) ---
        body_bytes, content_type = _build_multipart_body(data or {}, files)
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": content_type},
            method=method,
        )
    else:
        # --- JSON POST or GET ---
        headers: dict[str, str] = {}
        body: bytes | None = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            result: dict[str, Any] = json.loads(raw)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        try:
            error_body = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            error_body = {"raw": body_text}

        api_err = error_body.get("error", {})
        raise InstagramAPIError(
            message=api_err.get("message", f"HTTP {exc.code}"),
            status_code=exc.code,
            response_body=error_body,
            fb_trace_id=api_err.get("fbtrace_id", ""),
        ) from exc
    except urllib.error.URLError as exc:
        raise InstagramAPIError(
            message=f"Network error: {exc.reason}",
            status_code=0,
        ) from exc

    # Check for Graph API-level errors (HTTP 200 but error in body)
    if "error" in result:
        api_err = result["error"]
        raise InstagramAPIError(
            message=api_err.get("message", "Unknown API error"),
            status_code=api_err.get("code", 0),
            response_body=result,
            fb_trace_id=api_err.get("fbtrace_id", ""),
        )

    return result


# ---------------------------------------------------------------------------
# Multipart builder (stdlib only)
# ---------------------------------------------------------------------------


def _build_multipart_body(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    """Build multipart/form-data body bytes.

    Args:
        fields: Text form fields {name: value}.
        files: File fields {field_name: (filename, data_bytes, mime_type)}.

    Returns:
        (body_bytes, content_type_header_value)
    """
    boundary = "----IGBoundary" + hex(int(time.time() * 1_000_000))
    parts: list[bytes] = []

    # Text fields
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )

    # File fields
    for field_name, (filename, file_data, mime_type) in files.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8")
        )
        parts.append(file_data)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


# ---------------------------------------------------------------------------
# Carousel publishing
# ---------------------------------------------------------------------------


def create_carousel_item_media(
    image_path: str,
    caption: str = "",
) -> str:
    """Upload a single carousel item image and return its container ID.

    Uses multipart/form-data to POST the local PNG file to the
    ``/{ig-id}/media`` endpoint with ``is_carousel_item=true``.

    Args:
        image_path: Absolute path to a PNG file.
        caption: Optional caption for this item.

    Returns:
        Container ID string (e.g. "17841405320012345").
    """
    _validate_media_file(image_path, media_type="image")

    path = Path(image_path)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    file_data = path.read_bytes()

    fields: dict[str, str] = {
        "access_token": ACCESS_TOKEN,
        "is_carousel_item": "true",
    }
    if caption:
        fields["caption"] = caption

    body, content_type = _build_multipart_body(
        fields,
        {"media": (path.name, file_data, mime)},
    )

    url = f"{GRAPH_API_BASE}/{API_VERSION}/{INSTAGRAM_ACCOUNT_ID}/media"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        try:
            error_body = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            error_body = {"raw": body_text}
        api_err = error_body.get("error", {})
        raise InstagramAPIError(
            message=api_err.get("message", f"HTTP {exc.code}"),
            status_code=exc.code,
            response_body=error_body,
            fb_trace_id=api_err.get("fbtrace_id", ""),
        ) from exc

    if "error" in result:
        api_err = result["error"]
        raise InstagramAPIError(
            message=api_err.get("message", "Carousel item creation failed"),
            status_code=api_err.get("code", 0),
            response_body=result,
            fb_trace_id=api_err.get("fbtrace_id", ""),
        )

    container_id = str(result["id"])
    logger.info("Created carousel item media: %s", container_id)
    return container_id


def create_carousel_container(
    child_media_ids: list[str],
    caption: str,
) -> str:
    """Create a CAROUSEL container from child media IDs.

    Args:
        child_media_ids: List of container IDs from create_carousel_item_media().
        caption: Caption text for the carousel post.

    Returns:
        Carousel container ID.
    """
    children_str = ",".join(child_media_ids)
    data = {
        "media_type": "CAROUSEL",
        "children": children_str,
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    }
    result = _api_request(
        "POST",
        f"{INSTAGRAM_ACCOUNT_ID}/media",
        data=data,
    )
    container_id = str(result["id"])
    logger.info("Created carousel container: %s", container_id)
    return container_id


def publish_container(creation_id: str) -> dict[str, Any]:
    """Publish a media container by its creation ID.

    Args:
        creation_id: The container ID to publish.

    Returns:
        Dict with ``id`` (published media ID) and other response fields.
    """
    data = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN,
    }
    result = _api_request(
        "POST",
        f"{INSTAGRAM_ACCOUNT_ID}/media_publish",
        data=data,
    )
    logger.info("Published container: %s → media_id=%s", creation_id, result.get("id"))
    return result


def publish_carousel(
    image_paths: list[str],
    caption: str,
) -> dict[str, Any]:
    """Full carousel publishing pipeline.

    1. Each image → create_carousel_item_media()
    2. All item IDs → create_carousel_container()
    3. publish_container()

    Rate-limited via _check_rate_limit(). Retries on transient failures.

    Args:
        image_paths: List of absolute paths to PNG files.
        caption: Post caption.

    Returns:
        Dict with ``media_id``, ``container_id``, ``item_ids``.
    """
    if not _check_rate_limit():
        raise InstagramAPIError(
            message="Rate limit exceeded — max publishes per day reached",
            status_code=429,
        )

    item_ids: list[str] = []
    for idx, img_path in enumerate(image_paths):
        logger.info("Uploading carousel item %d/%d: %s", idx + 1, len(image_paths), img_path)

        def _upload_item(path: str = img_path) -> str:
            return create_carousel_item_media(path, caption="")

        container_id = _retry_with_backoff(_upload_item)
        item_ids.append(container_id)

    # Create parent carousel container
    def _create_parent() -> str:
        return create_carousel_container(item_ids, caption)

    parent_id = _retry_with_backoff(_create_parent)

    # Publish
    def _publish() -> dict[str, Any]:
        return publish_container(parent_id)

    publish_result = _retry_with_backoff(_publish)

    # Record successful publish for rate limiting
    _record_publish()

    media_id = str(publish_result.get("id", ""))
    logger.info(
        "Carousel published: media_id=%s, container=%s, items=%s",
        media_id,
        parent_id,
        item_ids,
    )
    return {
        "media_id": media_id,
        "container_id": parent_id,
        "item_ids": item_ids,
    }


# ---------------------------------------------------------------------------
# Reels publishing
# ---------------------------------------------------------------------------


def create_reel_container(
    video_path: str,
    caption: str,
    thumbnail_path: str | None = None,
    thumb_offset: float = 0.0,
) -> str:
    """Upload a video and create a REELS container.

    Uses multipart/form-data for local MP4 file upload.

    Args:
        video_path: Absolute path to an MP4 file.
        caption: Reel caption.
        thumbnail_path: Optional custom thumbnail (not uploaded, offset used).
        thumb_offset: Thumbnail offset in seconds from start (default 0).

    Returns:
        Reel container ID.
    """
    _validate_media_file(video_path, media_type="video")

    path = Path(video_path)
    file_data = path.read_bytes()

    fields: dict[str, str] = {
        "access_token": ACCESS_TOKEN,
        "media_type": "REELS",
        "caption": caption,
    }
    if thumb_offset > 0:
        fields["thumb_offset"] = str(thumb_offset)

    body, content_type = _build_multipart_body(
        fields,
        {"media": (path.name, file_data, "video/mp4")},
    )

    url = f"{GRAPH_API_BASE}/{API_VERSION}/{INSTAGRAM_ACCOUNT_ID}/media"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        try:
            error_body = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            error_body = {"raw": body_text}
        api_err = error_body.get("error", {})
        raise InstagramAPIError(
            message=api_err.get("message", f"HTTP {exc.code}"),
            status_code=exc.code,
            response_body=error_body,
            fb_trace_id=api_err.get("fbtrace_id", ""),
        ) from exc

    if "error" in result:
        api_err = result["error"]
        raise InstagramAPIError(
            message=api_err.get("message", "Reel container creation failed"),
            status_code=api_err.get("code", 0),
            response_body=result,
            fb_trace_id=api_err.get("fbtrace_id", ""),
        )

    container_id = str(result["id"])
    logger.info("Created reel container: %s", container_id)
    return container_id


def publish_reel(
    video_path: str,
    caption: str,
    thumbnail_path: str | None = None,
) -> dict[str, Any]:
    """Full Reels publishing pipeline.

    1. create_reel_container()
    2. _check_publishing_status() — poll until FINISHED/EXPIRED
    3. publish_container()

    Rate-limited via _check_rate_limit(). Retries on transient failures.

    Args:
        video_path: Absolute path to an MP4 file.
        caption: Reel caption.
        thumbnail_path: Optional custom thumbnail path.

    Returns:
        Dict with ``media_id`` and ``container_id``.
    """
    if not _check_rate_limit():
        raise InstagramAPIError(
            message="Rate limit exceeded — max publishes per day reached",
            status_code=429,
        )

    def _create() -> str:
        return create_reel_container(video_path, caption, thumbnail_path)

    container_id = _retry_with_backoff(_create)

    # Poll for processing completion
    status = _check_publishing_status(container_id)
    if status == "EXPIRED":
        raise InstagramAPIError(
            message=f"Reel container {container_id} expired during processing",
            status_code=410,
        )
    if status != "FINISHED":
        logger.warning("Reel container status: %s (expected FINISHED)", status)

    def _publish() -> dict[str, Any]:
        return publish_container(container_id)

    publish_result = _retry_with_backoff(_publish)

    _record_publish()

    media_id = str(publish_result.get("id", ""))
    logger.info("Reel published: media_id=%s, container=%s", media_id, container_id)
    return {
        "media_id": media_id,
        "container_id": container_id,
    }


# ---------------------------------------------------------------------------
# Caption generation
# ---------------------------------------------------------------------------


def _generate_caption(
    hook_text: str,
    cta_text: str,
    hashtags: list[str] | None = None,
    template: str = CAROUSEL_CAPTION_TEMPLATE,
) -> str:
    """Generate an Instagram caption with #prefixed hashtags.

    Args:
        hook_text: Opening hook text (e.g. first slide title).
        cta_text: Call-to-action text (e.g. last slide content).
        hashtags: List of hashtag words (without #). Falls back to DEFAULT_HASHTAGS.
        template: Caption template string with {hook_text}, {cta_text}, {hashtags}.

    Returns:
        Formatted caption string.
    """
    tag_list = hashtags if hashtags is not None else DEFAULT_HASHTAGS
    formatted_tags = " ".join(f"#{h}" for h in tag_list)

    return template.format(
        hook_text=hook_text,
        cta_text=cta_text,
        hashtags=formatted_tags,
    )


# ---------------------------------------------------------------------------
# Publishing status polling
# ---------------------------------------------------------------------------


def _check_publishing_status(
    container_id: str,
    max_retries: int = 5,
    retry_delay: int = 5,
) -> str:
    """Poll a container's publishing status until terminal or max retries.

    Args:
        container_id: The container ID to check.
        max_retries: Maximum poll attempts (default 5).
        retry_delay: Seconds between polls (default 5).

    Returns:
        Status code string: ``FINISHED``, ``EXPIRED``, ``IN_PROGRESS``, etc.
    """
    for attempt in range(max_retries):
        try:
            result = _api_request(
                "GET",
                f"{container_id}?fields=status_code",
            )
            status = result.get("status_code", "UNKNOWN")
        except InstagramAPIError as exc:
            logger.warning(
                "Status check failed (attempt %d/%d): %s",
                attempt + 1,
                max_retries,
                exc.message,
            )
            status = "ERROR"

        if status in ("FINISHED", "EXPIRED", "ERROR"):
            return status

        if attempt < max_retries - 1:
            logger.info(
                "Container %s status: %s — retrying in %ds (%d/%d)",
                container_id,
                status,
                retry_delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(retry_delay)

    return status


# ---------------------------------------------------------------------------
# Media validation
# ---------------------------------------------------------------------------


def _validate_media_file(
    file_path: str,
    media_type: str = "image",
) -> bool:
    """Validate a media file exists and meets size/type constraints.

    Args:
        file_path: Path to the media file.
        media_type: ``"image"`` or ``"video"``.

    Returns:
        True if valid.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file type or size is invalid.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {file_path}")

    size_mb = path.stat().st_size / (1024 * 1024)
    suffix = path.suffix.lower()

    if media_type == "image":
        if suffix not in (".png", ".jpg", ".jpeg"):
            raise ValueError(
                f"Invalid image format: {suffix} — expected .png or .jpg"
            )
        if size_mb > MAX_IMAGE_SIZE_MB:
            raise ValueError(
                f"Image too large: {size_mb:.1f}MB > {MAX_IMAGE_SIZE_MB}MB limit"
            )
    elif media_type == "video":
        if suffix != ".mp4":
            raise ValueError(f"Invalid video format: {suffix} — expected .mp4")
        if size_mb > MAX_VIDEO_SIZE_MB:
            raise ValueError(
                f"Video too large: {size_mb:.1f}MB > {MAX_VIDEO_SIZE_MB}MB limit"
            )
    else:
        raise ValueError(f"Unknown media_type: {media_type}")

    return True


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------


class TokenManager:
    """Instagram access token lifecycle manager.

    Token source: INSTAGRAM_ACCESS_TOKEN environment variable.
    Does NOT store tokens in files — env-only per threat model T-17-05-01.
    """

    def __init__(self) -> None:
        self._token: str = ACCESS_TOKEN

    def get_token(self) -> str:
        """Return the current access token from env."""
        return self._token

    def is_token_expired(self, error: InstagramAPIError) -> bool:
        """Check if an API error indicates token expiry.

        Error codes 10 (expired) and 190 (invalid OAuth) signal expiry.
        """
        code = error.status_code
        subcode = error.response_body.get("error", {}).get("error_subcode", 0)
        return code in (10, 190) or subcode in (463, 467)

    def needs_refresh(self, token_created_days_ago: int = 0) -> bool:
        """Check if the token is approaching 60-day expiry.

        Args:
            token_created_days_ago: Days since the token was created.
                If 0, always returns False (unknown creation date).

        Returns:
            True if token is >= 55 days old (5-day buffer before 60-day expiry).
        """
        if token_created_days_ago <= 0:
            return False
        return token_created_days_ago >= 55


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def _check_rate_limit() -> bool:
    """Check if daily publish limit has been reached.

    Reads instagram_publish_log.json, counts today's publishes,
    and returns False if >= MAX_PUBLISH_PER_HOUR.

    Automatically cleans entries older than 7 days.
    """
    log_path = Path(PUBLISH_LOG_FILE)

    if not log_path.exists():
        return True

    try:
        entries: list[dict[str, Any]] = json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # Clean old entries
    fresh: list[dict[str, Any]] = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > cutoff:
                fresh.append(entry)
        except (KeyError, ValueError):
            continue

    # Write back cleaned entries
    if len(fresh) < len(entries):
        log_path.write_text(
            json.dumps(fresh, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Count today's publishes
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = 0
    for entry in fresh:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= today_start:
                today_count += 1
        except (KeyError, ValueError):
            continue

    if today_count >= MAX_PUBLISH_PER_HOUR:
        logger.warning(
            "Rate limit reached: %d/%d publishes today",
            today_count,
            MAX_PUBLISH_PER_HOUR,
        )
        return False

    return True


def _record_publish() -> None:
    """Record a successful publish to the daily log."""
    log_path = Path(PUBLISH_LOG_FILE)
    entries: list[dict[str, Any]] = []

    if log_path.exists():
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []

    entries.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "publish",
    })

    log_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Retry with exponential backoff
# ---------------------------------------------------------------------------


def _retry_with_backoff(
    func: Any,
    *args: Any,
    max_retries: int = 3,
    base_delay: int = 60,
    **kwargs: Any,
) -> Any:
    """Execute func with exponential backoff on retryable errors.

    Retryable: rate_limit (code 4), server (code 2).
    Fatal: client errors (4xx), token errors (190, 10), etc.

    Args:
        func: Callable to execute.
        *args: Positional args for func.
        max_retries: Maximum retry attempts (default 3).
        base_delay: Base delay in seconds (default 60).
        **kwargs: Keyword args for func.

    Returns:
        func's return value.

    Raises:
        InstagramAPIError: On fatal errors or after max retries exhausted.
    """
    last_error: InstagramAPIError | None = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except InstagramAPIError as exc:
            last_error = exc
            error_code = exc.response_body.get("error", {}).get("code", exc.status_code)
            error_subcode = exc.response_body.get("error", {}).get("error_subcode", 0)

            # Fatal errors — do not retry
            if error_code in (10, 190) or error_subcode in (463, 467):
                logger.error("Fatal auth error (code=%s, sub=%s): %s", error_code, error_subcode, exc.message)
                raise
            if exc.status_code >= 400 and exc.status_code < 500 and exc.status_code != 429:
                logger.error("Client error %d: %s", exc.status_code, exc.message)
                raise

            # Retryable: rate_limit (code 4), server (code 2), 429
            is_retryable = (
                error_code in (4, 2)
                or exc.status_code == 429
                or exc.status_code >= 500
            )

            if not is_retryable:
                raise

            if attempt < max_retries:
                delay = RETRY_DELAYS_SECONDS[attempt] if attempt < len(RETRY_DELAYS_SECONDS) else base_delay * (2 ** attempt)
                logger.warning(
                    "Retryable error (code=%s): %s — retrying in %ds (%d/%d)",
                    error_code,
                    exc.message,
                    delay,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(delay)

    # All retries exhausted
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Publishing verification
# ---------------------------------------------------------------------------


def verify_publishing(media_id: str) -> dict[str, Any]:
    """Verify a published media item exists and retrieve its metadata.

    Args:
        media_id: The published media ID.

    Returns:
        Dict with ``id``, ``media_type``, ``permalink``, ``timestamp``.
    """
    result = _api_request(
        "GET",
        f"{media_id}?fields=id,media_type,permalink,timestamp",
    )
    logger.info("Verified media %s: type=%s", media_id, result.get("media_type"))
    return result
