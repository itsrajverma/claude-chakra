// Minimal, safe bridge between the renderer and the main process.
// Exposes only a tiny config/IPC surface — no Node APIs leak into the page.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("chakra", {
  getConfig: () => ipcRenderer.invoke("chakra:getConfig"),
  openAdmin: () => ipcRenderer.invoke("chakra:openAdmin"),
});
