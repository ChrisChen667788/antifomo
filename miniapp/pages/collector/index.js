const {
  getCollectorDaemonStatus,
  getCollectorStatus,
  getWechatAgentCapturePreview,
  getWechatAgentBatchStatus,
  getWechatAgentConfig,
  getWechatAgentHealth,
  getWechatAgentOCRPreview,
  getWechatAgentStatus,
  ingestOCRImage,
  listCollectorFailed,
  processCollectorPending,
  runCollectorDaemonOnce,
  runWechatAgentOnce,
  retryCollectorFailed,
  runWechatAgentSelfHeal,
  startCollectorDaemon,
  startWechatAgent,
  stopCollectorDaemon,
  stopWechatAgent,
  updateWechatAgentConfig,
  getCollectorDailySummary,
  listCollectorSources,
  listCollectorFeedSources,
  createCollectorSource,
  createCollectorRssSource,
  importCollectorSources,
  pullCollectorRssFeeds,
  updateCollectorSource,
  deleteCollectorSource
} = require("../../utils/api");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

function textByLanguage(language, mapping, fallback) {
  if (mapping[language]) return mapping[language];
  if (language === "zh-TW" && mapping["zh-CN"]) return mapping["zh-CN"];
  if (mapping.en) return mapping.en;
  return fallback;
}

function parseUrls(value) {
  const lines = String(value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const output = [];
  const seen = new Set();
  lines.forEach((line) => {
    if (!/^https?:\/\//i.test(line)) return;
    if (seen.has(line)) return;
    seen.add(line);
    output.push(line);
  });
  return output;
}

function formatTs(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  const yy = parsed.getFullYear();
  const mm = String(parsed.getMonth() + 1).padStart(2, "0");
  const dd = String(parsed.getDate()).padStart(2, "0");
  const hh = String(parsed.getHours()).padStart(2, "0");
  const min = String(parsed.getMinutes()).padStart(2, "0");
  const sec = String(parsed.getSeconds()).padStart(2, "0");
  return `${yy}-${mm}-${dd} ${hh}:${min}:${sec}`;
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return "-";
  const safe = Math.max(0, Math.floor(Number(seconds)));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatBytes(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const size = Number(value);
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

function hasBatchSnapshot(status) {
  if (!status) return false;
  return !!(
    status.total_segments ||
    status.finished_at ||
    status.running ||
    status.submitted ||
    status.submitted_new ||
    status.deduplicated_existing ||
    status.skipped_seen ||
    status.failed
  );
}

function buildBatchStatusView(status, i18n) {
  if (!hasBatchSnapshot(status)) {
    return {
      visible: false,
      progress: 0,
      title: "",
      summary: "",
      lastMessage: "",
      lastError: "",
      metrics: {
        submittedNew: 0,
        submittedUrl: 0,
        submittedUrlDirect: 0,
        submittedUrlShareCopy: 0,
        submittedUrlResolved: 0,
        submittedOcr: 0,
        deduplicatedExisting: 0,
        skippedSeen: 0,
        failed: 0
      }
    };
  }
  const totalSegments = Math.max(Number(status.total_segments || 0), 0);
  const currentSegment = Math.max(Number(status.current_segment_index || 0), status.running ? 1 : 0);
  const progress = totalSegments
    ? status.running
      ? Math.max(8, Math.min(96, Math.round((currentSegment / totalSegments) * 100)))
      : status.finished_at
        ? 100
        : 0
    : 0;
  const submittedUrl = Math.max(Number(status.submitted_url || 0), Number(status.live_report_submitted_url || 0));
  const submittedUrlDirect = Math.max(
    Number(status.submitted_url_direct || 0),
    Number(status.live_report_submitted_url_direct || 0)
  );
  const submittedUrlShareCopy = Math.max(
    Number(status.submitted_url_share_copy || 0),
    Number(status.live_report_submitted_url_share_copy || 0)
  );
  const submittedUrlResolved = Math.max(
    Number(status.submitted_url_resolved || 0),
    Number(status.live_report_submitted_url_resolved || 0)
  );
  const submittedOcr = Math.max(Number(status.submitted_ocr || 0), Number(status.live_report_submitted_ocr || 0));
  return {
    visible: true,
    progress,
    title: status.running ? i18n.wechatAgentBatchRunning : i18n.wechatAgentBatchLatest,
    summary: status.running
      ? `第 ${Math.max(currentSegment, 1)}/${Math.max(totalSegments, 1)} 段 · ${i18n.wechatAgentBatchSubmitted} ${Number(status.submitted || 0)} ${i18n.itemsUnit}`
      : `第 ${Math.max(totalSegments, 0)} ${i18n.wechatAgentBatchSegments} · ${i18n.wechatAgentBatchSubmitted} ${Number(status.submitted || 0)} ${i18n.itemsUnit}`,
    lastMessage: status.last_message || "",
    lastError: status.last_error || "",
    metrics: {
      submittedNew: Number(status.submitted_new || 0),
      submittedUrl,
      submittedUrlDirect,
      submittedUrlShareCopy,
      submittedUrlResolved,
      submittedOcr,
      deduplicatedExisting: Number(status.deduplicated_existing || 0),
      skippedSeen: Number(status.skipped_seen || 0),
      failed: Number(status.failed || 0)
    }
  };
}

Page({
  data: {
    prefClass: "",
    i18n: {},
    filePath: "",
    imagePreview: "",
    sourceUrl: "",
    titleHint: "",
    submitting: false,
    processingPending: false,
    retryingFailed: false,
    generatingDaily: false,
    message: "",
    resultItem: null,
    collectorStatus: null,
    daemonStatus: null,
    daemonOutput: "",
    daemonAction: "",
    daemonUptimeLabel: "-",
    daemonLastReportLabel: "-",
    daemonLastDailyLabel: "-",
    daemonLogText: "-",
    wechatAgentStatus: null,
    wechatAgentHealth: null,
    wechatAgentOutput: "",
    wechatAgentAction: "",
    wechatAgentUptimeLabel: "-",
    wechatAgentLastCycleLabel: "-",
    wechatAgentLogText: "-",
    wechatAgentConfig: null,
    wechatAgentCapturePreview: null,
    wechatAgentCaptureImage: "",
    wechatAgentOCRPreview: null,
    wechatAgentBatchStatus: null,
    wechatAgentBatchView: {
      visible: false,
      progress: 0,
      title: "",
      summary: "",
      lastMessage: "",
      lastError: "",
      metrics: {
        submittedNew: 0,
        submittedUrl: 0,
        submittedOcr: 0,
        deduplicatedExisting: 0,
        skippedSeen: 0,
        failed: 0
      }
    },
    failedItems: [],
    dailyMarkdown: "",
    collectorSources: [],
    collectorFeeds: [],
    rssFeedInput: "",
    rssFeedTitleInput: "",
    addingFeed: false,
    syncingFeeds: false,
    latestFeedSyncSummary: "",
    sourceManagerInput: "",
    batchSourceInput: "",
    batchSourceCount: 0,
    addingSource: false,
    importingSource: false,
    togglingSourceId: "",
    deletingSourceId: "",
    startingDaemon: false,
    stoppingDaemon: false,
    runningDaemonOnce: false,
    startingWechatAgent: false,
    stoppingWechatAgent: false,
    runningWechatAgentOnce: false,
    checkingWechatAgentHealth: false,
    healingWechatAgent: false,
    capturingWechatPreview: false,
    runningWechatOCRPreview: false,
    savingWechatAgentConfig: false
  },

  onLoad() {
    this.applyPreferences();
    this.refreshCollectorStatus();
  },

  onShow() {
    this.applyPreferences();
  },

  onPullDownRefresh() {
    this.refreshCollectorStatus().finally(() => wx.stopPullDownRefresh());
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: textByLanguage(language, {
        "zh-CN": "Collector Pipeline",
        "zh-TW": "Collector Pipeline",
        en: "Collector Pipeline",
        ja: "Collector Pipeline",
        ko: "Collector Pipeline"
      }, "Collector Pipeline"),
      title: textByLanguage(language, {
        "zh-CN": "公众号 OCR 入库",
        "zh-TW": "公眾號 OCR 入庫",
        en: "WeChat OCR Intake",
        ja: "WeChat OCR 取り込み",
        ko: "위챗 OCR 수집"
      }, "公众号 OCR 入库"),
      subtitle: textByLanguage(language, {
        "zh-CN": "手机端上传公众号截图，后台自动 OCR 并进入 Anti-fomo 过滤流程。",
        "zh-TW": "手機端上傳公眾號截圖，後台自動 OCR 並進入 Anti-fomo 過濾流程。",
        en: "Upload article screenshots from mobile. Backend OCR pushes content into Anti-fomo pipeline.",
        ja: "モバイルで記事スクリーンショットをアップロードすると、バックエンドOCRで Anti-fomo に取り込みます。",
        ko: "모바일에서 기사 스크린샷을 업로드하면 백엔드 OCR을 거쳐 Anti-fomo 파이프라인으로 들어갑니다."
      }, "手机端上传公众号截图，后台自动 OCR 并进入 Anti-fomo 过滤流程。"),
      chooseImage: textByLanguage(language, {
        "zh-CN": "选择截图",
        "zh-TW": "選擇截圖",
        en: "Choose Screenshot",
        ja: "画像を選択",
        ko: "스크린샷 선택"
      }, "选择截图"),
      sourceUrl: textByLanguage(language, {
        "zh-CN": "来源 URL（可选）",
        "zh-TW": "來源 URL（可選）",
        en: "Source URL (Optional)",
        ja: "元URL（任意）",
        ko: "원본 URL (선택)"
      }, "来源 URL（可选）"),
      sourceUrlPlaceholder: "https://mp.weixin.qq.com/s/...",
      titleHint: textByLanguage(language, {
        "zh-CN": "标题提示（可选）",
        "zh-TW": "標題提示（可選）",
        en: "Title Hint (Optional)",
        ja: "タイトル補助（任意）",
        ko: "제목 힌트 (선택)"
      }, "标题提示（可选）"),
      titleHintPlaceholder: textByLanguage(language, {
        "zh-CN": "例如：AI Agent 周报",
        "zh-TW": "例如：AI Agent 週報",
        en: "e.g. AI Agent Weekly",
        ja: "例: AI Agent 週報",
        ko: "예: AI Agent 주간"
      }, "例如：AI Agent 周报"),
      submit: textByLanguage(language, {
        "zh-CN": "提交 OCR 入库",
        "zh-TW": "提交 OCR 入庫",
        en: "Submit OCR Intake",
        ja: "OCR取り込み実行",
        ko: "OCR 수집 제출"
      }, "提交 OCR 入库"),
      submitting: textByLanguage(language, {
        "zh-CN": "提交中...",
        "zh-TW": "提交中...",
        en: "Submitting...",
        ja: "送信中...",
        ko: "제출 중..."
      }, "提交中..."),
      statusTitle: textByLanguage(language, {
        "zh-CN": "采集状态（24h）",
        "zh-TW": "採集狀態（24h）",
        en: "Collector Status (24h)",
        ja: "収集ステータス（24h）",
        ko: "수집 상태 (24h)"
      }, "采集状态（24h）"),
      daemonTitle: textByLanguage(language, {
        "zh-CN": "采集器守护进程",
        "zh-TW": "採集器守護進程",
        en: "Collector Daemon",
        ja: "収集デーモン",
        ko: "수집 데몬"
      }, "采集器守护进程"),
      daemonRunning: textByLanguage(language, {
        "zh-CN": "运行中",
        "zh-TW": "運行中",
        en: "Running",
        ja: "稼働中",
        ko: "실행 중"
      }, "运行中"),
      daemonStopped: textByLanguage(language, {
        "zh-CN": "已停止",
        "zh-TW": "已停止",
        en: "Stopped",
        ja: "停止中",
        ko: "중지됨"
      }, "已停止"),
      startDaemon: textByLanguage(language, {
        "zh-CN": "启动采集器",
        "zh-TW": "啟動採集器",
        en: "Start",
        ja: "開始",
        ko: "시작"
      }, "启动采集器"),
      stopDaemon: textByLanguage(language, {
        "zh-CN": "停止采集器",
        "zh-TW": "停止採集器",
        en: "Stop",
        ja: "停止",
        ko: "중지"
      }, "停止采集器"),
      runDaemonOnce: textByLanguage(language, {
        "zh-CN": "执行单轮采集",
        "zh-TW": "執行單輪採集",
        en: "Run Once",
        ja: "単発実行",
        ko: "1회 실행"
      }, "执行单轮采集"),
      daemonPid: textByLanguage(language, {
        "zh-CN": "PID",
        "zh-TW": "PID",
        en: "PID",
        ja: "PID",
        ko: "PID"
      }, "PID"),
      daemonUptime: textByLanguage(language, {
        "zh-CN": "运行时长",
        "zh-TW": "運行時長",
        en: "Uptime",
        ja: "稼働時間",
        ko: "가동 시간"
      }, "运行时长"),
      daemonSources: textByLanguage(language, {
        "zh-CN": "源文件 URL 数",
        "zh-TW": "來源檔 URL 數",
        en: "Source URLs",
        ja: "ソースURL数",
        ko: "소스 URL 수"
      }, "源文件 URL 数"),
      daemonLastReport: textByLanguage(language, {
        "zh-CN": "最近报告",
        "zh-TW": "最近報告",
        en: "Latest report",
        ja: "最新レポート",
        ko: "최근 리포트"
      }, "最近报告"),
      daemonLastDaily: textByLanguage(language, {
        "zh-CN": "最近日报",
        "zh-TW": "最近日報",
        en: "Latest daily",
        ja: "最新日次",
        ko: "최근 일일 요약"
      }, "最近日报"),
      daemonLogTail: textByLanguage(language, {
        "zh-CN": "最近日志",
        "zh-TW": "最近日誌",
        en: "Recent Logs",
        ja: "直近ログ",
        ko: "최근 로그"
      }, "最近日志"),
      wechatAgentTitle: textByLanguage(language, {
        "zh-CN": "微信 PC 全自动 Agent",
        "zh-TW": "微信 PC 全自動 Agent",
        en: "WeChat PC Full-Auto Agent",
        ja: "WeChat PC 全自動 Agent",
        ko: "WeChat PC 풀오토 Agent"
      }, "微信 PC 全自动 Agent"),
      wechatAgentHint: textByLanguage(language, {
        "zh-CN": "自动点击公众号列表并截图 OCR 入库。需给 Terminal/IDE 开启辅助功能和屏幕录制权限。",
        "zh-TW": "自動點擊公眾號列表並截圖 OCR 入庫。需為 Terminal/IDE 開啟輔助功能與螢幕錄製權限。",
        en: "Auto clicks OA list and ingests via screenshot OCR. Requires Accessibility + Screen Recording permissions.",
        ja: "公式アカウント一覧を自動クリックし、スクリーンショットOCRで取り込みます。Accessibility / 画面収録権限が必要です。",
        ko: "공식계정 목록을 자동 클릭하고 스크린샷 OCR로 수집합니다. 접근성/화면 녹화 권한이 필요합니다."
      }, "自动点击公众号列表并截图 OCR 入库。需给 Terminal/IDE 开启辅助功能和屏幕录制权限。"),
      wechatAgentStart: textByLanguage(language, {
        "zh-CN": "启动微信 Agent",
        "zh-TW": "啟動微信 Agent",
        en: "Start WeChat Agent",
        ja: "WeChat Agent 開始",
        ko: "WeChat Agent 시작"
      }, "启动微信 Agent"),
      wechatAgentStop: textByLanguage(language, {
        "zh-CN": "停止微信 Agent",
        "zh-TW": "停止微信 Agent",
        en: "Stop WeChat Agent",
        ja: "WeChat Agent 停止",
        ko: "WeChat Agent 중지"
      }, "停止微信 Agent"),
      wechatAgentRunOnce: textByLanguage(language, {
        "zh-CN": "单轮扫描",
        "zh-TW": "單輪掃描",
        en: "Run Single Cycle",
        ja: "単発スキャン",
        ko: "1회 스캔"
      }, "单轮扫描"),
      wechatAgentBatchTitle: textByLanguage(language, {
        "zh-CN": "最近一轮分段批处理",
        "zh-TW": "最近一輪分段批處理",
        en: "Latest Segmented Batch",
        ja: "直近の分割バッチ",
        ko: "최근 분할 배치"
      }, "最近一轮分段批处理"),
      wechatAgentBatchRunning: textByLanguage(language, {
        "zh-CN": "正在走 URL-first 采集",
        "zh-TW": "正在走 URL-first 採集",
        en: "Running URL-first collection",
        ja: "URL-first 収集中",
        ko: "URL-first 수집 중"
      }, "正在走 URL-first 采集"),
      wechatAgentBatchLatest: textByLanguage(language, {
        "zh-CN": "最近一轮采集结果",
        "zh-TW": "最近一輪採集結果",
        en: "Latest collection result",
        ja: "直近の収集結果",
        ko: "최근 수집 결과"
      }, "最近一轮采集结果"),
      wechatAgentBatchSubmitted: textByLanguage(language, {
        "zh-CN": "累计入队",
        "zh-TW": "累計入隊",
        en: "Queued",
        ja: "投入済み",
        ko: "누적 투입"
      }, "累计入队"),
      wechatAgentBatchSegments: textByLanguage(language, {
        "zh-CN": "段",
        "zh-TW": "段",
        en: "segments",
        ja: "区間",
        ko: "구간"
      }, "段"),
      wechatAgentBatchSubmittedNew: textByLanguage(language, {
        "zh-CN": "真正新增",
        "zh-TW": "真正新增",
        en: "New",
        ja: "新規",
        ko: "신규"
      }, "真正新增"),
      wechatAgentBatchSubmittedUrl: textByLanguage(language, {
        "zh-CN": "链接入队",
        "zh-TW": "連結入隊",
        en: "URL ingest",
        ja: "URL投入",
        ko: "URL 수집"
      }, "链接入队"),
      wechatAgentBatchUrlDirect: textByLanguage(language, {
        "zh-CN": "直接真链",
        "zh-TW": "直接真鏈",
        en: "Direct URL",
        ja: "直接URL",
        ko: "직접 URL"
      }, "直接真链"),
      wechatAgentBatchUrlShareCopy: textByLanguage(language, {
        "zh-CN": "分享取链",
        "zh-TW": "分享取鏈",
        en: "Share/Copy",
        ja: "共有コピー",
        ko: "공유/복사"
      }, "分享取链"),
      wechatAgentBatchUrlResolved: textByLanguage(language, {
        "zh-CN": "真链恢复",
        "zh-TW": "真鏈恢復",
        en: "Resolved URL",
        ja: "復元URL",
        ko: "복원 URL"
      }, "真链恢复"),
      wechatAgentBatchSubmittedOcr: textByLanguage(language, {
        "zh-CN": "OCR兜底",
        "zh-TW": "OCR兜底",
        en: "OCR fallback",
        ja: "OCRフォールバック",
        ko: "OCR 폴백"
      }, "OCR兜底"),
      wechatAgentBatchDedup: textByLanguage(language, {
        "zh-CN": "历史去重",
        "zh-TW": "歷史去重",
        en: "Deduplicated",
        ja: "既存重複",
        ko: "중복"
      }, "历史去重"),
      wechatAgentBatchSeen: textByLanguage(language, {
        "zh-CN": "已跳过",
        "zh-TW": "已跳過",
        en: "Skipped",
        ja: "スキップ",
        ko: "건너뜀"
      }, "已跳过"),
      wechatAgentBatchFailed: textByLanguage(language, {
        "zh-CN": "失败",
        "zh-TW": "失敗",
        en: "Failed",
        ja: "失敗",
        ko: "실패"
      }, "失败"),
      wechatAgentBatchMessage: textByLanguage(language, {
        "zh-CN": "最近状态",
        "zh-TW": "最近狀態",
        en: "Latest status",
        ja: "最新状態",
        ko: "최근 상태"
      }, "最近状态"),
      itemsUnit: textByLanguage(language, {
        "zh-CN": "条",
        "zh-TW": "條",
        en: "items",
        ja: "件",
        ko: "건"
      }, "条"),
      wechatAgentHashes: textByLanguage(language, {
        "zh-CN": "去重哈希数",
        "zh-TW": "去重雜湊數",
        en: "Dedup Hashes",
        ja: "重複除外ハッシュ数",
        ko: "중복제거 해시 수"
      }, "去重哈希数"),
      wechatAgentLastCycle: textByLanguage(language, {
        "zh-CN": "最近扫描",
        "zh-TW": "最近掃描",
        en: "Last Cycle",
        ja: "最新スキャン",
        ko: "최근 스캔"
      }, "最近扫描"),
      wechatAgentRunOncePid: textByLanguage(language, {
        "zh-CN": "单轮 PID",
        "zh-TW": "單輪 PID",
        en: "Run-Once PID",
        ja: "単発 PID",
        ko: "단일 실행 PID"
      }, "单轮 PID"),
      wechatAgentCycleSubmitted: textByLanguage(language, {
        "zh-CN": "最近提交",
        "zh-TW": "最近提交",
        en: "Last Submitted",
        ja: "直近送信数",
        ko: "최근 제출"
      }, "最近提交"),
      wechatAgentCycleFailed: textByLanguage(language, {
        "zh-CN": "最近失败",
        "zh-TW": "最近失敗",
        en: "Last Failed",
        ja: "直近失敗数",
        ko: "최근 실패"
      }, "最近失败"),
      wechatAgentCycleSkippedSeen: textByLanguage(language, {
        "zh-CN": "最近去重跳过",
        "zh-TW": "最近去重跳過",
        en: "Last Dedup Skipped",
        ja: "直近重複スキップ",
        ko: "최근 중복 스킵"
      }, "最近去重跳过"),
      wechatAgentCycleLowQuality: textByLanguage(language, {
        "zh-CN": "最近低质量跳过",
        "zh-TW": "最近低品質跳過",
        en: "Last Low-Quality Skipped",
        ja: "直近低品質スキップ",
        ko: "최근 저품질 스킵"
      }, "最近低质量跳过"),
      wechatAgentCycleError: textByLanguage(language, {
        "zh-CN": "最近错误",
        "zh-TW": "最近錯誤",
        en: "Last Error",
        ja: "直近エラー",
        ko: "최근 오류"
      }, "最近错误"),
      wechatAgentHealthCheck: textByLanguage(language, {
        "zh-CN": "健康检查",
        "zh-TW": "健康檢查",
        en: "Health Check",
        ja: "ヘルスチェック",
        ko: "상태 점검"
      }, "健康检查"),
      wechatAgentSelfHeal: textByLanguage(language, {
        "zh-CN": "一键修复",
        "zh-TW": "一鍵修復",
        en: "Self Heal",
        ja: "自動修復",
        ko: "자동 복구"
      }, "一键修复"),
      wechatAgentHealthHealthy: textByLanguage(language, {
        "zh-CN": "健康",
        "zh-TW": "健康",
        en: "Healthy",
        ja: "正常",
        ko: "정상"
      }, "健康"),
      wechatAgentHealthUnhealthy: textByLanguage(language, {
        "zh-CN": "异常",
        "zh-TW": "異常",
        en: "Unhealthy",
        ja: "異常",
        ko: "이상"
      }, "异常"),
      wechatAgentHealthReasons: textByLanguage(language, {
        "zh-CN": "异常原因",
        "zh-TW": "異常原因",
        en: "Reasons",
        ja: "理由",
        ko: "사유"
      }, "异常原因"),
      wechatAgentHealthCheckedAt: textByLanguage(language, {
        "zh-CN": "检查时间",
        "zh-TW": "檢查時間",
        en: "Checked At",
        ja: "確認時刻",
        ko: "확인 시각"
      }, "检查时间"),
      wechatAgentConfigTitle: textByLanguage(language, {
        "zh-CN": "微信 Agent 坐标配置",
        "zh-TW": "微信 Agent 座標配置",
        en: "WeChat Agent Coordinates",
        ja: "WeChat Agent 座標設定",
        ko: "WeChat Agent 좌표 설정"
      }, "微信 Agent 坐标配置"),
      wechatAgentConfigRows: textByLanguage(language, {
        "zh-CN": "每批行数",
        "zh-TW": "每批行數",
        en: "Rows/Batch",
        ja: "行数/バッチ",
        ko: "배치당 행수"
      }, "每批行数"),
      wechatAgentConfigBatches: textByLanguage(language, {
        "zh-CN": "每轮批次",
        "zh-TW": "每輪批次",
        en: "Batches/Cycle",
        ja: "バッチ/サイクル",
        ko: "사이클당 배치"
      }, "每轮批次"),
      wechatAgentConfigRowHeight: textByLanguage(language, {
        "zh-CN": "行高",
        "zh-TW": "行高",
        en: "Row Height",
        ja: "行の高さ",
        ko: "행 높이"
      }, "行高"),
      wechatAgentConfigListOrigin: textByLanguage(language, {
        "zh-CN": "列表原点",
        "zh-TW": "列表原點",
        en: "List Origin",
        ja: "一覧原点",
        ko: "목록 원점"
      }, "列表原点"),
      wechatAgentConfigCapture: textByLanguage(language, {
        "zh-CN": "截图区域",
        "zh-TW": "截圖區域",
        en: "Capture Rect",
        ja: "キャプチャ領域",
        ko: "캡처 영역"
      }, "截图区域"),
      wechatAgentConfigInterval: textByLanguage(language, {
        "zh-CN": "循环间隔（秒）",
        "zh-TW": "循環間隔（秒）",
        en: "Loop Interval (sec)",
        ja: "ループ間隔（秒）",
        ko: "루프 간격(초)"
      }, "循环间隔（秒）"),
      wechatAgentConfigHealthStale: textByLanguage(language, {
        "zh-CN": "健康阈值（分钟）",
        "zh-TW": "健康閾值（分鐘）",
        en: "Health Stale (min)",
        ja: "ヘルス閾値（分）",
        ko: "건강 임계값(분)"
      }, "健康阈值（分钟）"),
      wechatAgentConfigMinFileSize: textByLanguage(language, {
        "zh-CN": "最小截图体积 (KB)",
        "zh-TW": "最小截圖大小 (KB)",
        en: "Min Capture Size (KB)",
        ja: "最小キャプチャサイズ (KB)",
        ko: "최소 캡처 크기 (KB)"
      }, "最小截图体积 (KB)"),
      wechatAgentConfigSave: textByLanguage(language, {
        "zh-CN": "保存配置",
        "zh-TW": "儲存配置",
        en: "Save Config",
        ja: "設定を保存",
        ko: "설정 저장"
      }, "保存配置"),
      wechatAgentPreviewCapture: textByLanguage(language, {
        "zh-CN": "截图校准预览",
        "zh-TW": "截圖校準預覽",
        en: "Capture Preview",
        ja: "キャプチャ校正プレビュー",
        ko: "캡처 보정 미리보기"
      }, "截图校准预览"),
      wechatAgentPreviewOCR: textByLanguage(language, {
        "zh-CN": "OCR 质量预览",
        "zh-TW": "OCR 品質預覽",
        en: "OCR Preview",
        ja: "OCR 品質プレビュー",
        ko: "OCR 품질 미리보기"
      }, "OCR 质量预览"),
      wechatAgentPreviewImage: textByLanguage(language, {
        "zh-CN": "预览截图",
        "zh-TW": "預覽截圖",
        en: "Preview Image",
        ja: "プレビュー画像",
        ko: "미리보기 이미지"
      }, "预览截图"),
      wechatAgentPreviewSize: textByLanguage(language, {
        "zh-CN": "截图体积",
        "zh-TW": "截圖大小",
        en: "Capture Size",
        ja: "キャプチャサイズ",
        ko: "캡처 크기"
      }, "截图体积"),
      wechatAgentPreviewResult: textByLanguage(language, {
        "zh-CN": "OCR 识别预览",
        "zh-TW": "OCR 識別預覽",
        en: "OCR Result",
        ja: "OCR 結果",
        ko: "OCR 결과"
      }, "OCR 识别预览"),
      wechatAgentPreviewQuality: textByLanguage(language, {
        "zh-CN": "质量判定",
        "zh-TW": "品質判定",
        en: "Quality",
        ja: "品質判定",
        ko: "품질 판정"
      }, "质量判定"),
      wechatAgentPreviewPass: textByLanguage(language, {
        "zh-CN": "通过",
        "zh-TW": "通過",
        en: "Pass",
        ja: "合格",
        ko: "통과"
      }, "通过"),
      wechatAgentPreviewFail: textByLanguage(language, {
        "zh-CN": "不通过",
        "zh-TW": "不通過",
        en: "Fail",
        ja: "不合格",
        ko: "실패"
      }, "不通过"),
      wechatAgentPreviewReason: textByLanguage(language, {
        "zh-CN": "原因",
        "zh-TW": "原因",
        en: "Reason",
        ja: "理由",
        ko: "사유"
      }, "原因"),
      wechatAgentPreviewKeywords: textByLanguage(language, {
        "zh-CN": "关键词",
        "zh-TW": "關鍵詞",
        en: "Keywords",
        ja: "キーワード",
        ko: "키워드"
      }, "关键词"),
      total: t(language, "common.items", textByLanguage(language, {
        "zh-CN": "总数",
        "zh-TW": "總數",
        en: "Total",
        ja: "合計",
        ko: "총계"
      }, "总数")),
      ready: t(language, "status.ready", "已完成"),
      processing: t(language, "status.processing", "处理中"),
      failed: t(language, "status.failed", "失败"),
      ocrItems: textByLanguage(language, {
        "zh-CN": "OCR入库数",
        "zh-TW": "OCR入庫數",
        en: "OCR Intake",
        ja: "OCR取り込み数",
        ko: "OCR 수집 수"
      }, "OCR入库数"),
      openDetail: t(language, "action.open_detail", "Open Detail"),
      noResult: textByLanguage(language, {
        "zh-CN": "暂无 OCR 结果，上传截图后会展示结构化摘要。",
        "zh-TW": "暫無 OCR 結果，上傳截圖後會展示結構化摘要。",
        en: "No OCR result yet. Upload a screenshot to generate structured summary.",
        ja: "OCR結果はまだありません。画像アップロード後に構造化要約を表示します。",
        ko: "아직 OCR 결과가 없습니다. 스크린샷 업로드 후 구조화 요약이 표시됩니다."
      }, "暂无 OCR 结果，上传截图后会展示结构化摘要."),
      localMock: textByLanguage(language, {
        "zh-CN": "后端未连接，当前是本地状态演示",
        "zh-TW": "後端未連線，當前是本地狀態演示",
        en: "Backend unavailable, currently showing local demo status",
        ja: "バックエンド未接続のためローカル状態を表示中",
        ko: "백엔드 미연결: 로컬 데모 상태 표시 중"
      }, "后端未连接，当前是本地状态演示"),
      flushPending: textByLanguage(language, {
        "zh-CN": "补偿 Pending",
        "zh-TW": "補償 Pending",
        en: "Flush Pending",
        ja: "Pending補完",
        ko: "Pending 보정"
      }, "补偿 Pending"),
      retryFailed: textByLanguage(language, {
        "zh-CN": "重试 Failed",
        "zh-TW": "重試 Failed",
        en: "Retry Failed",
        ja: "Failed再試行",
        ko: "Failed 재시도"
      }, "重试 Failed"),
      generateDaily: textByLanguage(language, {
        "zh-CN": "生成日报",
        "zh-TW": "生成日報",
        en: "Generate Daily",
        ja: "日次生成",
        ko: "일일 생성"
      }, "生成日报"),
      failedTitle: textByLanguage(language, {
        "zh-CN": "失败列表",
        "zh-TW": "失敗列表",
        en: "Failed Items",
        ja: "失敗一覧",
        ko: "실패 목록"
      }, "失败列表"),
      noFailed: textByLanguage(language, {
        "zh-CN": "当前没有失败项",
        "zh-TW": "目前沒有失敗項",
        en: "No failed items",
        ja: "失敗項目なし",
        ko: "실패 항목 없음"
      }, "当前没有失败项"),
      dailyTitle: textByLanguage(language, {
        "zh-CN": "日报 Markdown",
        "zh-TW": "日報 Markdown",
        en: "Daily Markdown",
        ja: "日次Markdown",
        ko: "일일 Markdown"
      }, "日报 Markdown"),
      copyMarkdown: textByLanguage(language, {
        "zh-CN": "复制",
        "zh-TW": "複製",
        en: "Copy",
        ja: "コピー",
        ko: "복사"
      }, "复制"),
      markdownPlaceholder: textByLanguage(language, {
        "zh-CN": "点击“生成日报”后显示导出内容",
        "zh-TW": "點擊「生成日報」後顯示導出內容",
        en: "Generated markdown will appear here",
        ja: "生成後ここに表示されます",
        ko: "생성 후 여기에 표시됩니다"
      }, "点击“生成日报”后显示导出内容"),
      copied: textByLanguage(language, {
        "zh-CN": "Markdown 已复制",
        "zh-TW": "Markdown 已複製",
        en: "Markdown copied",
        ja: "Markdownをコピーしました",
        ko: "Markdown 복사 완료"
      }, "Markdown 已复制"),
      sourceManagerTitle: textByLanguage(language, {
        "zh-CN": "采集源管理",
        "zh-TW": "採集源管理",
        en: "Source Manager",
        ja: "ソース管理",
        ko: "소스 관리"
      }, "采集源管理"),
      rssFeedTitle: textByLanguage(language, {
        "zh-CN": "RSS 同步源",
        "zh-TW": "RSS 同步源",
        en: "RSS Feed Sources",
        ja: "RSS フィード",
        ko: "RSS 피드"
      }, "RSS 同步源"),
      rssFeedInputPlaceholder: "https://example.com/feed.xml",
      rssFeedNamePlaceholder: textByLanguage(language, {
        "zh-CN": "RSS 标题（可选）",
        "zh-TW": "RSS 標題（可選）",
        en: "RSS title (optional)",
        ja: "RSS タイトル（任意）",
        ko: "RSS 제목 (선택)"
      }, "RSS 标题（可选）"),
      rssFeedAdd: textByLanguage(language, {
        "zh-CN": "新增并同步 RSS",
        "zh-TW": "新增並同步 RSS",
        en: "Add & Sync RSS",
        ja: "追加して同期",
        ko: "RSS 추가 및 동기화"
      }, "新增并同步 RSS"),
      rssFeedSyncAll: textByLanguage(language, {
        "zh-CN": "同步全部 RSS",
        "zh-TW": "同步全部 RSS",
        en: "Sync All RSS",
        ja: "すべて同期",
        ko: "전체 RSS 동기화"
      }, "同步全部 RSS"),
      rssFeedLatest: textByLanguage(language, {
        "zh-CN": "最近 RSS 同步",
        "zh-TW": "最近 RSS 同步",
        en: "Latest RSS Sync",
        ja: "最新 RSS 同期",
        ko: "최근 RSS 동기화"
      }, "最近 RSS 同步"),
      rssFeedEmpty: textByLanguage(language, {
        "zh-CN": "还没有 RSS 同步源。",
        "zh-TW": "還沒有 RSS 同步源。",
        en: "No RSS feeds yet.",
        ja: "RSS フィードはまだありません。",
        ko: "RSS 피드가 아직 없습니다."
      }, "还没有 RSS 同步源。"),
      sourceInputPlaceholder: "https://mp.weixin.qq.com/s/...",
      sourceNotePlaceholder: textByLanguage(language, {
        "zh-CN": "备注（可选）",
        "zh-TW": "備註（可選）",
        en: "Note (optional)",
        ja: "メモ（任意）",
        ko: "메모 (선택)"
      }, "备注（可选）"),
      addSource: textByLanguage(language, {
        "zh-CN": "添加源",
        "zh-TW": "添加來源",
        en: "Add Source",
        ja: "ソース追加",
        ko: "소스 추가"
      }, "添加源"),
      batchSourceTitle: textByLanguage(language, {
        "zh-CN": "批量导入源（每行一个 URL）",
        "zh-TW": "批量導入來源（每行一個 URL）",
        en: "Batch Sources (one URL per line)",
        ja: "一括ソース追加（1行1URL）",
        ko: "소스 일괄 추가 (줄당 URL)"
      }, "批量导入源"),
      importSources: textByLanguage(language, {
        "zh-CN": "批量导入",
        "zh-TW": "批量導入",
        en: "Import",
        ja: "一括追加",
        ko: "일괄 추가"
      }, "批量导入"),
      sourceListTitle: textByLanguage(language, {
        "zh-CN": "当前采集源",
        "zh-TW": "當前採集來源",
        en: "Current Sources",
        ja: "現在のソース",
        ko: "현재 소스"
      }, "当前采集源"),
      noSources: textByLanguage(language, {
        "zh-CN": "暂无采集源",
        "zh-TW": "暫無採集來源",
        en: "No source yet",
        ja: "ソースなし",
        ko: "소스 없음"
      }, "暂无采集源"),
      sourceEnabled: textByLanguage(language, {
        "zh-CN": "启用",
        "zh-TW": "啟用",
        en: "Enabled",
        ja: "有効",
        ko: "활성"
      }, "启用"),
      sourceDisabled: textByLanguage(language, {
        "zh-CN": "停用",
        "zh-TW": "停用",
        en: "Disabled",
        ja: "無効",
        ko: "비활성"
      }, "停用"),
      sourceToggle: textByLanguage(language, {
        "zh-CN": "切换",
        "zh-TW": "切換",
        en: "Toggle",
        ja: "切替",
        ko: "전환"
      }, "切换"),
      sourceDelete: textByLanguage(language, {
        "zh-CN": "删除",
        "zh-TW": "刪除",
        en: "Delete",
        ja: "削除",
        ko: "삭제"
      }, "删除"),
      sourceRecognized: textByLanguage(language, {
        "zh-CN": "识别 URL",
        "zh-TW": "識別 URL",
        en: "URLs",
        ja: "URL数",
        ko: "URL 수"
      }, "识别 URL")
    };

    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      i18n
    });
    wx.setNavigationBarTitle({
      title: textByLanguage(language, {
        "zh-CN": "OCR采集器",
        "zh-TW": "OCR採集器",
        en: "OCR Collector",
        ja: "OCR収集",
        ko: "OCR 수집기"
      }, "OCR采集器")
    });
  },

  refreshCollectorStatus() {
    return Promise.all([
      getCollectorStatus(),
      listCollectorFailed(8),
      listCollectorSources(80),
      listCollectorFeedSources("rss"),
      getCollectorDaemonStatus(),
      getWechatAgentStatus(),
      getWechatAgentBatchStatus(),
      getWechatAgentHealth(),
      getWechatAgentConfig()
    ])
      .then(([status, failed, sources, feeds, daemon, wechatAgent, wechatAgentBatch, wechatAgentHealth, wechatAgentConfig]) => {
        this.setData({
          collectorStatus: status,
          daemonStatus: daemon,
          daemonUptimeLabel: formatDuration(daemon && daemon.uptime_seconds),
          daemonLastReportLabel: formatTs(daemon && daemon.last_report_at),
          daemonLastDailyLabel: formatTs(daemon && daemon.last_daily_summary_at),
          daemonLogText: Array.isArray(daemon && daemon.log_tail) && daemon.log_tail.length
            ? daemon.log_tail.join("\n")
            : "-",
          wechatAgentStatus: wechatAgent,
          wechatAgentBatchStatus: wechatAgentBatch || null,
          wechatAgentBatchView: buildBatchStatusView(wechatAgentBatch, this.data.i18n),
          wechatAgentHealth: wechatAgentHealth,
          wechatAgentUptimeLabel: formatDuration(wechatAgent && wechatAgent.uptime_seconds),
          wechatAgentLastCycleLabel: formatTs(wechatAgent && wechatAgent.last_cycle_at),
          wechatAgentLogText: Array.isArray(wechatAgent && wechatAgent.log_tail) && wechatAgent.log_tail.length
            ? wechatAgent.log_tail.join("\n")
            : "-",
          wechatAgentConfig: wechatAgentConfig || null,
          failedItems: failed.items || [],
          collectorSources: sources.items || [],
          collectorFeeds: (feeds.items || []).map((item) => ({
            ...item,
            last_synced_at_display: formatTs(item.last_synced_at)
          })),
          message: status._fromMock ? this.data.i18n.localMock : this.data.message
        });
      })
      .catch(() => {
        // keep ui available
      });
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: (res) => {
        const filePath = (((res || {}).tempFiles || [])[0] || {}).tempFilePath || "";
        if (!filePath) return;
        this.setData({
          filePath,
          imagePreview: filePath,
          message: ""
        });
      }
    });
  },

  onSourceUrlInput(e) {
    this.setData({ sourceUrl: e.detail.value });
  },

  onTitleHintInput(e) {
    this.setData({ titleHint: e.detail.value });
  },

  onSourceManagerInput(e) {
    this.setData({ sourceManagerInput: e.detail.value });
  },

  onRssFeedInput(e) {
    const field = e.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [field]: e.detail.value });
  },

  onBatchSourceInput(e) {
    const value = e.detail.value;
    this.setData({
      batchSourceInput: value,
      batchSourceCount: parseUrls(value).length
    });
  },

  addRssFeedSource() {
    const sourceUrl = (this.data.rssFeedInput || "").trim();
    if (!sourceUrl) return;
    this.setData({ addingFeed: true, message: "", latestFeedSyncSummary: "" });
    createCollectorRssSource({
      source_url: sourceUrl,
      title: (this.data.rssFeedTitleInput || "").trim() || undefined,
      pull_immediately: true,
      output_language: getApp().globalData.preferences.language
    })
      .then(() =>
        pullCollectorRssFeeds({
          limit: 8,
          output_language: getApp().globalData.preferences.language
        })
      )
      .then((res) => {
        const latest = Array.isArray(res.results) ? res.results[0] : null;
        this.setData({
          rssFeedInput: "",
          rssFeedTitleInput: "",
          latestFeedSyncSummary: latest
            ? `${latest.feed_title}：新增 ${latest.new_items}，去重 ${latest.deduplicated_items}，跳过 ${latest.skipped_items}`
            : "RSS 已创建。",
          message: "RSS 已创建并完成同步。"
        });
        return this.refreshCollectorStatus();
      })
      .catch(() => {
        this.setData({ message: "RSS 创建或同步失败，请检查地址。" });
      })
      .finally(() => {
        this.setData({ addingFeed: false });
      });
  },

  syncRssFeeds() {
    this.setData({ syncingFeeds: true, latestFeedSyncSummary: "", message: "" });
    pullCollectorRssFeeds({
      limit: 8,
      output_language: getApp().globalData.preferences.language
    })
      .then((res) => {
        const latest = Array.isArray(res.results) ? res.results[0] : null;
        this.setData({
          latestFeedSyncSummary: latest
            ? `${latest.feed_title}：新增 ${latest.new_items}，去重 ${latest.deduplicated_items}，跳过 ${latest.skipped_items}`
            : "RSS 同步完成。"
        });
        return this.refreshCollectorStatus();
      })
      .catch(() => {
        this.setData({ latestFeedSyncSummary: "RSS 同步失败，请稍后重试。" });
      })
      .finally(() => {
        this.setData({ syncingFeeds: false });
      });
  },

  submitOCR() {
    if (!this.data.filePath) {
      wx.showToast({
        title: textByLanguage(getApp().globalData.preferences.language, {
          "zh-CN": "请先选择截图",
          "zh-TW": "請先選擇截圖",
          en: "Choose an image first",
          ja: "先に画像を選択してください",
          ko: "먼저 이미지를 선택하세요"
        }, "请先选择截图"),
        icon: "none"
      });
      return;
    }
    this.setData({ submitting: true, message: "" });
    ingestOCRImage({
      filePath: this.data.filePath,
      source_url: (this.data.sourceUrl || "").trim() || undefined,
      title_hint: (this.data.titleHint || "").trim() || undefined,
      output_language: getApp().globalData.preferences.language,
      deduplicate: true
    })
      .then((res) => {
        this.setData({
          resultItem: res.item || null,
          message: `${res.ocr_provider || "ocr"} / conf=${res.ocr_confidence || 0}`
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `OCR submit failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ submitting: false });
      });
  },

  startDaemon() {
    this.setData({ startingDaemon: true, message: "" });
    startCollectorDaemon()
      .then((res) => {
        this.setData({
          daemonStatus: res.status || null,
          daemonOutput: (res.output || "").slice(-2400),
          daemonAction: res.action || "start",
          daemonLogText: Array.isArray(res && res.status && res.status.log_tail) && res.status.log_tail.length
            ? res.status.log_tail.join("\n")
            : this.data.daemonLogText,
          message: res.message || "collector start requested"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `start daemon failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ startingDaemon: false });
      });
  },

  stopDaemon() {
    this.setData({ stoppingDaemon: true, message: "" });
    stopCollectorDaemon()
      .then((res) => {
        this.setData({
          daemonStatus: res.status || null,
          daemonOutput: (res.output || "").slice(-2400),
          daemonAction: res.action || "stop",
          daemonLogText: Array.isArray(res && res.status && res.status.log_tail) && res.status.log_tail.length
            ? res.status.log_tail.join("\n")
            : this.data.daemonLogText,
          message: res.message || "collector stop requested"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `stop daemon failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ stoppingDaemon: false });
      });
  },

  runDaemonOnce() {
    this.setData({ runningDaemonOnce: true, message: "" });
    runCollectorDaemonOnce({
      output_language: getApp().globalData.preferences.language,
      max_collect_per_cycle: 30
    })
      .then((res) => {
        this.setData({
          daemonStatus: res.status || null,
          daemonOutput: (res.output || "").slice(-2400),
          daemonAction: res.action || "run_once",
          daemonLogText: Array.isArray(res && res.status && res.status.log_tail) && res.status.log_tail.length
            ? res.status.log_tail.join("\n")
            : this.data.daemonLogText,
          message: res.message || "collector cycle completed"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `run daemon once failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ runningDaemonOnce: false });
      });
  },

  startWechatAgent() {
    this.setData({ startingWechatAgent: true, message: "" });
    startWechatAgent()
      .then((res) => {
        this.setData({
          wechatAgentStatus: res.status || null,
          wechatAgentOutput: (res.output || "").slice(-2400),
          wechatAgentAction: res.action || "start",
          wechatAgentLogText: Array.isArray(res && res.status && res.status.log_tail) && res.status.log_tail.length
            ? res.status.log_tail.join("\n")
            : this.data.wechatAgentLogText,
          message: res.message || "wechat agent start requested"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `start wechat agent failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ startingWechatAgent: false });
      });
  },

  stopWechatAgent() {
    this.setData({ stoppingWechatAgent: true, message: "" });
    stopWechatAgent()
      .then((res) => {
        this.setData({
          wechatAgentStatus: res.status || null,
          wechatAgentOutput: (res.output || "").slice(-2400),
          wechatAgentAction: res.action || "stop",
          wechatAgentLogText: Array.isArray(res && res.status && res.status.log_tail) && res.status.log_tail.length
            ? res.status.log_tail.join("\n")
            : this.data.wechatAgentLogText,
          message: res.message || "wechat agent stop requested"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `stop wechat agent failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ stoppingWechatAgent: false });
      });
  },

  runWechatAgentOnce() {
    this.setData({ runningWechatAgentOnce: true, message: "" });
    runWechatAgentOnce({
      output_language: getApp().globalData.preferences.language,
      max_items: 12,
      wait: false
    })
      .then((res) => {
        this.setData({
          wechatAgentStatus: res.status || null,
          wechatAgentOutput: (res.output || "").slice(-2400),
          wechatAgentAction: res.action || "run_once",
          wechatAgentLogText: Array.isArray(res && res.status && res.status.log_tail) && res.status.log_tail.length
            ? res.status.log_tail.join("\n")
            : this.data.wechatAgentLogText,
          message: res.message || "wechat agent cycle completed"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `run wechat agent once failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ runningWechatAgentOnce: false });
      });
  },

  checkWechatAgentHealth() {
    this.setData({ checkingWechatAgentHealth: true, message: "" });
    getWechatAgentHealth({
      stale_minutes: this.data.wechatAgentConfig && this.data.wechatAgentConfig.health_stale_minutes
        ? this.data.wechatAgentConfig.health_stale_minutes
        : undefined
    })
      .then((res) => {
        this.setData({
          wechatAgentHealth: res || null,
          wechatAgentStatus: res && res.status ? res.status : this.data.wechatAgentStatus,
          message: `wechat health=${res && res.healthy ? "ok" : "bad"} reasons=${res && res.reasons ? res.reasons.join(",") : "-"}`
        });
      })
      .catch((err) => {
        this.setData({
          message: `wechat health check failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ checkingWechatAgentHealth: false });
      });
  },

  selfHealWechatAgent() {
    this.setData({ healingWechatAgent: true, message: "" });
    runWechatAgentSelfHeal()
      .then((res) => {
        this.setData({
          wechatAgentHealth: res && res.health_after ? res.health_after : this.data.wechatAgentHealth,
          wechatAgentStatus:
            res && res.health_after && res.health_after.status
              ? res.health_after.status
              : this.data.wechatAgentStatus,
          wechatAgentOutput: (res && res.output ? res.output : "").slice(-2400),
          message: (res && res.message) || "wechat self-heal completed"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `wechat self-heal failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ healingWechatAgent: false });
      });
  },

  previewWechatCapture() {
    this.setData({ capturingWechatPreview: true, message: "" });
    getWechatAgentCapturePreview()
      .then((res) => {
        const mimeType = res && res.mime_type ? res.mime_type : "image/png";
        const imageBase64 = res && res.image_base64 ? res.image_base64 : "";
        const previewImage = imageBase64 ? `data:${mimeType};base64,${imageBase64}` : "";
        this.setData({
          wechatAgentCapturePreview: res || null,
          wechatAgentCaptureImage: previewImage,
          message: `${this.data.i18n.wechatAgentPreviewSize}: ${formatBytes(res && res.image_size_bytes)}`
        });
      })
      .catch((err) => {
        this.setData({
          message: `wechat capture preview failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ capturingWechatPreview: false });
      });
  },

  previewWechatOCR() {
    this.setData({ runningWechatOCRPreview: true, message: "" });
    getWechatAgentOCRPreview({
      output_language: getApp().globalData.preferences.language
    })
      .then((res) => {
        const confidence = Number(res && res.confidence ? res.confidence : 0);
        this.setData({
          wechatAgentOCRPreview: res || null,
          message: `${this.data.i18n.wechatAgentPreviewResult}: ${(res && res.provider) || "-"}, conf=${confidence.toFixed(3)}`
        });
      })
      .catch((err) => {
        this.setData({
          message: `wechat ocr preview failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ runningWechatOCRPreview: false });
      });
  },

  onWechatAgentConfigInput(e) {
    const field = (e.currentTarget.dataset && e.currentTarget.dataset.field) || "";
    const value = Number.parseInt(e.detail.value || "0", 10);
    if (!field) return;
    if (Number.isNaN(value)) return;
    const current = this.data.wechatAgentConfig || {};
    if (field.startsWith("list_origin.")) {
      const key = field.split(".")[1];
      this.setData({
        wechatAgentConfig: {
          ...current,
          list_origin: {
            ...(current.list_origin || {}),
            [key]: value
          }
        }
      });
      return;
    }
    if (field.startsWith("article_capture_region.")) {
      const key = field.split(".")[1];
      this.setData({
        wechatAgentConfig: {
          ...current,
          article_capture_region: {
            ...(current.article_capture_region || {}),
            [key]: value
          }
        }
      });
      return;
    }
    this.setData({
      wechatAgentConfig: {
        ...current,
        [field]: value
      }
    });
  },

  saveWechatAgentConfig() {
    const payload = this.data.wechatAgentConfig;
    if (!payload) return;
    this.setData({ savingWechatAgentConfig: true, message: "" });
    updateWechatAgentConfig(payload)
      .then((res) => {
        this.setData({
          wechatAgentConfig: res || payload,
          message: "wechat agent config saved"
        });
      })
      .catch((err) => {
        this.setData({
          message: `save wechat config failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ savingWechatAgentConfig: false });
      });
  },

  flushPending() {
    this.setData({ processingPending: true, message: "" });
    processCollectorPending(80)
      .then((res) => {
        this.setData({
          message: `pending scanned=${res.scanned}, processed=${res.processed}, failed=${res.failed}, remaining=${res.remaining_pending}`
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `flush pending failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ processingPending: false });
      });
  },

  retryFailed() {
    this.setData({ retryingFailed: true, message: "" });
    retryCollectorFailed(30)
      .then((res) => {
        this.setData({
          message: `retry scanned=${res.scanned}, ready=${res.ready}, failed=${res.failed}`
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `retry failed failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ retryingFailed: false });
      });
  },

  generateDaily() {
    this.setData({ generatingDaily: true, message: "" });
    getCollectorDailySummary(24, 12)
      .then((res) => {
        this.setData({
          dailyMarkdown: res.markdown || "",
          message: `daily total=${res.total_ingested}, ready=${res.ready_count}, failed=${res.failed_count}`
        });
      })
      .catch((err) => {
        this.setData({
          message: `daily summary failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ generatingDaily: false });
      });
  },

  copyMarkdown() {
    const text = (this.data.dailyMarkdown || "").trim();
    if (!text) return;
    wx.setClipboardData({
      data: text,
      success: () => {
        this.setData({
          message: this.data.i18n.copied
        });
      }
    });
  },

  addCollectorSource() {
    const sourceUrl = (this.data.sourceManagerInput || "").trim();
    if (!sourceUrl) return;
    this.setData({ addingSource: true, message: "" });
    createCollectorSource({
      source_url: sourceUrl,
      enabled: true
    })
      .then(() => {
        this.setData({
          sourceManagerInput: "",
          message: "source added"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `add source failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ addingSource: false });
      });
  },

  importCollectorSourcesBatch() {
    const urls = parseUrls(this.data.batchSourceInput || "");
    if (!urls.length) return;
    this.setData({ importingSource: true, message: "" });
    importCollectorSources({
      urls,
      enabled: true
    })
      .then((res) => {
        this.setData({
          batchSourceInput: "",
          batchSourceCount: 0,
          message: `source import total=${res.total}, created=${res.created}, exists=${res.exists}, invalid=${res.invalid}`
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `import sources failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ importingSource: false });
      });
  },

  toggleCollectorSource(e) {
    const sourceId = (e.currentTarget.dataset && e.currentTarget.dataset.id) || "";
    if (!sourceId) return;
    const source = (this.data.collectorSources || []).find((row) => row.id === sourceId);
    if (!source) return;
    this.setData({ togglingSourceId: sourceId, message: "" });
    updateCollectorSource(sourceId, {
      enabled: !source.enabled
    })
      .then(() => {
        this.setData({
          message: "source updated"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `toggle source failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ togglingSourceId: "" });
      });
  },

  deleteCollectorSource(e) {
    const sourceId = (e.currentTarget.dataset && e.currentTarget.dataset.id) || "";
    if (!sourceId) return;
    this.setData({ deletingSourceId: sourceId, message: "" });
    deleteCollectorSource(sourceId)
      .then(() => {
        this.setData({
          message: "source deleted"
        });
        this.refreshCollectorStatus();
      })
      .catch((err) => {
        this.setData({
          message: `delete source failed: ${err && err.message ? err.message : "unknown error"}`
        });
      })
      .finally(() => {
        this.setData({ deletingSourceId: "" });
      });
  },

  openItemDetail() {
    const item = this.data.resultItem;
    if (!item || !item.id) return;
    wx.navigateTo({
      url: `/pages/item/index?id=${item.id}`
    });
  }
});
