import os
import sys

import pytest

# Configure the relay before main.py is imported: a fixed secret and no Gemini key,
# so tests never touch the network. Explicit values also stop load_dotenv() from
# picking up a developer's local .env.
os.environ["SHARED_SECRET"] = "test-secret"
os.environ["GEMINI_API_KEY"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


class FakeSocket:
    """Stands in for a connected phone or PC WebSocket and records what it was sent."""

    def __init__(self, on_send=None):
        self.sent = []
        self.on_send = on_send

    async def send_json(self, payload):
        self.sent.append(payload)
        if self.on_send:
            self.on_send(payload)

    def types(self):
        return [m["type"] for m in self.sent]


@pytest.fixture(autouse=True)
def reset_relay_state():
    """main.py keeps connection state in module globals; isolate every test."""
    main.phone_ws = None
    main.pc_ws = None
    main.gemini_client = None
    main.audit_log.clear()
    main.chat_history.clear()
    main.pending_pc_calls.clear()
    main.pending_confirmations.clear()
    main.pending_plan_approvals.clear()
    yield


@pytest.fixture
def fake_socket():
    return FakeSocket


@pytest.fixture
def phone():
    main.phone_ws = FakeSocket()
    return main.phone_ws
