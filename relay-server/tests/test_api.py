"""REST and WebSocket endpoints: health, token auth and the phone protocol."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main

SECRET = "test-secret"


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def test_health_endpoint_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["pc_connected"] is False


@pytest.mark.parametrize("path", ["/audit-log", "/status"])
@pytest.mark.parametrize("query", ["", "?token=", "?token=wrong-secret"])
def test_protected_endpoints_reject_missing_or_wrong_token(client, path, query):
    assert client.get(path + query).status_code == 401


def test_audit_log_with_valid_token(client):
    main.log_audit("list_directory", {"path": "~/Downloads"}, {"items": []})
    response = client.get(f"/audit-log?token={SECRET}")
    assert response.status_code == 200
    entry = response.json()["log"][0]
    assert entry["tool"] == "list_directory"
    assert entry["status"] == "success"


def test_status_with_valid_token(client):
    body = client.get(f"/status?token={SECRET}").json()
    assert body["gemini_configured"] is False
    assert body["audit_log_entries"] == 0


def test_audit_log_keeps_only_the_latest_200_entries():
    for i in range(250):
        main.log_audit("list_directory", {"i": i}, {})
    assert len(main.audit_log) == 200
    assert main.audit_log[0]["args"] == {"i": 50}  # oldest entries dropped first


@pytest.mark.parametrize("endpoint", ["/ws/phone", "/ws/pc"])
def test_websocket_with_wrong_token_is_closed_with_4001(client, endpoint):
    with client.websocket_connect(f"{endpoint}?token=wrong") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4001


def test_phone_connects_and_answers_ping(client):
    with client.websocket_connect(f"/ws/phone?token={SECRET}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "status"
        assert hello["pc_connected"] is False

        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"


def test_phone_is_told_when_the_pc_agent_connects(client):
    with client.websocket_connect(f"/ws/phone?token={SECRET}") as phone:
        phone.receive_json()  # initial status
        with client.websocket_connect(f"/ws/pc?token={SECRET}"):
            update = phone.receive_json()
            assert update["type"] == "status" and update["pc_connected"] is True
        update = phone.receive_json()
        assert update["pc_connected"] is False
