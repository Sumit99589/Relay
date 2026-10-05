# Remote PC Control Agent

[![Tests](https://github.com/Sumit99589/Relay/actions/workflows/tests.yml/badge.svg)](https://github.com/Sumit99589/Relay/actions/workflows/tests.yml)

Control your PC remotely from your phone using natural language commands. An AI agent (powered by Gemini) reasons about what to do, executes operations on your PC, and reports back — all through a chat interface.

```
[Phone: Chat UI] ←WebSocket→ [Relay Server: Cloud] ←WebSocket→ [PC Agent: Local]
                                       │
                              [Gemini API: reasoning]
```

## ✨ Features

- **Natural language control**: "Find last week's budget file and email it to john@example.com"
- **Multi-step reasoning**: The AI chains tools (search → preview → fetch → email) automatically
- **File operations**: Search, preview, fetch, and delete files (scoped to safe folders)
- **Command execution**: Run whitelisted shell commands (ls, df, du, zip, etc.)
- **Email with attachments**: Send files via Gmail API
- **Safety guardrails**: Folder scoping, command whitelist, confirmation for destructive actions, audit log
- **Real-time progress**: See each step as the agent works ("🔍 Searching files...", "📧 Sending email...")

## 🏗️ Architecture

| Component | Location | Runs on |
|---|---|---|
| **Relay Server** | `relay-server/` | Cloud (Render/Railway free tier) |
| **PC Agent** | `pc-agent/` | Your PC (background Python script) |
| **Phone UI** | `phone-ui/` | Any modern browser (Next.js on Vercel or similar) |

The PC **never accepts inbound connections** — it opens an outbound WebSocket to the relay and keeps it alive. The relay handles Gemini API calls, so the PC agent needs no API key.

## 🚀 Quick Start (Local Development)

### Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/apikey) (free)

### 1. Set up the Relay Server

```bash
cd relay-server
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Edit .env — add your GEMINI_API_KEY and set a SHARED_SECRET

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Set up the PC Agent

```bash
cd pc-agent
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Edit .env — set RELAY_URL=ws://localhost:8000/ws/pc and paste the same SHARED_SECRET

# Start the agent
python agent.py
```

### 3. Open the Phone UI

```bash
cd phone-ui
npm install
npm run dev
# Open http://localhost:3000
```

In the UI, click ⚙️ Settings and enter:
- **Relay URL**: `ws://localhost:8000`
- **Auth Token**: your `SHARED_SECRET` from the relay .env

## 📦 Deployment (Free Tier)

### Relay Server → Render.com

1. Push to GitHub
2. Create a **New Web Service** on [render.com](https://render.com)
3. Connect your repo, set root directory to `relay-server/`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables: `GEMINI_API_KEY`, `SHARED_SECRET`
7. Select **Free** instance type

### Phone UI → Vercel or another Next.js host

1. Create a new project on [vercel.com](https://vercel.com) or [netlify.com](https://netlify.com)
2. Connect your repo, set root directory to `phone-ui/`
3. Use `npm run build` as the build command
4. Deploy the generated Next.js application

### PC Agent → Your Machine

```bash
# Just run it in the background
cd pc-agent
# Update .env with your Render relay URL: wss://your-app.onrender.com/ws/pc
python agent.py
```

## 📧 Gmail API Setup (Optional)

To enable email sending:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → enable **Gmail API**
3. Create **OAuth 2.0 Client ID** (Desktop App)
4. Download `credentials.json` → place in `relay-server/`
5. On first email send, a browser window opens for OAuth consent
6. After authorizing, a `token.json` is saved for future use

Without Gmail configured, everything else works — email just returns a "not configured" error.

## 🔒 Security

- **Auth token**: Both WebSocket endpoints and the `/audit-log` and `/status` routes require the shared secret; a bad token closes the socket with code `4001`
- **Folder scoping**: File operations resolve symlinks and `..` with `realpath` and are restricted to `ALLOWED_FOLDERS` (the example `.env` scopes them to `~/Desktop`, `~/Documents`, `~/Downloads`, `/mnt`; if the variable is unset the agent defaults to `/`)
- **Injection-safe app commands**: `run_app_command` only runs pre-defined git/docker/npm/process templates, and every argument is escaped with `shlex.quote`
- **Confirmation**: Deleting a file, or overwriting an existing one, requires explicit approval on the phone
- **Audit log**: The last 200 tool calls are logged with timestamp and status, accessible from the UI

## 🛠️ Free-form Commands (`run_command`)

By default `run_command` is unrestricted (`ALLOW_UNRESTRICTED_COMMANDS=true`), so the agent can use pipes and redirection. Set `ALLOW_UNRESTRICTED_COMMANDS=false` in the PC agent's `.env` to switch to whitelist mode, where only these commands (plus their Windows equivalents) are allowed and patterns such as `rm`, `sudo` and `dd` are blocked:

```
ls, dir, find, tree, cat, head, tail, wc, grep,
df, du, free, uptime, uname, hostname, whoami, date,
zip, tar, gzip, unzip, echo, pwd, env, printenv, which, file, stat, md5sum, sha256sum
```

## 🧪 Testing

The test suite runs offline: Gemini is replaced by a scripted fake, so no API key or network is needed. GitHub Actions runs it on every push and pull request against Python 3.11, 3.12 and 3.13.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r relay-server/requirements.txt -r pc-agent/requirements.txt -r requirements-dev.txt
pytest
```

What is covered:

| Area | Tests |
|---|---|
| Path sandbox (`pc-agent/tests/test_file_ops.py`) | `..` traversal, symlink escapes, sibling folders sharing a prefix (`/x/allowed-evil`), every file tool refusing out-of-sandbox paths |
| Command injection (`pc-agent/tests/test_app_commands.py`) | `;`, `&&`, `\|`, `$()`, backticks and newlines stay a single argument, verified in a real shell; output truncation; timeouts |
| Whitelist mode (`pc-agent/tests/test_command_runner.py`) | non-whitelisted commands rejected, blocked patterns win after a whitelisted command, rejected commands never reach `subprocess` |
| API and auth (`relay-server/tests/test_api.py`) | token checks on REST and WebSocket endpoints, phone/PC connection status, audit-log cap |
| Agent loop (`relay-server/tests/test_agent_loop.py`) | PC call timeouts, confirmation gate, self-correction recovery and give-up, plan revisions, exponential backoff on 429/503 |

## 📝 License

MIT
