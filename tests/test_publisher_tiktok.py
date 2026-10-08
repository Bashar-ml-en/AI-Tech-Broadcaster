"""
Tests for Native TikTok Content Posting API v2 Publisher using httpx.MockTransport.
"""

from pathlib import Path
import httpx
from src.publisher_tiktok import (
    publish_to_tiktok,
    calculate_chunks,
    build_tiktok_title
)


def test_tiktok_skips_non_reel_formats():
    res_post = publish_to_tiktok({"format_type": "post", "headline": "Test Post"})
    assert res_post["status"] == "skipped"
    assert res_post["error_code"] == "FORMAT_UNSUPPORTED"

    res_story = publish_to_tiktok({"format_type": "story", "headline": "Test Story"})
    assert res_story["status"] == "skipped"
    assert res_story["error_code"] == "FORMAT_UNSUPPORTED"


def test_tiktok_calculate_chunks_math():
    # Small file (under 64MB) -> 1 chunk
    chunk_size, total_chunks = calculate_chunks(15 * 1024 * 1024)
    assert total_chunks == 1
    assert chunk_size == 15 * 1024 * 1024

    # Large file (80MB) -> chunked by 10MB
    chunk_size, total_chunks = calculate_chunks(80 * 1024 * 1024)
    assert total_chunks == 8
    assert chunk_size == 10 * 1024 * 1024


def test_tiktok_simulation_mode(monkeypatch):
    monkeypatch.setenv("PUBLISH_MODE", "simulate")
    post = {"format_type": "reel", "headline": "Simulated TikTok Reel"}
    res = publish_to_tiktok(post, media=None)
    assert res["status"] == "simulated"
    assert res["platform"] == "tiktok"
    assert res["request_preview"]["video_init"]["post_info"]["is_aigc"] is True


def test_tiktok_mock_transport_unaudited_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLISH_MODE", "live")
    monkeypatch.setattr("src.publisher_tiktok.TIKTOK_CLIENT_KEY", "tt_client_key_123")
    monkeypatch.setattr("src.publisher_tiktok.TIKTOK_ACCESS_TOKEN", "tt_access_token_123")

    # Create small test mp4 file
    test_video = tmp_path / "test.mp4"
    test_video.write_bytes(b"\x00" * 1024 * 1024)  # 1MB dummy bytes

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "/creator_info/query/" in url:
            # Unaudited app returns only SELF_ONLY
            return httpx.Response(200, json={
                "data": {
                    "privacy_level_options": ["SELF_ONLY"],
                    "duet_disabled": False
                },
                "error": {"code": "ok", "message": ""}
            })
        if "/video/init/" in url:
            return httpx.Response(200, json={
                "data": {
                    "publish_id": "v_pub_tiktok_777",
                    "upload_url": "https://upload.tiktok.com/put_bytes"
                },
                "error": {"code": "ok", "message": ""}
            })
        if "put_bytes" in url and request.method == "PUT":
            return httpx.Response(200)
        if "/status/fetch/" in url:
            return httpx.Response(200, json={
                "data": {"status": "PUBLISH_COMPLETE"},
                "error": {"code": "ok", "message": ""}
            })
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    media = {"local_path": str(test_video), "hosted": False}
    post = {"format_type": "reel", "headline": "Live TikTok Reel"}

    res = publish_to_tiktok(post, media=media, client=client)
    assert res["status"] == "published"
    assert res["remote_id"] == "v_pub_tiktok_777"
    assert res["note"] == "private_unaudited_app"
