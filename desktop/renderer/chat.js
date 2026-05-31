// Renderer chat logic: streams Anthropic-shaped SSE from the Chakra proxy's
// /v1/messages endpoint and renders the assistant's reply incrementally.

const ANTHROPIC_VERSION = "2023-06-01";
const MAX_TOKENS = 1024;

const els = {
  messages: document.getElementById("messages"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  model: document.getElementById("model"),
  status: document.getElementById("status"),
  settings: document.getElementById("settings"),
};

let config = { proxyUrl: "http://127.0.0.1:8082", authToken: "", adminUrl: "" };
const history = []; // [{ role: "user" | "assistant", content: "..." }]
let streaming = false;

async function init() {
  try {
    if (window.chakra) {
      config = await window.chakra.getConfig();
    }
  } catch {
    // fall back to defaults
  }
  const params = new URLSearchParams(window.location.search);
  if (params.get("proxyReady") === "0") {
    setStatus(
      "Proxy not detected yet. Start it with `chakra-server`, or set CHAKRA_PROXY_URL.",
      true,
    );
  }
  wireEvents();
}

function setStatus(text, isError = false) {
  els.status.textContent = text || "";
  els.status.classList.toggle("error", Boolean(isError));
}

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  const roleEl = document.createElement("span");
  roleEl.className = "role";
  roleEl.textContent = role === "user" ? "You" : "Assistant";
  const body = document.createElement("span");
  body.className = "body";
  body.textContent = text;
  node.append(roleEl, body);
  els.messages.appendChild(node);
  els.messages.scrollTop = els.messages.scrollHeight;
  return body;
}

function buildHeaders() {
  const headers = {
    "content-type": "application/json",
    "anthropic-version": ANTHROPIC_VERSION,
  };
  if (config.authToken) {
    headers["x-api-key"] = config.authToken;
    headers["authorization"] = `Bearer ${config.authToken}`;
  }
  return headers;
}

function parseSseEvent(chunk, onText, onError) {
  for (const line of chunk.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const data = trimmed.slice(5).trim();
    if (!data || data === "[DONE]") continue;
    let payload;
    try {
      payload = JSON.parse(data);
    } catch {
      continue;
    }
    if (payload.type === "content_block_delta" && payload.delta) {
      if (typeof payload.delta.text === "string") onText(payload.delta.text);
    } else if (payload.type === "error") {
      onError(payload.error?.message || "Upstream error");
    }
  }
}

async function send() {
  const text = els.input.value.trim();
  if (!text || streaming) return;

  els.input.value = "";
  els.input.style.height = "auto";
  addMessage("user", text);
  history.push({ role: "user", content: text });

  const assistantBody = addMessage("assistant", "");
  let assistantText = "";
  streaming = true;
  els.send.disabled = true;
  setStatus("Thinking…");

  try {
    const res = await fetch(`${config.proxyUrl}/v1/messages`, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({
        model: els.model.value.trim(),
        max_tokens: MAX_TOKENS,
        stream: true,
        messages: history,
      }),
    });

    if (!res.ok || !res.body) {
      const detail = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${detail}`.trim());
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let failed = null;

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const evt of events) {
        parseSseEvent(
          evt,
          (t) => {
            assistantText += t;
            assistantBody.textContent = assistantText;
            els.messages.scrollTop = els.messages.scrollHeight;
          },
          (msg) => {
            failed = msg;
          },
        );
      }
    }

    if (failed) throw new Error(failed);
    history.push({ role: "assistant", content: assistantText });
    setStatus("");
  } catch (err) {
    assistantBody.textContent = assistantText || "(no response)";
    setStatus(`Request failed: ${err.message}`, true);
    // Roll back the user turn so a retry doesn't double-send context.
    if (history.at(-1)?.role === "user") history.pop();
  } finally {
    streaming = false;
    els.send.disabled = false;
  }
}

function wireEvents() {
  els.send.addEventListener("click", send);
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  els.input.addEventListener("input", () => {
    els.input.style.height = "auto";
    els.input.style.height = `${Math.min(els.input.scrollHeight, 200)}px`;
  });
  els.settings.addEventListener("click", () => {
    if (window.chakra) window.chakra.openAdmin();
  });
}

init();
