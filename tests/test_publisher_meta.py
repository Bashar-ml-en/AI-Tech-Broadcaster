"""
Tests for Native Meta (Facebook & Instagram) Publisher using httpx.MockTransport.
"""

import httpx
from src.publisher_meta import (
    publish_to_meta,
    publish_to_instagram,
    publish_to_facebook,
    build_caption
)


def test_meta_caption_builder_truncates_on_word_boundary():
    long_headline = "A " * 1200
    caption = build_caption(long_headline, max_len=200)
    assert len(caption) <= 200
    assert caption.endswith("...")


def test_meta_simulation_mode_returns_previews():
    post = {"format_type": "post", "headline": "Meta Simulation Test"}
    results = publish_to_meta(post, media_refs=[])
    assert len(results) == 2
    for r in results:
        assert r["status"] == "simulated"
        assert r["mode"] == "simulated"
        assert r["request_preview"] is not None


def test_meta_skipped_when_media_not_hosted(monkeypatch):
    monkeypatch.setenv("PUBLISH_MODE", "live")
    monkeypatch.setattr("src.publisher_meta.META_PAGE_ACCESS_TOKEN", "EAABtesttokenwithmorethan20characters")

    post = {"format_type": "post", "headline": "Unstaged Test"}
    unhosted = [{"local_path": "test.png", "hosted": False, "public_url": None}]

    res_ig = publish_to_instagram(post, media_refs=unhosted)
    assert res_ig["status"] == "skipped"
    assert res_ig["error_code"] == "NO_PUBLIC_MEDIA"

    res_fb = publish_to_facebook(post, media_refs=unhosted)
    assert res_fb["status"] == "skipped"
    assert res_fb["error_code"] == "NO_PUBLIC_MEDIA"


def test_instagram_mock_transport_reel_flow(monkeypatch):
    monkeypatch.setenv("PUBLISH_MODE", "live")
    monkeypatch.setattr("src.publisher_meta.META_PAGE_ACCESS_TOKEN", "EAABtesttokenwithmorethan20characters")
    monkeypatch.setattr("src.publisher_meta.META_INSTAGRAM_ACCOUNT_ID", "17841400000000000")

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "/content_publishing_limit" in url:
            return httpx.Response(200, json={"data": [{"quota_usage": 5, "config": {"quota_total": 50}}]})
        if "/media_publish" in url and request.method == "POST":
            return httpx.Response(200, json={"id": "published_media_456"})
        if "/media" in url and request.method == "POST":
            return httpx.Response(200, json={"id": "container_123"})
        if "/container_123" in url and request.method == "GET":
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if "/published_media_456" in url and request.method == "GET":
            return httpx.Response(200, json={"permalink": "https://instagram.com/p/reel456"})
        return httpx.Response(404, json={"error": f"Not found: {url}"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    from src.publisher_meta import publish_instagram_reel
    res = publish_instagram_reel("https://r2.dev/clip.mp4", "Caption text", client=client)
    assert res["status"] == "published"
    assert res["remote_id"] == "published_media_456"
    assert "https://instagram.com/p/reel456" in res["permalink"]


def test_exchange_user_token_for_page_token():
    from src.publisher_meta import exchange_user_token_for_page_token

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "/1399811016543093" in url:
            return httpx.Response(200, json={
                "access_token": "EAABpermanentpagetokenextracted12345",
                "id": "1399811016543093",
                "name": "EraofAi Facebook Page"
            })
        return httpx.Response(404, json={"error": "Not found"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    result = exchange_user_token_for_page_token(
        token="EAABusertokenfromexplorer987654321",
        page_id="1399811016543093",
        client=client
    )
    assert result is not None
    assert result["page_token"] == "EAABpermanentpagetokenextracted12345"
    assert result["page_id"] == "1399811016543093"
    assert result["exchanged"] is True


def test_diagnose_meta_connection_with_mock():
    from src.publisher_meta import diagnose_meta_connection

    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "/1399811016543093" in url and "instagram_business_account" in url:
            return httpx.Response(200, json={
                "id": "1399811016543093",
                "name": "EraofAi",
                "instagram_business_account": {"id": "17841499999999", "username": "eraof_ai20"}
            })
        if "/1399811016543093" in url:
            return httpx.Response(200, json={
                "access_token": "EAABpageaccessvalidtoken123456789",
                "id": "1399811016543093",
                "name": "EraofAi"
            })
        if "/me/permissions" in url:
            return httpx.Response(200, json={
                "data": [
                    {"permission": "pages_manage_posts", "status": "granted"},
                    {"permission": "instagram_content_publish", "status": "granted"}
                ]
            })
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    diag = diagnose_meta_connection(
        token="EAABpageaccessvalidtoken123456789",
        page_id="1399811016543093",
        client=client
    )
    assert diag["configured"] is True
    assert diag["status"] == "ready"
    assert diag["can_post_facebook"] is True
    assert diag["instagram_account_id"] == "17841499999999"
    assert diag["instagram_username"] == "eraof_ai20"
    assert "pages_manage_posts" in diag["scopes"]

