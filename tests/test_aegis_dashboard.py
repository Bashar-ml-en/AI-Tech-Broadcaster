"""
Tests for Aegis Mission Control Dashboard & Telemetry APIs.
"""

import os
from pathlib import Path
from fastapi.testclient import TestClient
from src.webhook_server import app, root_dir


def test_aegis_dashboard_html_response():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    html = response.text
    # Check for Aegis Nexus Sahara markers
    assert "AEGIS NEXUS" in html
    assert "Sahara Edition" in html or "SAHARA" in html.upper()
    assert "Directed Acyclic Graph (DAG)" in html
    assert "MCP" in html
    assert "Autonomous Pipeline Stepper" in html
    assert "MEDIA STAGE" in html


def test_aegis_subagents_telemetry():
    client = TestClient(app)
    response = client.get("/api/subagents")
    assert response.status_code == 200
    data = response.json()
    assert "subagents" in data
    assert len(data["subagents"]) == 8
    names = [s["name"] for s in data["subagents"]]
    assert "SCRAPER CORE" in names
    assert "CURATOR AGENT" in names
    assert "SCRIPTWRITER" in names
    assert "NEURAL AUDIO" in names
    assert "VIDEO SYNTH" in names
    assert "QA GATEKEEPER" in names
    assert "DISPATCH FLEET" in names
    assert "ANALYTICS HARVEST" in names


def test_aegis_mcp_status():
    client = TestClient(app)
    response = client.get("/api/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert "protocol" in data
    assert "servers" in data
    server_names = [s["name"] for s in data["servers"]]
    assert "mcp_social_server" in server_names
    assert "gemini-api" in server_names
    assert "r2_storage_gateway" in server_names


def test_aegis_cycle_lock_clear():
    client = TestClient(app)
    lock_file = root_dir / "storage" / ".cycle.lock"
    # Create temporary lock file
    lock_file.touch()
    assert lock_file.exists()

    response = client.post("/api/lock/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"
    assert not lock_file.exists()

    # Second call should indicate not found
    response_second = client.post("/api/lock/clear")
    assert response_second.status_code == 200
    assert response_second.json()["status"] == "not_found"


def test_aegis_broadcast_trigger():
    client = TestClient(app)
    response = client.post("/api/broadcast/trigger", json={"format": "reel", "force": True})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "triggered"
    assert data["format"] == "reel"
    assert data["force"] is True


def test_aegis_platforms_reach_and_ledger():
    client = TestClient(app)
    reach_resp = client.get("/api/platforms/reach")
    assert reach_resp.status_code == 200
    reach_data = reach_resp.json()
    assert "total_posts" in reach_data
    assert "platforms" in reach_data
    for plat in ("telegram", "tiktok", "facebook", "instagram", "threads"):
        assert plat in reach_data["platforms"]
        p_info = reach_data["platforms"][plat]
        assert "reached_count" in p_info
        assert "unreached_count" in p_info
        assert p_info["reached_count"] + p_info["unreached_count"] == reach_data["total_posts"]

    ledger_resp = client.get("/api/platforms/telegram/ledger")
    assert ledger_resp.status_code == 200
    ledger_data = ledger_resp.json()
    assert ledger_data["platform"] == "telegram"
    assert "reached_posts" in ledger_data
    assert "unreached_posts" in ledger_data
    assert "subagent" in ledger_data


def test_aegis_subagent_action_and_mcp_execute():
    client = TestClient(app)
    sa_resp = client.post("/api/subagents/SA-06/action", json={"action": "diagnostics"})
    assert sa_resp.status_code == 200
    assert sa_resp.json()["status"] == "ok"

    mcp_resp = client.post(
        "/api/mcp/execute",
        json={"tool": "get_platform_reach_ledger", "params": {"platform": "tiktok"}}
    )
    assert mcp_resp.status_code == 200
    mcp_data = mcp_resp.json()
    assert mcp_data["jsonrpc"] == "2.0"
    assert mcp_data["tool"] == "get_platform_reach_ledger"
    assert "result" in mcp_data

