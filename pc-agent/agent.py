"""
Remote PC Control Agent — PC Agent

Lightweight Python script that runs on the user's PC.
Connects outbound to the relay server via WebSocket and executes tool calls locally.
Implements auto-reconnect with exponential backoff.
"""

import os
import sys
import json
import asyncio
import logging
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────────

RELAY_URL = os.getenv("RELAY_URL", "ws://localhost:8000/ws/pc")
SHARED_SECRET = os.getenv("SHARED_SECRET", "")
ALLOWED_FOLDERS = os.getenv("ALLOWED_FOLDERS", "/").split(",")

# Reconnect settings
INITIAL_RECONNECT_DELAY = 1  # seconds
MAX_RECONNECT_DELAY = 60     # seconds
HEARTBEAT_INTERVAL = 30      # seconds

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pc-agent")

# ─── Initialize tool handlers ────────────────────────────────────────────────

from file_ops import FileOperations
from command_runner import CommandRunner
from app_commands import AppCommandRunner

file_ops = FileOperations(ALLOWED_FOLDERS)
command_runner = CommandRunner()
app_command_runner = AppCommandRunner()

# Tool dispatch map
TOOL_HANDLERS = {
    "list_directory": lambda params: file_ops.list_directory(**params),
    "search_files": lambda params: file_ops.search_files(**params),
    "search_file_content": lambda params: file_ops.search_file_content(**params),
    "read_file_preview": lambda params: file_ops.read_file_preview(**params),
    "fetch_file": lambda params: file_ops.fetch_file(**params),
    "delete_file": lambda params: file_ops.delete_file(**params),
    "write_file": lambda params: file_ops.write_file(**params),
    "append_to_file": lambda params: file_ops.append_to_file(**params),
    "create_file": lambda params: file_ops.create_file(**params),
    "run_command": lambda params: command_runner.run_command(**params),
    "run_app_command": lambda params: app_command_runner.run_app_command(**params),
}


# ─── WebSocket Client ───────────────────────────────────────────────────────

async def handle_message(websocket, data: dict):
    """Handle an incoming message from the relay server."""
    msg_type = data.get("type", "")

    if msg_type == "tool_call":
        call_id = data.get("id", "")
        method = data.get("method", "")
        params = data.get("params", {})

        logger.info(f"Tool call received: {method}({params}) [id={call_id}]")

        # Execute the tool
        handler = TOOL_HANDLERS.get(method)
        if handler:
            try:
                result = handler(params)
            except Exception as e:
                logger.error(f"Tool execution error: {e}", exc_info=True)
                result = {"error": f"Tool execution failed: {str(e)}"}
        else:
            result = {"error": f"Unknown tool: {method}"}

        # Send result back
        response = {
            "type": "tool_result",
            "id": call_id,
            "result": result,
        }
        await websocket.send(json.dumps(response))
        logger.info(f"Tool result sent for {method} [id={call_id}]")

    elif msg_type == "start_chunked_transfer":
        # Relay is requesting us to stream a large file in chunks
        file_path = data.get("path", "")
        logger.info(f"Chunked transfer requested for: {file_path}")
        await file_ops.stream_file_chunks(file_path, websocket)

    elif msg_type == "ping":
        await websocket.send(json.dumps({"type": "pong"}))

    else:
        logger.warning(f"Unknown message type: {msg_type}")


async def heartbeat(websocket):
    """Send periodic heartbeats to keep the connection alive."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send(json.dumps({"type": "ping"}))
            logger.debug("Heartbeat sent")
    except Exception:
        pass  # Connection closed, heartbeat stops


async def connect_and_listen():
    """Connect to the relay server and listen for messages."""
    # pyrefly: ignore [missing-import]
    import websockets

    # Build connection URL with auth token
    separator = "&" if "?" in RELAY_URL else "?"
    url = f"{RELAY_URL}{separator}token={SHARED_SECRET}"

    logger.info(f"Connecting to relay: {RELAY_URL}")

    async with websockets.connect(
        url,
        ping_interval=20,
        ping_timeout=10,
        max_size=10 * 1024 * 1024,  # 10 MB max message size
    ) as websocket:
        logger.info("Connected to relay server!")

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat(websocket))

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await handle_message(websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message[:100]}")
                except Exception as e:
                    logger.error(f"Message handling error: {e}", exc_info=True)
        finally:
            heartbeat_task.cancel()


async def run_agent():
    """Main loop with auto-reconnect and exponential backoff."""
    reconnect_delay = INITIAL_RECONNECT_DELAY

    while True:
        try:
            await connect_and_listen()
            # If we get here, the connection closed cleanly
            reconnect_delay = INITIAL_RECONNECT_DELAY
        except KeyboardInterrupt:
            logger.info("Agent stopped by user.")
            break
        except Exception as e:
            logger.error(f"Connection error: {e}")

        logger.info(f"Reconnecting in {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    """Start the PC agent."""
    print("=" * 60)
    print("  Remote PC Control — PC Agent")
    print("=" * 60)
    print(f"  Relay URL: {RELAY_URL}")
    print(f"  Allowed folders: {', '.join(ALLOWED_FOLDERS)}")
    print(f"  Token: {SHARED_SECRET[:6]}...{SHARED_SECRET[-4:] if len(SHARED_SECRET) > 10 else '???'}")
    print("=" * 60)

    if not SHARED_SECRET:
        logger.error("SHARED_SECRET is not set! Copy it from the relay server's .env.")
        sys.exit(1)

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logger.info("Agent stopped.")


if __name__ == "__main__":
    main()
