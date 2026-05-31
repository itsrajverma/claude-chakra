# Claude Chakra — Desktop App (MVP scaffold)

A lightweight **desktop chat app** for Claude Chakra. It runs the Chakra proxy
locally and gives you a Claude-style chat window that routes your messages to the
**free model providers** Chakra supports — no paid Anthropic key, no browser tab.

> **Status: MVP scaffold — not yet click-tested.** The code is structured and
> syntax-checked, but it has **not** been launched in a GUI or packaged into an
> installer yet. Treat this as the starting point; the first real launch + the
> Python-sidecar bundling step need a developer at a desktop machine. This lives on
> the `desktop-app-mvp` branch and is **secondary** to the CLI/proxy (priority #1).

---

## What it is

- **Electron** shell (`main.js`) that:
  1. starts `chakra-server` as a child process (or connects to an external proxy),
  2. waits for the proxy's `/health` endpoint, then
  3. opens a chat window (`renderer/`) wired to the proxy's `/v1/messages`.
- A minimal **chat UI** (`renderer/`) that streams the Anthropic-shaped SSE reply
  incrementally, with a model selector and a one-click link to the Admin UI for keys.

Because chat talks to `/v1/messages` directly, **it needs no Claude Code / Node agent** —
only the proxy and your free provider keys.

## Run it in dev mode

Prerequisites: Node 18+ and Chakra installed so `chakra-server` is on your PATH
(`uv tool install --force .` from the repo root).

```bash
cd desktop
npm install
npm start
```

Set a provider key first (run `chakra-providers` or open the Admin UI at
`http://127.0.0.1:8082/admin`). Then pick a free model in the top bar, e.g.
`groq/llama-3.3-70b-versatile` or `gemini/gemini-2.5-flash`, and chat.

### Connect to an already-running proxy

```bash
CHAKRA_PROXY_URL=http://127.0.0.1:8082 npm start
```

When `CHAKRA_PROXY_URL` is set, the app will **not** spawn its own proxy.

### Environment knobs

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHAKRA_PROXY_URL` | _(empty)_ | Connect to an external proxy; skips spawning one |
| `CHAKRA_HOST` / `CHAKRA_PORT` | `127.0.0.1` / `8082` | Where to reach the proxy |
| `CHAKRA_SERVER_COMMAND` | `chakra-server` | Command used to launch the proxy |
| `ANTHROPIC_AUTH_TOKEN` | _(empty)_ | Sent as `x-api-key` if the proxy requires auth |

## Build an installer (no administrator permission)

```bash
npm run dist          # current OS
npm run dist:win      # Windows: NSIS per-user installer + portable .exe
```

The Windows installer is configured for a **per-user install with no UAC prompt**
(`nsis.perMachine: false`, `oneClick: false`) — it installs under
`%LOCALAPPDATA%\Programs` and never writes to `Program Files`. The `portable` target
produces a single `.exe` that needs no installation at all.

> First-launch note: an **unsigned** build triggers Windows SmartScreen's
> "Windows protected your PC" notice (a reputation warning, **not** an admin prompt).
> A code-signing certificate removes it. macOS needs notarization to avoid Gatekeeper.

## Roadmap (next milestones, need a desktop machine)

1. **First launch + click-test** the chat flow end to end.
2. **Bundle the Python proxy as a sidecar** (PyInstaller/Nuitka) so end users need no
   Python install — replace the `chakra-server`-on-PATH assumption.
3. **Persist chat history**, add model dropdown sourced from `/v1/models`, stop/regenerate.
4. **Code signing + auto-update** (electron-updater) for friction-free installs.
5. Optional: an "agent" mode that launches Claude Code inside the shell.

## Architecture note

This folder is intentionally isolated: it is **Node/Electron only** and is not part of
the Python package or its CI (ruff/ty/pytest). Nothing here can affect the priority-#1
proxy/CLI.
