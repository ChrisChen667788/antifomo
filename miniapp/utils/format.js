function toFeedCardLabel(action) {
  if (action === "deep_read") return "立即深读";
  if (action === "later") return "稍后精读";
  return "可放心忽略";
}

function scoreTo100(scoreValue) {
  if (scoreValue === null || scoreValue === undefined || Number.isNaN(Number(scoreValue))) {
    return 50;
  }
  const score = ((Number(scoreValue) - 1) / 4) * 100;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function formatTime(ts) {
  if (!ts) return "";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "";
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function formatCountdown(totalSeconds) {
  const safe = Math.max(0, Number(totalSeconds) || 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

module.exports = {
  toFeedCardLabel,
  scoreTo100,
  formatTime,
  formatCountdown
};
