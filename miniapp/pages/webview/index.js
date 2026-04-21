Page({
  data: {
    url: "",
  },

  onLoad(options) {
    const raw = String((options && options.url) || "").trim();
    const decoded = raw ? decodeURIComponent(raw) : "";
    this.setData({
      url: decoded,
    });
  },
});
