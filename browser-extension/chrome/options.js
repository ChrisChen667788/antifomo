const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const SETTINGS_KEY = "antiFomoApiBaseUrl";

const apiBaseInput = document.getElementById("api-base");
const saveBtn = document.getElementById("save-btn");
const statusEl = document.getElementById("status");

function normalizeApiBase(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) return DEFAULT_API_BASE;
  return trimmed.replace(/\/+$/, "");
}

function setStatus(message) {
  statusEl.textContent = message || "";
}

function loadSettings() {
  chrome.storage.sync.get([SETTINGS_KEY], (res) => {
    apiBaseInput.value = normalizeApiBase(res?.[SETTINGS_KEY]);
  });
}

function saveSettings() {
  const value = normalizeApiBase(apiBaseInput.value);
  chrome.storage.sync.set({ [SETTINGS_KEY]: value }, () => {
    setStatus("已保存。");
  });
}

saveBtn.addEventListener("click", saveSettings);

document.addEventListener("DOMContentLoaded", loadSettings);
