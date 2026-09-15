from unittest.mock import Mock, patch

from src.webhook_poster import _post
from src.webhook_poster import post_to_url


def test_reel_webhook_rotates_after_quota_failure(monkeypatch):
    monkeypatch.setenv("MAKE_REEL_WEBHOOK_URL", "https://one.example,https://two.example")
    quota_failure = Mock(status_code=200, text="operations exhausted")
    success = Mock(status_code=200, text="accepted")
    with patch("src.webhook_poster.random.shuffle", lambda urls: None), \
         patch("src.webhook_poster.requests.post", side_effect=[quota_failure, success]) as post:
        assert _post("MAKE_REEL_WEBHOOK_URL", "same caption", "video", "reel.mp4", b"video", "video/mp4", 1) == "posted"
    assert post.call_count == 2


def test_single_url_uses_the_same_multipart_contract():
    success = Mock(status_code=200, text="accepted")
    with patch("src.webhook_poster.requests.post", return_value=success) as post:
        assert post_to_url("https://one.example", "test", "photo", "test.jpg",
                           b"image", "image/jpeg", 60) is success
    assert post.call_args.kwargs["data"] == {"message": "test"}
    assert post.call_args.kwargs["files"]["photo"] == ("test.jpg", b"image", "image/jpeg")
