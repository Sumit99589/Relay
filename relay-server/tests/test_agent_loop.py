"""Agent loop: PC calls, confirmation gates, self-correction and rate-limit backoff.

Gemini is replaced by a scripted fake, so these tests run offline and deterministically.
"""

import asyncio
from types import SimpleNamespace

import pytest

import main


# ─── Fakes ───────────────────────────────────────────────────────────────────

def gemini_call(name, **args):
    """A Gemini response asking for one function call."""
    return SimpleNamespace(function_calls=[SimpleNamespace(name=name, args=args)], candidates=[])


class ScriptedGemini:
    """Returns (or raises) the scripted items in order, one per generate_content call."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.calls += 1
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


class ScriptedTools:
    """Replaces execute_tool: maps tool name to a result and records every call."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    async def __call__(self, name, args):
        self.calls.append(name)
        return self.results[name]


@pytest.fixture
def no_sleep(monkeypatch):
    """Record backoff delays instead of actually waiting."""
    delays = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds, *args, **kwargs):
        delays.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    return delays


# ─── PC tool calls ───────────────────────────────────────────────────────────

async def test_pc_call_fails_fast_when_agent_is_offline():
    result = await main.call_pc_tool("list_directory", {"path": "~"})
    assert "not connected" in result["error"]


async def test_pc_call_resolves_when_agent_replies(fake_socket):
    def reply(payload):
        main.pending_pc_calls[payload["id"]].set_result({"items": ["a.txt"]})

    main.pc_ws = fake_socket(on_send=reply)
    result = await main.call_pc_tool("list_directory", {"path": "~"})
    assert result == {"items": ["a.txt"]}
    assert main.pending_pc_calls == {}  # no leaked futures


async def test_pc_call_times_out_and_cleans_up(fake_socket):
    main.pc_ws = fake_socket()  # never replies
    result = await main.call_pc_tool("list_directory", {"path": "~"}, timeout=0.05)
    assert "timed out" in result["error"]
    assert main.pending_pc_calls == {}


# ─── Confirmation gate ───────────────────────────────────────────────────────

async def test_declined_delete_never_reaches_the_pc(phone, monkeypatch):
    pc_calls = []

    async def fake_pc_call(method, params, timeout=60.0):
        pc_calls.append(method)
        return {"success": True}

    async def user_says_no(message, timeout=120.0):
        return False

    monkeypatch.setattr(main, "call_pc_tool", fake_pc_call)
    monkeypatch.setattr(main, "request_confirmation", user_says_no)

    result = await main.execute_tool("delete_file", {"path": "~/Documents/report.pdf"})

    assert result == {"error": "Action cancelled by user."}
    assert pc_calls == []
    assert main.audit_log[-1]["status"] == "cancelled"


async def test_writing_a_new_file_skips_the_overwrite_prompt(phone, monkeypatch):
    async def fake_pc_call(method, params, timeout=60.0):
        if method == "read_file_preview":
            return {"error": "File not found"}  # target does not exist yet
        return {"success": True}

    async def must_not_ask(message, timeout=120.0):
        raise AssertionError("no confirmation needed for a brand-new file")

    monkeypatch.setattr(main, "call_pc_tool", fake_pc_call)
    monkeypatch.setattr(main, "request_confirmation", must_not_ask)

    result = await main.execute_tool("write_file", {"path": "~/new.txt", "content": "hi"})
    assert result == {"success": True}


async def test_confirmation_times_out_as_a_refusal(phone):
    confirmed = await main.request_confirmation("Delete?", timeout=0.05)
    assert confirmed is False
    assert main.pending_confirmations == {}


# ─── Self-correction ─────────────────────────────────────────────────────────

async def test_successful_tool_does_not_consult_gemini(phone, monkeypatch):
    gemini = ScriptedGemini(AssertionError("Gemini should not be called"))
    main.gemini_client = gemini
    monkeypatch.setattr(main, "execute_tool", ScriptedTools({"list_directory": {"items": []}}))

    result = await main.execute_tool_with_self_correction("list_directory", {}, contents=[])

    assert result == {"items": []}
    assert gemini.calls == 0


async def test_failed_tool_is_corrected_by_gemini(phone, monkeypatch):
    tools = ScriptedTools({
        "read_file_preview": {"error": "File not found: ~/budget.xlsx"},
        "search_files": {"results": ["~/Documents/budget-2026.xlsx"]},
    })
    main.gemini_client = ScriptedGemini(gemini_call("search_files", query="budget"))
    monkeypatch.setattr(main, "execute_tool", tools)
    contents = []

    result = await main.execute_tool_with_self_correction("read_file_preview", {"path": "~/budget.xlsx"}, contents)

    assert result == {"results": ["~/Documents/budget-2026.xlsx"]}
    assert tools.calls == ["read_file_preview", "search_files"]
    assert phone.types() == ["self_correction", "self_correction_resolved"]
    # The error is fed back to the model so it can diagnose the failure.
    assert "File not found" in contents[0].parts[0].text


async def test_self_correction_gives_up_after_max_attempts(phone, monkeypatch):
    tools = ScriptedTools({"read_file_preview": {"error": "Permission denied"}})
    main.gemini_client = ScriptedGemini(gemini_call("read_file_preview", path="~/x"))
    monkeypatch.setattr(main, "execute_tool", tools)

    result = await main.execute_tool_with_self_correction("read_file_preview", {"path": "~/x"}, contents=[])

    assert result == {"error": "Permission denied"}
    assert len(tools.calls) == main.MAX_SELF_CORRECTION_ATTEMPTS
    assert phone.sent[-1]["exhausted"] is True
    assert main.audit_log[-1]["status"] == "self_correction_exhausted"


async def test_plan_proposal_during_correction_is_returned_as_a_plan_revision(phone, monkeypatch):
    main.gemini_client = ScriptedGemini(gemini_call(main.PLAN_TOOL, summary="Ask first", steps=["a"]))
    monkeypatch.setattr(main, "execute_tool", ScriptedTools({"run_command": {"error": "boom"}}))

    result = await main.execute_tool_with_self_correction("run_command", {"command": "x"}, contents=[])

    assert result["error"] == "boom"
    assert result["_plan_revision"]["summary"] == "Ask first"


async def test_rate_limited_gemini_calls_back_off_exponentially(phone, monkeypatch, no_sleep):
    tools = ScriptedTools({"read_file_preview": {"error": "not found"}, "search_files": {"results": []}})
    gemini = ScriptedGemini(
        RuntimeError("429 RESOURCE_EXHAUSTED"),
        RuntimeError("503 UNAVAILABLE"),
        gemini_call("search_files", query="x"),
    )
    main.gemini_client = gemini
    monkeypatch.setattr(main, "execute_tool", tools)

    result = await main.execute_tool_with_self_correction("read_file_preview", {"path": "x"}, contents=[])

    assert result == {"results": []}
    assert gemini.calls == 3
    assert no_sleep == [7, 14]  # 7s, then doubled


async def test_non_retryable_gemini_error_keeps_the_original_tool_error(phone, monkeypatch, no_sleep):
    main.gemini_client = ScriptedGemini(ValueError("400 INVALID_ARGUMENT"))
    monkeypatch.setattr(main, "execute_tool", ScriptedTools({"fetch_file": {"error": "too big"}}))

    result = await main.execute_tool_with_self_correction("fetch_file", {"path": "x"}, contents=[])

    assert result == {"error": "too big"}
    assert no_sleep == []  # no pointless retries on a bad request
