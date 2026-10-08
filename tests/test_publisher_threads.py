"""
Tests for Native Threads Publisher using httpx.MockTransport.
"""

import httpx
from src.publisher_threads import (
    publish_to_threads,
    build_threads_text,
    refresh_threads_token
)


def test_threads_text_length_and_truncation():
    post = {"headline": "H" * 600, "format_type": "post"}
    text = build_threads_text(post, max_len=500)
    assert len(text) <= 500
    assert text.endswith("...")


def test_threads_simulation_mode():
    post = {"headline": "Simulation Threads Post", "format_type": "post"}
    res = publish_to_threads(post, media=[])
    assert res["status"] == "simulated"
    assert res["platform"] == "threads"
    assert res["request_preview"] is not None


def test_threads_downgrades_to_text_when_media_unhosted():
    post = {"headline": "Unhosted Threads Post", "format_type": "reel"}
    media = [{"local_path": "clip.mp4", "hosted": False, "public_url": None}]
    res = publish_to_threads(post, media=media)
    assert res["status"] == "simulated"
    assert res["request_preview"]["media_type"] == "TEXT"
    assert res["note"] == "downgraded_to_text"


def test_threads_mock_transport_live_publish(monkeypatch):
    monkeypatch.setenv("PUBLISH_MODE", "live")
    monkeypatch.setattr("src.publisher_threads.THREADS_USER_ID", "178414555555")
    monkeypatch.setattr("src.publisher_threads.THREADS_ACCESS_TOKEN", "TH_ACCESS_TOKEN_MORE_THAN_20_CHARS")

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "/threads_publishing_limit" in url:
            return httpx.Response(200, json={"data": [{"quota_usage": 1, "config": {"quota_total": 250}}]})
        if "/threads_publish" in url and request.method == "POST":
            return httpx.Response(200, json={"id": "th_media_1001"})
        if "/threads" in url and request.method == "POST":
            return httpx.Response(200, json={"id": "th_container_999"})
        if "/th_container_999" in url and request.method == "GET":
            return httpx.Response(200, json={"status": "FINISHED"})
        if "/th_media_1001" in url and request.method == "GET":
            return httpx.Response(200, json={"permalink": "https://threads.net/@user/post/1001"})
        return httpx.Response(404, json={"error": f"Not found: {url}"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    post = {"headline": "Live Threads Test", "format_type": "post", "source_url": "https://example.com"}
    res = publish_to_threads(post, media=[], client=client)

    assert res["status"] == "published"
    assert res["remote_id"] == "th_media_1001"
    assert "https://threads.net/@user/post/1001" in res["permalink"]
