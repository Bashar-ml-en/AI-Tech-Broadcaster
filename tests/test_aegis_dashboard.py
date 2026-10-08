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
    # Check for Aegis Mission Control markers
    assert "AEGIS MISSION CONTROL" in html
    assert "SAHARA EDITION" in html
    assert "MULTI-AGENT DAG TOPOLOGY" in html
    assert "MCP INTEGRATION" in html
    assert "6-STAGE AUTONOMOUS PIPELINE STEPPER" in html
    assert "OMNICHANNEL FLEET COMMAND" in html
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
