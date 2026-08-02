"""
Posts Reels straight to the Facebook Graph API — no Make.com, no operation
quota, no image host. Facebook takes the video binary itself.

Needs FB_PAGE_ID + FB_PAGE_ACCESS_TOKEN in .env; `python get_token.py` walks
you through getting a permanent page token with the right scopes.

Reels publishing is a three-phase upload:

  start   POST /{page_id}/video_reels  upload_phase=start
          → {"video_id": …, "upload_url": …}
  upload  POST {upload_url}  with the raw bytes, Authorization: OAuth <token>
  finish  POST /{page_id}/video_reels  upload_phase=finish&video_state=PUBLISHED

ponytail: single-chunk upload, no resume. Our reels are ~300 KB; add offset
chunking only if we ever post something big enough to fail mid-transfer.
"""

import os

import requests

GRAPH = "https://graph.facebook.com"


def _creds() -> tuple[str, str, str]:
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    token   = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        raise RuntimeError(
            "FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN not set — run `python get_token.py`."
        )
    return page_id, token, os.getenv("GRAPH_API_VERSION", "v23.0")


def _check(r: requests.Response, phase: str) -> dict:
    if r.status_code >= 400:
        # Graph puts the real reason in the body; the status alone is useless
        raise RuntimeError(f"reel {phase} failed {r.status_code}: {r.text[:200]}")
    return r.json()


def post_reel(caption: str, video_path: str) -> str:
    """Publish video_path as a Reel on the page. Returns the video id."""
    page_id, token, version = _creds()
    endpoint = f"{GRAPH}/{version}/{page_id}/video_reels"

    with open(video_path, "rb") as f:
        blob = f.read()

    started = _check(requests.post(
        endpoint,
        data={"upload_phase": "start", "access_token": token},
        timeout=60,
    ), "start")

    video_id   = started["video_id"]
    upload_url = started.get("upload_url") or \
        f"https://rupload.facebook.com/video-upload/{version}/{video_id}"

    print(f"    Uploading {len(blob) // 1024} KB to Facebook…")
    _check(requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {token}",
            "offset":        "0",
            "file_size":     str(len(blob)),
        },
        data=blob,
        timeout=300,
    ), "upload")

    _check(requests.post(
        endpoint,
        data={
            "upload_phase": "finish",
            "video_id":     video_id,
            "video_state":  "PUBLISHED",
            "description":  caption,
            "access_token": token,
        },
        timeout=120,
    ), "finish")

    return video_id


def _demo() -> None:
    """Checks the three phases are built correctly without a real token —
    the parts that silently break are the OAuth header (Graph rejects a plain
    Bearer) and posting the bytes as the body rather than a multipart file.
    """
    import json
    import tempfile
    from unittest.mock import patch

    os.environ["FB_PAGE_ID"]           = "12345"
    os.environ["FB_PAGE_ACCESS_TOKEN"] = "tok"
    calls = []

    class Fake:
        status_code = 200
        text = ""
        def json(self):
            return {"video_id": "vid1",
                    "upload_url": "https://rupload.facebook.com/video-upload/v23.0/vid1"}

    def fake_post(url, **kw):
        calls.append((url, kw))
        return Fake()

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"x" * 4096)
        path = f.name

    with patch("requests.post", fake_post):
        assert post_reel("caption here", path) == "vid1"

    assert len(calls) == 3, len(calls)
    start, upload, finish = calls

    assert start[0].endswith("/v23.0/12345/video_reels")
    assert start[1]["data"]["upload_phase"] == "start"

    # Graph rejects "Bearer"; the bytes must be the body, not files=
    assert upload[0].endswith("/video-upload/v23.0/vid1")
    assert upload[1]["headers"]["Authorization"] == "OAuth tok"
    assert upload[1]["headers"]["file_size"] == "4096"
    assert upload[1]["data"] == b"x" * 4096
    assert "files" not in upload[1]

    assert finish[1]["data"]["upload_phase"] == "finish"
    assert finish[1]["data"]["video_state"] == "PUBLISHED"
    assert finish[1]["data"]["description"] == "caption here"
    assert finish[1]["data"]["video_id"] == "vid1"

    # A Graph error must surface its body, not just the status code
    error_body = json.dumps({"error": {"message": "Invalid OAuth access token"}})

    class Err:
        status_code = 400
        text = error_body
        def json(self): return {}

    with patch("requests.post", lambda url, **kw: Err()):
        try:
            post_reel("c", path)
            raise AssertionError("should have raised")
        except RuntimeError as e:
            assert "Invalid OAuth" in str(e), e

    # Missing credentials must fail loudly, before any upload work
    os.environ["FB_PAGE_ID"] = ""
    try:
        post_reel("c", path)
        raise AssertionError("should have raised")
    except RuntimeError as e:
        assert "get_token.py" in str(e)

    os.unlink(path)
    print("OK")


if __name__ == "__main__":
    _demo()
