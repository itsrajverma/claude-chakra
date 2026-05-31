// Electron main process for the Claude Chakra desktop chat app.
//
// Responsibilities:
//   1. Start the Chakra proxy as a child process (unless one is already running,
//      or CHAKRA_PROXY_URL points at an external instance).
//   2. Wait for the proxy's /health endpoint to come up.
//   3. Open a chat window (renderer/) wired to the proxy's /v1/messages endpoint.
//   4. Tear the proxy child down on quit.
//
// NOTE: This is an MVP scaffold. It runs in dev mode when `chakra-server` is on
// PATH (e.g. after `uv tool install --force .` in the repo root). Bundling the
// Python proxy as a self-contained sidecar (so end users need no Python) is the
// next milestone — see desktop/README.md.

const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");

const PROXY_HOST = process.env.CHAKRA_HOST || "127.0.0.1";
const PROXY_PORT = process.env.CHAKRA_PORT || "8082";
const EXTERNAL_PROXY_URL = process.env.CHAKRA_PROXY_URL || "";
const PROXY_URL = EXTERNAL_PROXY_URL || `http://${PROXY_HOST}:${PROXY_PORT}`;
const AUTH_TOKEN = process.env.ANTHROPIC_AUTH_TOKEN || "";
const HEALTH_TIMEOUT_MS = 30000;
const HEALTH_POLL_MS = 500;

/** Command used to launch the proxy when not connecting to an external one. */
const SERVER_COMMAND = process.env.CHAKRA_SERVER_COMMAND || "chakra-server";

let proxyChild = null;
let mainWindow = null;

function startProxyIfNeeded() {
  if (EXTERNAL_PROXY_URL) {
    return; // Caller manages the proxy lifecycle.
  }
  try {
    proxyChild = spawn(SERVER_COMMAND, [], {
      env: { ...process.env, CHAKRA_OPEN_BROWSER: "0" },
      shell: process.platform === "win32",
      stdio: "ignore",
      windowsHide: true,
    });
    proxyChild.on("error", (err) => {
      console.error(`Failed to launch ${SERVER_COMMAND}: ${err.message}`);
    });
  } catch (err) {
    console.error(`Could not spawn proxy: ${err.message}`);
  }
}

function checkHealth() {
  return new Promise((resolve) => {
    const req = http.get(`${PROXY_URL}/health`, (res) => {
      res.resume();
      resolve(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForProxy() {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await checkHealth()) {
      return true;
    }
    await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
  }
  return false;
}

function createWindow(proxyReady) {
  mainWindow = new BrowserWindow({
    width: 980,
    height: 760,
    minWidth: 560,
    minHeight: 480,
    title: "Claude Chakra",
    backgroundColor: "#0f1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const params = new URLSearchParams({
    proxyUrl: PROXY_URL,
    proxyReady: proxyReady ? "1" : "0",
  });
  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"), {
    search: params.toString(),
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// Renderer asks the main process for runtime config (keeps the token out of the URL).
ipcMain.handle("chakra:getConfig", () => ({
  proxyUrl: PROXY_URL,
  authToken: AUTH_TOKEN,
  adminUrl: `${PROXY_URL}/admin`,
}));

ipcMain.handle("chakra:openAdmin", () => {
  shell.openExternal(`${PROXY_URL}/admin`);
});

app.whenReady().then(async () => {
  startProxyIfNeeded();
  const ready = await waitForProxy();
  createWindow(ready);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(ready);
    }
  });
});

function stopProxy() {
  if (proxyChild && !proxyChild.killed) {
    try {
      proxyChild.kill();
    } catch {
      // best effort
    }
    proxyChild = null;
  }
}

app.on("window-all-closed", () => {
  stopProxy();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", stopProxy);
process.on("exit", stopProxy);
