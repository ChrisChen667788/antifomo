const EVENT_KEY = "antiFomoEventLogV1";
const MAX_EVENTS = 400;

function readEvents() {
  try {
    const raw = wx.getStorageSync(EVENT_KEY);
    if (Array.isArray(raw)) return raw;
    if (typeof raw === "string" && raw) {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    }
  } catch (_) {
    // ignore
  }
  return [];
}

function writeEvents(events) {
  const safe = Array.isArray(events) ? events.slice(-MAX_EVENTS) : [];
  wx.setStorageSync(EVENT_KEY, safe);
}

function trackEvent(name, payload = {}) {
  const events = readEvents();
  events.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    ts: Date.now(),
    name,
    payload
  });
  writeEvents(events);
}

function listEvents(limit = 200) {
  return readEvents().slice(-limit).reverse();
}

function clearEvents() {
  wx.removeStorageSync(EVENT_KEY);
}

module.exports = {
  trackEvent,
  listEvents,
  clearEvents
};
