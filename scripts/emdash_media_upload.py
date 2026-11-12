#!/usr/bin/env python3
"""EmDash 미디어 업로드 헬퍼 (2026-11-12).

썸네일을 R2 로 올려 `/_emdash/api/media/file/<key>` URL 을 받는다. 이 경로를 쓰면
`public/images` 에 넣고 사이트를 재배포할 필요가 없다(주간 잡 자동화용).

인증은 `~/.env.common` 의 `EMDASH_AIKOREA24_API_TOKEN` 을 쓴다(값은 출력하지 않는다).
`User-Agent` 를 브라우저로 보내지 않으면 Cloudflare 가 1010 으로 막는다(실측).

사용:
    python3 scripts/emdash_media_upload.py <이미지경로>
"""
import os
import sys
import uuid
import urllib.request

BASE = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr").rstrip("/")
PAT_KEYS = ("EMDASH_AIKOREA24_API_TOKEN", "EMDASH_PAT", "EMDASH_API_TOKEN")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36")

_MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _pat():
    for k in PAT_KEYS:
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    common = os.path.expanduser("~/.env.common")
    if os.path.exists(common):
        with open(common, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() in PAT_KEYS:
                    v = v.strip().strip('"').strip("'")
                    if v:
                        return v
    return None


def upload_image(path):
    """이미지 1건 업로드. 성공하면 공개 URL, 실패하면 None."""
    pat = _pat()
    if not pat:
        print("  ! EmDash PAT 없음")
        return None
    ext = os.path.splitext(path)[1].lower()
    mime = _MIME.get(ext)
    if not mime:
        print(f"  ! 지원하지 않는 확장자: {ext}")
        return None
    data = open(path, "rb").read()
    boundary = "----" + uuid.uuid4().hex
    body = b"".join([
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
         f"filename=\"thumb{ext}\"\r\nContent-Type: {mime}\r\n\r\n").encode(),
        data + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(BASE + "/_emdash/api/media", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + pat)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            import json
            d = json.loads(r.read() or b"{}")
    except Exception as e:  # noqa: BLE001
        body_txt = ""
        try:
            body_txt = e.read()[:200].decode("utf-8", "ignore")
        except Exception:
            pass
        print(f"  ! 업로드 실패 {getattr(e, 'code', type(e).__name__)} {body_txt}")
        return None
    item = ((d.get("data") or {}).get("item") or {})
    key = item.get("storageKey")
    if not key:
        print("  ! 응답에 storageKey 없음")
        return None
    return f"{BASE}/_emdash/api/media/file/{key}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용법: python3 scripts/emdash_media_upload.py <이미지경로>")
    url = upload_image(sys.argv[1])
    print(url or "실패")
    sys.exit(0 if url else 2)
