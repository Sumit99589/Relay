"""
Remote PC Control Agent — Relay Server

FastAPI application that acts as the WebSocket hub between Phone UI and PC Agent,
and hosts the Gemini reasoning loop for multi-step tool calling.
"""

import os
import sys
import json
import uuid
import asyncio
import base64
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# Ensure relay-server directory is in sys.path for internal imports
SERVER_DIR = Path(__file__).parent.resolve()
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
    HAS_GENAI_DEPS = True
except ImportError:
    genai = None
    types = None
    HAS_GENAI_DEPS = False

from tools import ALL_TOOLS, SYSTEM_PROMPT, DESTRUCTIVE_TOOLS, PC_SIDE_TOOLS, SERVER_SIDE_TOOLS, PLAN_TOOL
import gmail_service

# ─── Configuration ───────────────────────────────────────────────────────────

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SHARED_SECRET = os.getenv("SHARED_SECRET", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if not SHARED_SECRET:
    SHARED_SECRET = uuid.uuid4().hex
    logging.warning(f"No SHARED_SECRET set — auto-generated: {SHARED_SECRET}")
    logging.warning("Set this in your .env and share with the PC agent.")

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("relay")

# ─── Gemini Client ───────────────────────────────────────────────────────────

gemini_client = None

if GEMINI_API_KEY:
    if HAS_GENAI_DEPS:
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info(f"Gemini client initialized with model: {GEMINI_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
    else:
        logger.error("GEMINI_API_KEY set but 'google-genai' package is not installed.")
else:
    logger.warning("No GEMINI_API_KEY set — LLM reasoning disabled.")

# ─── FastAPI App ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Remote PC Control — Relay Server starting")
    logger.info(f"Gemini model: {GEMINI_MODEL}")
    logger.info(f"Gemini configured: {gemini_client is not None}")
    logger.info(f"Gmail configured: {gmail_service.CREDENTIALS_FILE.exists()}")
    logger.info(f"Shared secret: {SHARED_SECRET[:6]}...{SHARED_SECRET[-4:]}")
    logger.info("=" * 60)
    yield


app = FastAPI(title="Remote PC Control — Relay Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ───────────────────────────────────────────────────────────────────

# Connected clients
phone_ws: Optional[WebSocket] = None
pc_ws: Optional[WebSocket] = None

# Pending tool call responses from PC agent (id → asyncio.Future)
pending_pc_calls: dict[str, asyncio.Future] = {}

# Pending user confirmations (id → asyncio.Future)
pending_confirmations: dict[str, asyncio.Future] = {}

# Audit log (in-memory, list of dicts)
audit_log: list[dict] = []

# Chat history for Gemini (per-session, resets on reconnect)
chat_history: list[dict] = []

# ─── Plan & Self-Correction State ────────────────────────────────────────────

class TaskState:
    NO_PLAN_NEEDED = "no_plan_needed"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    EXECUTING = "executing"

# Current task state
current_task_state: str = TaskState.NO_PLAN_NEEDED

# Pending plan approval futures (id → asyncio.Future)
pending_plan_approvals: dict[str, asyncio.Future] = {}

# The single agent turn currently controlled by the phone. Keeping the task lets
# the phone cancel Gemini reasoning without changing the PC-agent protocol.
active_reasoning_task: Optional[asyncio.Task] = None

# Max self-correction retry attempts
MAX_SELF_CORRECTION_ATTEMPTS = 3


# ─── Helpers ─────────────────────────────────────────────────────────────────

def log_audit(tool_name: str, args: dict, result: dict, status: str = "success"):
    """Log a tool call to the in-memory audit log."""
    entry = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "args": args,
        "result_summary": _summarize_result(result),
        "status": status,
    }
    audit_log.append(entry)
    # Keep last 200 entries
    if len(audit_log) > 200:
        audit_log.pop(0)
    logger.info(f"Audit: {tool_name}({args}) → {status}")


def _summarize_result(result: dict) -> str:
    """Create a short summary of a tool result for the audit log."""
    result_str = json.dumps(result)
    if len(result_str) > 300:
        return result_str[:300] + "..."
    return result_str


async def send_to_phone(msg_type: str, message: str, **extra):
    """Send a JSON message to the phone client."""
    global phone_ws
    if phone_ws:
        try:
            payload = {"type": msg_type, "message": message, **extra}
            await phone_ws.send_json(payload)
        except Exception as e:
            logger.error(f"Failed to send to phone: {e}")
            phone_ws = None


async def send_to_pc(msg_type: str, **payload):
    """Send a JSON message to the PC agent."""
    global pc_ws
    if pc_ws:
        try:
            await pc_ws.send_json({"type": msg_type, **payload})
        except Exception as e:
            logger.error(f"Failed to send to PC: {e}")
            pc_ws = None


async def send_plan_to_phone(plan_id: str, plan_args: dict):
    """Send a plan proposal card to the phone for user approval."""
    global phone_ws
    if phone_ws:
        try:
            await phone_ws.send_json({
                "type": "plan_proposal",
                "id": plan_id,
                "summary": plan_args.get("summary", ""),
                "steps": list(plan_args.get("steps", [])),
                "risk_level": plan_args.get("risk_level", "low"),
            })
        except Exception as e:
            logger.error(f"Failed to send plan to phone: {e}")
            phone_ws = None


async def call_pc_tool(method: str, params: dict, timeout: float = 60.0) -> dict:
    """Send a tool call to the PC agent and wait for the result."""
    global pc_ws
    if not pc_ws:
        return {"error": "PC agent is not connected. Please make sure the agent is running on your PC."}

    call_id = uuid.uuid4().hex[:12]
    future = asyncio.get_event_loop().create_future()
    pending_pc_calls[call_id] = future

    try:
        await send_to_pc("tool_call", id=call_id, method=method, params=params)
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        return {"error": f"Tool call '{method}' timed out after {timeout}s."}
    finally:
        pending_pc_calls.pop(call_id, None)


async def request_confirmation(message: str, timeout: float = 120.0) -> bool:
    """Send a confirmation request to the phone and wait for user response."""
    confirm_id = uuid.uuid4().hex[:12]
    future = asyncio.get_event_loop().create_future()
    pending_confirmations[confirm_id] = future

    try:
        await send_to_phone("confirm", message, id=confirm_id)
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        await send_to_phone("response", "⏰ Confirmation timed out. Action cancelled.")
        return False
    finally:
        pending_confirmations.pop(confirm_id, None)


# ─── Tool Execution ─────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_args: dict) -> dict:
    """Execute a tool call, routing to PC agent or server-side handler."""

    # --- Destructive tool: require confirmation first ---
    if tool_name in DESTRUCTIVE_TOOLS:
        needs_confirm = True
        if tool_name == "delete_file":
            confirm_msg = f"⚠️ **Delete file**: `{tool_args.get('path', '?')}`\n\nThis cannot be undone. Proceed?"
        elif tool_name == "write_file":
            target_path = tool_args.get("path", "")
            # Check if target file exists before confirming overwrite
            check_res = await call_pc_tool("read_file_preview", {"path": target_path})
            if check_res and "error" not in check_res:
                confirm_msg = f"⚠️ **Overwrite file**: File `{target_path}` already exists.\n\nOverwrite with new content?"
            else:
                # File doesn't exist yet, no overwrite confirmation needed
                needs_confirm = False
        else:
            confirm_msg = f"⚠️ **Destructive action**: `{tool_name}`\n\nProceed?"

        if needs_confirm:
            await send_to_phone("response", f"🛑 Requesting confirmation for action...")
            confirmed = await request_confirmation(confirm_msg)

            if not confirmed:
                result = {"error": "Action cancelled by user."}
                log_audit(tool_name, tool_args, result, status="cancelled")
                return result

    # --- PC-side tools ---
    if tool_name in PC_SIDE_TOOLS:
        # Progress update
        progress_msgs = {
            "list_directory": f"📁 Listing directory `{tool_args.get('path', '~/Downloads')}`...",
            "search_files": "🔍 Searching files on PC...",
            "read_file_preview": f"📄 Reading preview of `{tool_args.get('path', '?')}`...",
            "fetch_file": f"📦 Fetching file `{tool_args.get('path', '?')}`...",
            "run_command": f"⚡ Running command: `{tool_args.get('command', '?')}`...",
            "delete_file": f"🗑️ Deleting `{tool_args.get('path', '?')}`...",
            "write_file": f"✏️ Writing to `{tool_args.get('path', '?')}`...",
            "append_to_file": f"📝 Appending to `{tool_args.get('path', '?')}`...",
            "create_file": f"📄 Creating file `{tool_args.get('path', '?')}`...",
            "run_app_command": f"🛠️ Running `{tool_args.get('template', '?')}`...",
            "search_file_content": f"🔍 Searching file contents for `{tool_args.get('query', '?')}`...",
        }
        await send_to_phone("response", progress_msgs.get(tool_name, f"⏳ Executing {tool_name}..."))

        result = await call_pc_tool(tool_name, tool_args)

        # For fetch_file with chunked response: initiate chunked transfer
        if tool_name == "fetch_file" and result.get("chunked"):
            file_path = result.get("path", "")
            file_name = result.get("name", "")
            file_size = result.get("size", 0)
            total_chunks = result.get("total_chunks", 0)
            checksum = result.get("checksum", "")
            mime = result.get("type", "application/octet-stream")

            size_mb = file_size / 1024 / 1024
            await send_to_phone("response", f"📦 Large file detected ({size_mb:.1f} MB). Starting chunked transfer...")

            # Send file_transfer_start to phone
            if phone_ws:
                await phone_ws.send_json({
                    "type": "file_transfer_start",
                    "name": file_name,
                    "size": file_size,
                    "total_chunks": total_chunks,
                    "mime": mime,
                    "checksum": checksum,
                })

            # Tell PC agent to start streaming chunks
            await send_to_pc("start_chunked_transfer", path=file_path)

            # Return lightweight result to Gemini (don't wait for transfer)
            gemini_result = {
                "name": file_name,
                "size": file_size,
                "type": mime,
                "status": "chunked_transfer_started",
                "message": f"Large file '{file_name}' ({size_mb:.1f} MB) is being transferred to the user's phone in {total_chunks} chunks. The transfer is happening in the background.",
            }
            log_audit(tool_name, tool_args, gemini_result, status="success")
            return gemini_result

        # For fetch_file, send payload to phone for user download, then strip base64 before passing to Gemini
        if tool_name == "fetch_file" and "data" in result and "error" not in result:
            await send_to_phone(
                "file_download",
                f"📦 File retrieved: `{result.get('name')}`",
                name=result.get("name"),
                size=result.get("size"),
                mime=result.get("type"),
                data=result["data"]
            )
            # Lightweight result for Gemini history (no huge base64 string)
            gemini_result = {
                "name": result.get("name"),
                "size": result.get("size"),
                "type": result.get("type"),
                "status": "success",
                "message": f"File '{result.get('name')}' ({result.get('size')} bytes) fetched and delivered to user's phone for download.",
            }
            log_audit(tool_name, tool_args, gemini_result, status="success")
            return gemini_result

        log_audit(tool_name, tool_args, result, status="error" if "error" in result else "success")
        return result

    # --- Server-side tools ---
    if tool_name == "send_email":
        await send_to_phone("response", f"📧 Sending email to `{tool_args.get('to', '?')}`...")

        # If attachment_path is specified, fetch the file from PC first
        attachment_data = None
        attachment_name = None

        if tool_args.get("attachment_path"):
            await send_to_phone("response", f"📦 Fetching attachment from PC...")
            file_result = await call_pc_tool("fetch_file", {"path": tool_args["attachment_path"]})

            if "error" in file_result:
                result = {"error": f"Could not fetch attachment: {file_result['error']}"}
                log_audit(tool_name, tool_args, result, status="error")
                return result

            attachment_data = base64.b64decode(file_result.get("data", ""))
            attachment_name = file_result.get("name", "attachment")

        result = gmail_service.send_email(
            to=tool_args["to"],
            subject=tool_args["subject"],
            body=tool_args["body"],
            attachment_data=attachment_data,
            attachment_name=attachment_name,
        )
        log_audit(tool_name, tool_args, result, status="error" if not result.get("success") else "success")
        return result

    return {"error": f"Unknown tool: {tool_name}"}


# ─── Gemini Reasoning Loop ──────────────────────────────────────────────────

async def request_plan_approval(plan_id: str, plan_args: dict, timeout: float = 120.0) -> dict:
    """Send a plan proposal to the phone and wait for user decision."""
    future = asyncio.get_event_loop().create_future()
    pending_plan_approvals[plan_id] = future

    try:
        await send_plan_to_phone(plan_id, plan_args)
        result = await asyncio.wait_for(future, timeout=timeout)
        return result  # {"decision": "approve"|"modify"|"reject", "feedback": "..."}
    except asyncio.TimeoutError:
        await send_to_phone("response", "⏰ Plan approval timed out. Action cancelled.")
        return {"decision": "reject", "feedback": "Timed out waiting for user approval."}
    finally:
        pending_plan_approvals.pop(plan_id, None)


async def execute_tool_with_self_correction(tool_name: str, tool_args: dict, contents: list, attempt: int = 1) -> dict:
    """Execute a tool call with self-correction on failure.
    
    If the tool fails, feeds the error back to Gemini for diagnosis and retry,
    up to MAX_SELF_CORRECTION_ATTEMPTS times.
    """
    result = await execute_tool(tool_name, tool_args)

    if result.get("error") and attempt < MAX_SELF_CORRECTION_ATTEMPTS:
        error_msg = result["error"]
        logger.warning(f"Self-correction attempt {attempt}/{MAX_SELF_CORRECTION_ATTEMPTS}: {tool_name} failed: {error_msg}")

        # Log the self-correction attempt to audit
        log_audit(tool_name, tool_args, result, status="self_correction")

        # Notify phone with amber self-correction status
        await send_to_phone("self_correction",
            f"⚠️ `{tool_name}` failed: {error_msg}. Trying a different approach...",
            attempt=attempt,
            max_attempts=MAX_SELF_CORRECTION_ATTEMPTS,
            tool=tool_name,
            error=error_msg,
        )

        # Build a correction prompt for Gemini
        correction_prompt = (
            f"The tool call {tool_name}({json.dumps(tool_args)}) failed with error: {error_msg}\n"
            f"This was attempt {attempt} of {MAX_SELF_CORRECTION_ATTEMPTS}.\n"
            f"Diagnose why this likely failed and try a different approach — for example:\n"
            f"- If a file wasn't found, use search_files or search_file_content to locate the correct path\n"
            f"- If a permission error occurred, use run_command to check permissions (e.g. ls -la) and explain what's needed\n"
            f"- If a command failed, consider whether the syntax or working directory was wrong\n"
            f"- If search_files returned no results, try search_file_content to search inside file contents\n"
            f"Do not just repeat the exact same call — adjust based on the error."
        )

        # Add the correction as a user message into the conversation
        correction_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=correction_prompt)]
        )
        contents.append(correction_content)

        # Ask Gemini for a corrective action
        try:
            response = None
            for retry in range(4):
                try:
                    # The Gemini SDK call is synchronous. Run it off the event
                    # loop so a phone-side Stop request can cancel this task
                    # immediately instead of waiting for inference to return.
                    response = await asyncio.to_thread(
                        gemini_client.models.generate_content,
                        model=GEMINI_MODEL,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=ALL_TOOLS,
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.3,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                    break
                except Exception as api_err:
                    err_str = str(api_err)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                        if retry < 3:
                            wait = 7 * (2 ** retry)
                            await asyncio.sleep(wait)
                        else:
                            raise
                    else:
                        raise

            if response and response.function_calls:
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)

                # Process the first corrective tool call
                for fc in response.function_calls:
                    next_name = fc.name
                    next_args = dict(fc.args) if fc.args else {}

                    # Don't self-correct a propose_plan — that's a plan revision, not a retry
                    if next_name == PLAN_TOOL:
                        return {"error": error_msg, "_plan_revision": next_args}

                    logger.info(f"Self-correction: trying {next_name}({next_args}) (attempt {attempt + 1})")

                    # Recursively try with incremented attempt
                    corrected_result = await execute_tool_with_self_correction(
                        next_name, next_args, contents, attempt=attempt + 1
                    )

                    # If the corrected call succeeded, notify phone
                    if not corrected_result.get("error"):
                        await send_to_phone("self_correction_resolved",
                            f"✅ Recovered: `{next_name}` succeeded after {attempt} {'retry' if attempt == 1 else 'retries'}.",
                            tool=next_name,
                            attempts=attempt + 1,
                        )

                    # Add the function response for the corrected call
                    func_response = types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=next_name,
                            response=corrected_result,
                        )]
                    )
                    contents.append(func_response)

                    return corrected_result

        except Exception as e:
            logger.error(f"Self-correction Gemini call failed: {e}")

    # If we've exhausted retries and still have an error, notify
    if result.get("error") and attempt >= MAX_SELF_CORRECTION_ATTEMPTS:
        log_audit(tool_name, tool_args, result, status="self_correction_exhausted")
        await send_to_phone("self_correction",
            f"🔧 Tried {attempt} approaches but couldn't complete `{tool_name}`. Last error: {result['error']}",
            attempt=attempt,
            max_attempts=MAX_SELF_CORRECTION_ATTEMPTS,
            tool=tool_name,
            error=result["error"],
            exhausted=True,
        )

    return result


async def run_gemini_reasoning(user_message: str):
    """Run the Gemini reasoning loop with function calling, plan approval, and self-correction."""
    global active_reasoning_task, chat_history, current_task_state

    if not gemini_client:
        await send_to_phone("final", "❌ Gemini API is not configured. Set GEMINI_API_KEY in .env and restart the server.")
        if active_reasoning_task is asyncio.current_task():
            active_reasoning_task = None
        return

    if not pc_ws:
        await send_to_phone("final", "❌ PC agent is not connected. Please start the agent on your PC first.")
        if active_reasoning_task is asyncio.current_task():
            active_reasoning_task = None
        return

    current_task_state = TaskState.NO_PLAN_NEEDED

    try:
        # Build message history
        contents = []

        # Add chat history
        for entry in chat_history:
            contents.append(entry)

        # Add new user message
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        )
        contents.append(user_content)
        chat_history.append(user_content)

        # Reasoning loop — up to 15 iterations (increased for self-correction overhead)
        max_iterations = 15
        for iteration in range(max_iterations):
            logger.info(f"Gemini reasoning iteration {iteration + 1}")

            # Retry logic for rate limits (429)
            response = None
            for retry in range(4):
                try:
                    response = gemini_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=ALL_TOOLS,
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.3,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                    break  # Success
                except Exception as api_err:
                    err_str = str(api_err)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                        if retry < 3:
                            wait = 7 * (2 ** retry)  # 7s, 14s, 28s
                            logger.warning(f"Rate limited, retrying in {wait}s (attempt {retry + 2}/4)")
                            await send_to_phone("response", f"⏳ Rate limited — retrying in {wait}s...")
                            await asyncio.sleep(wait)
                        else:
                            raise
                    else:
                        raise

            # Check for function calls
            if response.function_calls:
                # Add the model's response content once
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)

                # Process each function call
                for fc in response.function_calls:
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    logger.info(f"Gemini requested tool: {tool_name}({tool_args})")

                    # ─── Plan Interception ────────────────────────────
                    if tool_name == PLAN_TOOL:
                        current_task_state = TaskState.AWAITING_PLAN_APPROVAL
                        plan_id = uuid.uuid4().hex[:12]

                        logger.info(f"Plan proposed (risk={tool_args.get('risk_level', '?')}): {tool_args.get('summary', '?')}")
                        await send_to_phone("response", "🗺️ Planning my approach...")

                        # Wait for user approval
                        approval = await request_plan_approval(plan_id, tool_args)
                        decision = approval.get("decision", "reject")
                        feedback = approval.get("feedback", "")

                        if decision == "approve":
                            current_task_state = TaskState.EXECUTING
                            logger.info("Plan approved by user")
                            await send_to_phone("response", "✅ Plan approved — executing...")

                            # Feed approval back to Gemini
                            func_response = types.Content(
                                role="user",
                                parts=[types.Part.from_function_response(
                                    name=PLAN_TOOL,
                                    response={"approved": True, "message": "User approved the plan. Proceed with execution."},
                                )]
                            )
                            contents.append(func_response)

                        elif decision == "modify":
                            current_task_state = TaskState.NO_PLAN_NEEDED
                            logger.info(f"Plan modification requested: {feedback}")
                            await send_to_phone("response", "📝 Revising plan based on your feedback...")

                            # Feed modification back to Gemini
                            func_response = types.Content(
                                role="user",
                                parts=[types.Part.from_function_response(
                                    name=PLAN_TOOL,
                                    response={
                                        "approved": False,
                                        "user_feedback": feedback,
                                        "message": f"User wants modifications: {feedback}. Please revise your plan and call propose_plan again.",
                                    },
                                )]
                            )
                            contents.append(func_response)

                        else:  # reject
                            current_task_state = TaskState.NO_PLAN_NEEDED
                            logger.info("Plan rejected by user")
                            await send_to_phone("final", "❌ Plan rejected. Task cancelled.")

                            # Store in chat history
                            model_content = types.Content(
                                role="model",
                                parts=[types.Part.from_text(text="Plan was rejected by the user. Task cancelled.")]
                            )
                            chat_history.append(model_content)
                            return

                        # Continue the reasoning loop
                        continue

                    # ─── Normal Tool Execution (with Self-Correction) ─
                    tool_result = await execute_tool_with_self_correction(
                        tool_name, tool_args, contents
                    )

                    # Add the function response
                    func_response = types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=tool_name,
                            response=tool_result,
                        )]
                    )
                    contents.append(func_response)

                # Continue the loop — Gemini may want to call more tools
                continue

            # No function calls — this is the final text response
            final_text = response.text if response.text else "Done. No additional information to report."

            # Store in chat history
            model_content = types.Content(
                role="model",
                parts=[types.Part.from_text(text=final_text)]
            )
            chat_history.append(model_content)

            # Keep history manageable (last 20 turns)
            if len(chat_history) > 40:
                chat_history = chat_history[-20:]

            current_task_state = TaskState.NO_PLAN_NEEDED
            await send_to_phone("final", final_text)
            return

        # Exceeded max iterations
        current_task_state = TaskState.NO_PLAN_NEEDED
        await send_to_phone("final", "⚠️ Reached maximum reasoning steps. The task may be too complex — try breaking it into smaller requests.")

    except asyncio.CancelledError:
        current_task_state = TaskState.NO_PLAN_NEEDED
        logger.info("Gemini reasoning cancelled by phone")
        # A replacement request may already be active; do not let a late
        # cancellation overwrite its state in the phone UI.
        if active_reasoning_task is asyncio.current_task():
            await send_to_phone("final", "Task stopped.")
        raise
    except Exception as e:
        current_task_state = TaskState.NO_PLAN_NEEDED
        logger.error(f"Gemini reasoning error: {e}", exc_info=True)
        await send_to_phone("final", f"❌ Error during reasoning: {str(e)}")
    finally:
        if active_reasoning_task is asyncio.current_task():
            active_reasoning_task = None


# ─── WebSocket Endpoints ────────────────────────────────────────────────────

@app.websocket("/ws/phone")
async def phone_endpoint(websocket: WebSocket, token: str = Query("")):
    """WebSocket endpoint for the phone chat UI."""
    global phone_ws, active_reasoning_task

    # Auth check
    if token != SHARED_SECRET:
        # Accept first so browser WebSocket clients receive the application close
        # code instead of FastAPI translating the rejection into a generic 403.
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid auth token")
        logger.warning("Phone connection rejected: invalid token")
        return

    await websocket.accept()
    phone_ws = websocket
    logger.info("Phone client connected")

    # Send connection status
    pc_status = "connected" if pc_ws else "disconnected"
    await send_to_phone("status", f"Connected to relay. PC agent: {pc_status}", pc_connected=(pc_ws is not None))

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "chat":
                user_message = data.get("message", "").strip()
                if user_message:
                    logger.info(f"Phone message: {user_message}")
                    # Keep one current turn so a stop action always has an
                    # unambiguous target. A new request replaces an older one.
                    if active_reasoning_task and not active_reasoning_task.done():
                        active_reasoning_task.cancel()
                    active_reasoning_task = asyncio.create_task(run_gemini_reasoning(user_message))

            elif msg_type == "cancel":
                if active_reasoning_task and not active_reasoning_task.done():
                    active_reasoning_task.cancel()
                    logger.info("Phone requested cancellation of active reasoning")

            elif msg_type == "confirm_response":
                confirm_id = data.get("id", "")
                confirmed = data.get("confirmed", False)
                future = pending_confirmations.get(confirm_id)
                if future and not future.done():
                    future.set_result(confirmed)

            elif msg_type == "plan_response":
                plan_id = data.get("id", "")
                decision = data.get("decision", "reject")  # approve, modify, reject
                feedback = data.get("feedback", "")
                future = pending_plan_approvals.get(plan_id)
                if future and not future.done():
                    future.set_result({"decision": decision, "feedback": feedback})
                    logger.info(f"Plan {plan_id} response: {decision}")

            elif msg_type == "ping":
                await send_to_phone("pong", "")

    except WebSocketDisconnect:
        logger.info("Phone client disconnected")
        phone_ws = None
        if active_reasoning_task and not active_reasoning_task.done():
            active_reasoning_task.cancel()
    except Exception as e:
        logger.error(f"Phone WebSocket error: {e}")
        phone_ws = None


@app.websocket("/ws/pc")
async def pc_endpoint(websocket: WebSocket, token: str = Query("")):
    """WebSocket endpoint for the PC agent."""
    global pc_ws

    # Auth check
    if token != SHARED_SECRET:
        # Keep auth failures observable to WebSocket clients as close code 4001.
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid auth token")
        logger.warning("PC agent connection rejected: invalid token")
        return

    await websocket.accept()
    pc_ws = websocket
    logger.info("PC agent connected")

    # Notify phone
    await send_to_phone("status", "✅ PC agent is now connected!", pc_connected=True)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "tool_result":
                call_id = data.get("id", "")
                result = data.get("result", {})
                future = pending_pc_calls.get(call_id)
                if future and not future.done():
                    future.set_result(result)

            elif msg_type == "file_transfer_chunk":
                # Pass-through: forward chunk to phone client
                if phone_ws:
                    try:
                        await phone_ws.send_json(data)
                    except Exception as e:
                        logger.error(f"Failed to forward chunk to phone: {e}")

            elif msg_type == "file_transfer_end":
                # Pass-through: forward transfer end to phone client
                if phone_ws:
                    try:
                        await phone_ws.send_json(data)
                    except Exception as e:
                        logger.error(f"Failed to forward transfer end to phone: {e}")
                logger.info(f"Chunked transfer complete: {data.get('name', '?')}")

            elif msg_type == "file_transfer_error":
                # Pass-through: forward error to phone client
                if phone_ws:
                    try:
                        await phone_ws.send_json(data)
                    except Exception as e:
                        logger.error(f"Failed to forward transfer error to phone: {e}")
                logger.error(f"Chunked transfer error from PC: {data.get('error', '?')}")

            elif msg_type == "pong":
                pass  # Heartbeat response

    except WebSocketDisconnect:
        logger.info("PC agent disconnected")
        pc_ws = None
        # Notify phone
        await send_to_phone("status", "⚠️ PC agent disconnected.", pc_connected=False)
        # Fail any pending calls
        for call_id, future in list(pending_pc_calls.items()):
            if not future.done():
                future.set_result({"error": "PC agent disconnected during operation."})
    except Exception as e:
        logger.error(f"PC agent WebSocket error: {e}")
        pc_ws = None


# ─── REST Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Remote PC Control — Relay Server",
        "status": "running",
        "pc_connected": pc_ws is not None,
        "phone_connected": phone_ws is not None,
    }


@app.get("/audit-log")
async def get_audit_log(token: str = Query("")):
    """Get the audit log (requires auth token)."""
    if token != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    return JSONResponse(content={"log": audit_log})


@app.get("/status")
async def get_status(token: str = Query("")):
    """Get system status (requires auth token)."""
    if token != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    return {
        "pc_connected": pc_ws is not None,
        "phone_connected": phone_ws is not None,
        "audit_log_entries": len(audit_log),
        "chat_history_entries": len(chat_history),
        "gemini_configured": gemini_client is not None,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)



