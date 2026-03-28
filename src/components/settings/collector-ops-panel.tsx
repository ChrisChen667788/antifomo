"use client";

import Link from "next/link";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import {
  getItem,
  getCollectorDaemonStatus,
  getCollectorDailySummary,
  getCollectorStatus,
  getWechatAgentDedupSummary,
  getWechatAgentCapturePreview,
  getWechatAgentBatchStatus,
  getWechatAgentConfig,
  getWechatAgentHealth,
  getWechatAgentOCRPreview,
  getWechatAgentStatus,
  listCollectorFailed,
  processCollectorPending,
  runCollectorDaemonOnce,
  runWechatAgentBatch,
  runWechatAgentOnce,
  retryCollectorFailed,
  resetWechatAgentDedupSummary,
  runWechatAgentSelfHeal,
  startCollectorDaemon,
  startWechatAgent,
  stopCollectorDaemon,
  stopWechatAgent,
  updateWechatAgentConfig,
  type ApiItem,
  type CollectorDaemonStatus,
  type CollectorDailySummary,
  type CollectorFailedItem,
  type CollectorStatus,
  type WechatAgentDedupSummary,
  type WechatAgentConfig,
  type WechatAgentCapturePreview,
  type WechatAgentBatchStatus,
  type WechatAgentHealth,
  type WechatAgentOCRPreview,
  type WechatAgentStatus,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import type { AppLanguage } from "@/lib/preferences";

function pickText(
  language: AppLanguage,
  mapping: Partial<Record<AppLanguage, string>>,
  fallback: string,
): string {
  if (mapping[language]) return mapping[language] as string;
  if (language === "zh-TW" && mapping["zh-CN"]) return mapping["zh-CN"] as string;
  if (mapping.en) return mapping.en as string;
  return fallback;
}

function localText(language: AppLanguage, key: string): string {
  const map: Record<string, Partial<Record<AppLanguage, string>>> = {
    title: {
      "zh-CN": "Collector 运维面板",
      "zh-TW": "Collector 運維面板",
      en: "Collector Ops Panel",
      ja: "Collector 運用パネル",
      ko: "Collector 운영 패널",
    },
    description: {
      "zh-CN": "用于管理采集质量：补偿 pending、重试 failed、生成日报 Markdown。",
      "zh-TW": "用於管理採集品質：補償 pending、重試 failed、生成日報 Markdown。",
      en: "Manage collector quality: flush pending, retry failed, generate daily Markdown.",
      ja: "収集品質管理: pending補完、failed再試行、日次Markdown生成。",
      ko: "수집 품질 관리: pending 보정, failed 재시도, 일일 Markdown 생성.",
    },
    daemonTitle: {
      "zh-CN": "采集器守护进程",
      "zh-TW": "採集器守護進程",
      en: "Collector Daemon",
      ja: "収集デーモン",
      ko: "수집 데몬",
    },
    daemonRunning: {
      "zh-CN": "运行中",
      "zh-TW": "運行中",
      en: "Running",
      ja: "稼働中",
      ko: "실행 중",
    },
    daemonStopped: {
      "zh-CN": "已停止",
      "zh-TW": "已停止",
      en: "Stopped",
      ja: "停止中",
      ko: "중지됨",
    },
    startDaemon: {
      "zh-CN": "启动采集器",
      "zh-TW": "啟動採集器",
      en: "Start",
      ja: "開始",
      ko: "시작",
    },
    stopDaemon: {
      "zh-CN": "停止采集器",
      "zh-TW": "停止採集器",
      en: "Stop",
      ja: "停止",
      ko: "중지",
    },
    runOnce: {
      "zh-CN": "执行单轮采集",
      "zh-TW": "執行單輪採集",
      en: "Run Once",
      ja: "単発実行",
      ko: "1회 실행",
    },
    daemonPid: {
      "zh-CN": "进程 PID",
      "zh-TW": "進程 PID",
      en: "PID",
      ja: "PID",
      ko: "PID",
    },
    daemonUptime: {
      "zh-CN": "运行时长",
      "zh-TW": "運行時長",
      en: "Uptime",
      ja: "稼働時間",
      ko: "가동 시간",
    },
    daemonSources: {
      "zh-CN": "源文件 URL 数",
      "zh-TW": "來源檔 URL 數",
      en: "Source URLs",
      ja: "ソースURL数",
      ko: "소스 URL 수",
    },
    daemonLastReport: {
      "zh-CN": "最近报告",
      "zh-TW": "最近報告",
      en: "Latest report",
      ja: "最新レポート",
      ko: "최근 리포트",
    },
    daemonLastDaily: {
      "zh-CN": "最近日报",
      "zh-TW": "最近日報",
      en: "Latest daily summary",
      ja: "最新日次",
      ko: "최근 일일 요약",
    },
    daemonLogTail: {
      "zh-CN": "最近日志",
      "zh-TW": "最近日誌",
      en: "Recent logs",
      ja: "直近ログ",
      ko: "최근 로그",
    },
    daemonOutput: {
      "zh-CN": "执行输出",
      "zh-TW": "執行輸出",
      en: "Command output",
      ja: "実行出力",
      ko: "실행 출력",
    },
    wechatAgentTitle: {
      "zh-CN": "微信 PC 全自动 Agent",
      "zh-TW": "微信 PC 全自動 Agent",
      en: "WeChat PC Full-Auto Agent",
      ja: "WeChat PC 全自動 Agent",
      ko: "WeChat PC 풀오토 Agent",
    },
    wechatAgentHint: {
      "zh-CN": "自动点击公众号列表，优先提取真链并入库；只有明确开启时才使用 OCR 兜底。连续命中同一篇时会自动加大翻页幅度。需先给 Terminal/IDE 开启辅助功能与屏幕录制权限。",
      "zh-TW": "自動點擊公眾號列表，優先提取真鏈並入庫；只有明確開啟時才使用 OCR 兜底。連續命中同一篇時會自動加大翻頁幅度。需先為 Terminal/IDE 開啟輔助功能與螢幕錄製權限。",
      en: "Auto clicks the OA list, prioritizes real article URLs, and only falls back to OCR when explicitly enabled. Repeated hits on the same article now trigger larger list jumps. Requires Accessibility + Screen Recording permissions.",
      ja: "公式アカウント一覧を自動クリックし、まず実URLの取得を優先し、明示的に有効化した場合のみOCRにフォールバックします。同じ記事を連続で拾った場合は自動で送り幅を広げます。Accessibility と Screen Recording 権限が必要です。",
      ko: "공식계정 목록을 자동 클릭하고 실제 링크 추출을 우선하며, 명시적으로 켠 경우에만 OCR 폴백을 사용합니다. 같은 글이 반복되면 목록 점프 폭을 자동으로 키웁니다. 접근성/화면 녹화 권한이 필요합니다.",
    },
    wechatAgentStart: {
      "zh-CN": "启动微信 Agent",
      "zh-TW": "啟動微信 Agent",
      en: "Start WeChat Agent",
      ja: "WeChat Agent 開始",
      ko: "WeChat Agent 시작",
    },
    wechatAgentStop: {
      "zh-CN": "停止微信 Agent",
      "zh-TW": "停止微信 Agent",
      en: "Stop WeChat Agent",
      ja: "WeChat Agent 停止",
      ko: "WeChat Agent 중지",
    },
    wechatAgentRunOnce: {
      "zh-CN": "单轮扫描",
      "zh-TW": "單輪掃描",
      en: "Run Single Cycle",
      ja: "単発スキャン",
      ko: "1회 스캔",
    },
    wechatAgentRunBatch: {
      "zh-CN": "分段扫描 18 篇",
      "zh-TW": "分段掃描 18 篇",
      en: "Segmented Scan 18",
      ja: "分割スキャン 18",
      ko: "분할 스캔 18",
    },
    wechatAgentBatchTitle: {
      "zh-CN": "最近一轮分段批处理",
      "zh-TW": "最近一輪分段批處理",
      en: "Latest segmented batch",
      ja: "直近の分割バッチ",
      ko: "최근 분할 배치",
    },
    wechatAgentBatchProgress: {
      "zh-CN": "进度",
      "zh-TW": "進度",
      en: "Progress",
      ja: "進捗",
      ko: "진행률",
    },
    wechatAgentBatchSubmittedNew: {
      "zh-CN": "真正新增",
      "zh-TW": "真正新增",
      en: "New",
      ja: "新規",
      ko: "신규",
    },
    wechatAgentBatchDedup: {
      "zh-CN": "历史去重",
      "zh-TW": "歷史去重",
      en: "Deduplicated",
      ja: "既存重複",
      ko: "중복",
    },
    wechatAgentBatchSeen: {
      "zh-CN": "已跳过",
      "zh-TW": "已跳過",
      en: "Skipped",
      ja: "スキップ",
      ko: "스킵",
    },
    wechatAgentBatchFailed: {
      "zh-CN": "失败",
      "zh-TW": "失敗",
      en: "Failed",
      ja: "失敗",
      ko: "실패",
    },
    wechatAgentBatchSubmittedUrl: {
      "zh-CN": "链接入队",
      "zh-TW": "連結入隊",
      en: "URL ingest",
      ja: "URL投入",
      ko: "URL 수집",
    },
    wechatAgentBatchSubmittedOcr: {
      "zh-CN": "OCR兜底",
      "zh-TW": "OCR兜底",
      en: "OCR fallback",
      ja: "OCRフォールバック",
      ko: "OCR 폴백",
    },
    wechatAgentBatchMessage: {
      "zh-CN": "最近状态",
      "zh-TW": "最近狀態",
      en: "Latest status",
      ja: "最新状態",
      ko: "최근 상태",
    },
    wechatAgentBatchItemsTitle: {
      "zh-CN": "本轮新增卡片",
      "zh-TW": "本輪新增卡片",
      en: "New Cards in This Run",
      ja: "今回の新規カード",
      ko: "이번 신규 카드",
    },
    wechatAgentBatchItemsHint: {
      "zh-CN": "与 Session Summary 使用同一组新增卡片，可直接打开详情或回到总结页继续筛选。",
      "zh-TW": "與 Session Summary 使用同一組新增卡片，可直接打開詳情或回到總結頁繼續篩選。",
      en: "This uses the same new-card set as Session Summary. Open detail directly or continue filtering there.",
      ja: "Session Summary と同じ新規カード群です。詳細を開くか、Summary で続けて絞り込めます。",
      ko: "Session Summary와 같은 신규 카드 묶음입니다. 바로 상세를 열거나 Summary에서 계속 필터링할 수 있습니다.",
    },
    wechatAgentBatchOpenSummary: {
      "zh-CN": "回到总结页筛选",
      "zh-TW": "回到總結頁篩選",
      en: "Open Summary Filters",
      ja: "Summary で絞り込む",
      ko: "Summary에서 필터링",
    },
    wechatAgentBatchOpenItem: {
      "zh-CN": "打开详情",
      "zh-TW": "打開詳情",
      en: "Open Detail",
      ja: "詳細を開く",
      ko: "상세 열기",
    },
    untitled: {
      "zh-CN": "未命名内容",
      "zh-TW": "未命名內容",
      en: "Untitled item",
      ja: "無題コンテンツ",
      ko: "제목 없음",
    },
    unknownSource: {
      "zh-CN": "未知来源",
      "zh-TW": "未知來源",
      en: "Unknown source",
      ja: "不明なソース",
      ko: "알 수 없는 출처",
    },
    wechatAgentProcessedHashes: {
      "zh-CN": "已去重哈希数",
      "zh-TW": "已去重雜湊數",
      en: "Dedup Hashes",
      ja: "重複除外ハッシュ数",
      ko: "중복제거 해시 수",
    },
    wechatAgentLastCycle: {
      "zh-CN": "最近扫描",
      "zh-TW": "最近掃描",
      en: "Last Cycle",
      ja: "最新スキャン",
      ko: "최근 스캔",
    },
    wechatAgentRunOncePid: {
      "zh-CN": "单轮 PID",
      "zh-TW": "單輪 PID",
      en: "Run-Once PID",
      ja: "単発 PID",
      ko: "단일 실행 PID",
    },
    wechatAgentCycleSubmitted: {
      "zh-CN": "最近提交",
      "zh-TW": "最近提交",
      en: "Last Submitted",
      ja: "直近送信数",
      ko: "최근 제출",
    },
    wechatAgentCycleFailed: {
      "zh-CN": "最近失败",
      "zh-TW": "最近失敗",
      en: "Last Failed",
      ja: "直近失敗数",
      ko: "최근 실패",
    },
    wechatAgentCycleSkippedSeen: {
      "zh-CN": "最近去重跳过",
      "zh-TW": "最近去重跳過",
      en: "Last Dedup Skipped",
      ja: "直近重複スキップ",
      ko: "최근 중복 스킵",
    },
    wechatAgentCycleLowQuality: {
      "zh-CN": "最近低质量跳过",
      "zh-TW": "最近低品質跳過",
      en: "Last Low-Quality Skipped",
      ja: "直近低品質スキップ",
      ko: "최근 저품질 스킵",
    },
    wechatAgentCycleError: {
      "zh-CN": "最近错误",
      "zh-TW": "最近錯誤",
      en: "Last Error",
      ja: "直近エラー",
      ko: "최근 오류",
    },
    wechatAgentDedupTitle: {
      "zh-CN": "去重状态",
      "zh-TW": "去重狀態",
      en: "Dedup State",
      ja: "重複除外状態",
      ko: "중복 제거 상태",
    },
    wechatAgentDedupRuns: {
      "zh-CN": "历史轮次",
      "zh-TW": "歷史輪次",
      en: "Run History",
      ja: "実行履歴",
      ko: "실행 이력",
    },
    wechatAgentDedupLastRun: {
      "zh-CN": "最近完成",
      "zh-TW": "最近完成",
      en: "Last Finished",
      ja: "直近完了",
      ko: "최근 완료",
    },
    wechatAgentDedupReset: {
      "zh-CN": "重置去重",
      "zh-TW": "重置去重",
      en: "Reset Dedup",
      ja: "重複除外をリセット",
      ko: "중복 제거 초기화",
    },
    wechatAgentDedupResetHard: {
      "zh-CN": "清空去重+历史",
      "zh-TW": "清空去重+歷史",
      en: "Clear Dedup + Runs",
      ja: "重複除外+履歴を削除",
      ko: "중복 제거+이력 삭제",
    },
    wechatAgentDedupResetHint: {
      "zh-CN": "用于重新验证最新公众号流，避免历史哈希把新一轮测试全部判成已见。",
      "zh-TW": "用於重新驗證最新公眾號流，避免歷史雜湊把新一輪測試全部判成已見。",
      en: "Use this before a fresh regression run so historical hashes do not mark the whole batch as seen.",
      ja: "再回帰前に使用し、過去ハッシュで全件既読判定されるのを防ぎます。",
      ko: "새 회귀 전에 사용해 과거 해시로 전체가 이미 본 항목 처리되는 것을 막습니다.",
    },
    wechatAgentBatchLive: {
      "zh-CN": "段内实时进度",
      "zh-TW": "段內即時進度",
      en: "Live In-Segment Progress",
      ja: "セグメント内リアルタイム進捗",
      ko: "세그먼트 내 실시간 진행",
    },
    wechatAgentBatchLiveCheckpoint: {
      "zh-CN": "最近检查点",
      "zh-TW": "最近檢查點",
      en: "Latest Checkpoint",
      ja: "最新チェックポイント",
      ko: "최근 체크포인트",
    },
    wechatAgentConfigTitle: {
      "zh-CN": "微信 Agent 坐标配置",
      "zh-TW": "微信 Agent 座標配置",
      en: "WeChat Agent Coordinates",
      ja: "WeChat Agent 座標設定",
      ko: "WeChat Agent 좌표 설정",
    },
    wechatAgentConfigSave: {
      "zh-CN": "保存配置",
      "zh-TW": "儲存配置",
      en: "Save Config",
      ja: "設定を保存",
      ko: "설정 저장",
    },
    wechatAgentConfigRows: {
      "zh-CN": "每批行数",
      "zh-TW": "每批行數",
      en: "Rows/Batch",
      ja: "行数/バッチ",
      ko: "배치당 행수",
    },
    wechatAgentConfigBatches: {
      "zh-CN": "每轮批次",
      "zh-TW": "每輪批次",
      en: "Batches/Cycle",
      ja: "バッチ/サイクル",
      ko: "사이클당 배치",
    },
    wechatAgentConfigRowHeight: {
      "zh-CN": "行高",
      "zh-TW": "行高",
      en: "Row Height",
      ja: "行の高さ",
      ko: "행 높이",
    },
    wechatAgentConfigListOrigin: {
      "zh-CN": "列表原点 (x,y)",
      "zh-TW": "列表原點 (x,y)",
      en: "List Origin (x,y)",
      ja: "一覧原点 (x,y)",
      ko: "목록 원점 (x,y)",
    },
    wechatAgentConfigCapture: {
      "zh-CN": "截图区域 (x,y,w,h)",
      "zh-TW": "截圖區域 (x,y,w,h)",
      en: "Capture Rect (x,y,w,h)",
      ja: "キャプチャ領域 (x,y,w,h)",
      ko: "캡처 영역 (x,y,w,h)",
    },
    wechatAgentConfigProfile: {
      "zh-CN": "链接提取策略",
      "zh-TW": "連結提取策略",
      en: "Link Extraction Profile",
      ja: "リンク抽出プロファイル",
      ko: "링크 추출 프로필",
    },
    wechatAgentConfigProfileHint: {
      "zh-CN": "auto 会先试内置热点模板；manual 仅使用下方自定义热点和菜单偏移。",
      "zh-TW": "auto 會先試內建熱點模板；manual 僅使用下方自訂熱點與選單偏移。",
      en: "auto tries built-in hotspot templates first; manual uses only the custom hotspot and menu offsets below.",
      ja: "auto は内蔵ホットスポットを優先し、manual は下のカスタム点だけを使います。",
      ko: "auto는 내장 핫스팟 템플릿을 우선 사용하고, manual은 아래 사용자 정의 점만 사용합니다.",
    },
    wechatAgentConfigProfileAuto: {
      "zh-CN": "自动",
      "zh-TW": "自動",
      en: "Auto",
      ja: "自動",
      ko: "자동",
    },
    wechatAgentConfigProfileCompact: {
      "zh-CN": "紧凑窗口",
      "zh-TW": "緊湊視窗",
      en: "Compact Window",
      ja: "コンパクト",
      ko: "콤팩트 창",
    },
    wechatAgentConfigProfileStandard: {
      "zh-CN": "标准窗口",
      "zh-TW": "標準視窗",
      en: "Standard Window",
      ja: "標準",
      ko: "표준 창",
    },
    wechatAgentConfigProfileWide: {
      "zh-CN": "宽窗口",
      "zh-TW": "寬視窗",
      en: "Wide Window",
      ja: "ワイド",
      ko: "와이드 창",
    },
    wechatAgentConfigProfileManual: {
      "zh-CN": "仅自定义热点",
      "zh-TW": "僅自訂熱點",
      en: "Manual Hotspots Only",
      ja: "カスタムのみ",
      ko: "사용자 정의만",
    },
    wechatAgentConfigHotspots: {
      "zh-CN": "分享热点 (右边距:上边距)",
      "zh-TW": "分享熱點 (右邊距:上邊距)",
      en: "Share Hotspots (right:top)",
      ja: "共有ホットスポット (右余白:上余白)",
      ko: "공유 핫스팟 (오른쪽:위)",
    },
    wechatAgentConfigMenuOffsets: {
      "zh-CN": "菜单候选偏移 (dx:dy)",
      "zh-TW": "選單候選偏移 (dx:dy)",
      en: "Menu Offsets (dx:dy)",
      ja: "メニュー候補オフセット (dx:dy)",
      ko: "메뉴 후보 오프셋 (dx:dy)",
    },
    wechatAgentConfigHotspotsHint: {
      "zh-CN": "文章页右上角分享/打开浏览器热点，多个点用逗号分隔。",
      "zh-TW": "文章頁右上角分享/開啟瀏覽器熱點，多個點用逗號分隔。",
      en: "Article-page share/open-browser hotspots. Separate multiple points with commas.",
      ja: "記事右上の共有/ブラウザ起動ホットスポット。複数点はカンマ区切り。",
      ko: "기사 우측 상단 공유/브라우저 열기 핫스팟. 여러 점은 쉼표로 구분.",
    },
    wechatAgentConfigMenuHint: {
      "zh-CN": "相对分享热点的菜单点击候选，用于复制链接/浏览器打开。",
      "zh-TW": "相對分享熱點的選單候選，用於複製連結/瀏覽器開啟。",
      en: "Relative menu click candidates for copy-link/open-browser.",
      ja: "共有点からの相対メニュー候補。リンクコピー/ブラウザ起動用。",
      ko: "공유 지점 기준 상대 메뉴 후보. 링크 복사/브라우저 열기용.",
    },
    wechatAgentConfigInterval: {
      "zh-CN": "循环间隔 (秒)",
      "zh-TW": "循環間隔 (秒)",
      en: "Loop Interval (sec)",
      ja: "ループ間隔 (秒)",
      ko: "루프 간격 (초)",
    },
    wechatAgentConfigMinFileSize: {
      "zh-CN": "最小截图体积 (KB)",
      "zh-TW": "最小截圖大小 (KB)",
      en: "Min Capture Size (KB)",
      ja: "最小キャプチャサイズ (KB)",
      ko: "최소 캡처 크기 (KB)",
    },
    wechatAgentPreviewCapture: {
      "zh-CN": "截图校准预览",
      "zh-TW": "截圖校準預覽",
      en: "Capture Preview",
      ja: "キャプチャ校正プレビュー",
      ko: "캡처 보정 미리보기",
    },
    wechatAgentPreviewOCR: {
      "zh-CN": "OCR 质量预览",
      "zh-TW": "OCR 品質預覽",
      en: "OCR Preview",
      ja: "OCR 品質プレビュー",
      ko: "OCR 품질 미리보기",
    },
    wechatAgentPreviewImage: {
      "zh-CN": "预览截图",
      "zh-TW": "預覽截圖",
      en: "Preview Image",
      ja: "プレビュー画像",
      ko: "미리보기 이미지",
    },
    wechatAgentPreviewSize: {
      "zh-CN": "截图体积",
      "zh-TW": "截圖大小",
      en: "Capture Size",
      ja: "キャプチャサイズ",
      ko: "캡처 크기",
    },
    wechatAgentPreviewOCRTitle: {
      "zh-CN": "OCR 识别预览",
      "zh-TW": "OCR 識別預覽",
      en: "OCR Result",
      ja: "OCR 結果",
      ko: "OCR 결과",
    },
    wechatAgentPreviewOCRQuality: {
      "zh-CN": "质量判定",
      "zh-TW": "品質判定",
      en: "Quality",
      ja: "品質判定",
      ko: "품질 판정",
    },
    wechatAgentPreviewOCRQualityOK: {
      "zh-CN": "通过",
      "zh-TW": "通過",
      en: "Pass",
      ja: "合格",
      ko: "통과",
    },
    wechatAgentPreviewOCRQualityBad: {
      "zh-CN": "不通过",
      "zh-TW": "不通過",
      en: "Fail",
      ja: "不合格",
      ko: "실패",
    },
    wechatAgentPreviewOCRReason: {
      "zh-CN": "原因",
      "zh-TW": "原因",
      en: "Reason",
      ja: "理由",
      ko: "사유",
    },
    wechatAgentPreviewOCRProvider: {
      "zh-CN": "OCR 提供方",
      "zh-TW": "OCR 來源",
      en: "Provider",
      ja: "OCR プロバイダ",
      ko: "OCR 제공자",
    },
    wechatAgentPreviewOCRBody: {
      "zh-CN": "正文预览",
      "zh-TW": "正文預覽",
      en: "Body Preview",
      ja: "本文プレビュー",
      ko: "본문 미리보기",
    },
    wechatAgentPreviewOCRKeywords: {
      "zh-CN": "关键词",
      "zh-TW": "關鍵詞",
      en: "Keywords",
      ja: "キーワード",
      ko: "키워드",
    },
    wechatAgentHealthCheck: {
      "zh-CN": "健康检查",
      "zh-TW": "健康檢查",
      en: "Health Check",
      ja: "ヘルスチェック",
      ko: "상태 점검",
    },
    wechatAgentSelfHeal: {
      "zh-CN": "一键修复",
      "zh-TW": "一鍵修復",
      en: "Self Heal",
      ja: "自動修復",
      ko: "자동 복구",
    },
    wechatAgentHealthHealthy: {
      "zh-CN": "健康",
      "zh-TW": "健康",
      en: "Healthy",
      ja: "正常",
      ko: "정상",
    },
    wechatAgentHealthUnhealthy: {
      "zh-CN": "异常",
      "zh-TW": "異常",
      en: "Unhealthy",
      ja: "異常",
      ko: "이상",
    },
    wechatAgentHealthReasons: {
      "zh-CN": "异常原因",
      "zh-TW": "異常原因",
      en: "Reasons",
      ja: "理由",
      ko: "사유",
    },
    wechatAgentHealthCheckedAt: {
      "zh-CN": "检查时间",
      "zh-TW": "檢查時間",
      en: "Checked At",
      ja: "確認時刻",
      ko: "확인 시각",
    },
    wechatAgentConfigHealthStale: {
      "zh-CN": "健康阈值 (分钟)",
      "zh-TW": "健康閾值 (分鐘)",
      en: "Health Stale (min)",
      ja: "ヘルス閾値 (分)",
      ko: "건강 임계값 (분)",
    },
    refresh: {
      "zh-CN": "刷新状态",
      "zh-TW": "刷新狀態",
      en: "Refresh",
      ja: "更新",
      ko: "새로고침",
    },
    flushPending: {
      "zh-CN": "补偿 Pending",
      "zh-TW": "補償 Pending",
      en: "Flush Pending",
      ja: "Pending補完",
      ko: "Pending 보정",
    },
    retryFailed: {
      "zh-CN": "重试 Failed",
      "zh-TW": "重試 Failed",
      en: "Retry Failed",
      ja: "Failed再試行",
      ko: "Failed 재시도",
    },
    generateDaily: {
      "zh-CN": "生成日报 Markdown",
      "zh-TW": "生成日報 Markdown",
      en: "Generate Daily Markdown",
      ja: "日次Markdown生成",
      ko: "일일 Markdown 생성",
    },
    copy: {
      "zh-CN": "复制 Markdown",
      "zh-TW": "複製 Markdown",
      en: "Copy Markdown",
      ja: "Markdownをコピー",
      ko: "Markdown 복사",
    },
    statusTitle: {
      "zh-CN": "24h 采集状态",
      "zh-TW": "24h 採集狀態",
      en: "24h Collector Status",
      ja: "24時間ステータス",
      ko: "24시간 수집 상태",
    },
    failedTitle: {
      "zh-CN": "失败列表",
      "zh-TW": "失敗列表",
      en: "Failed Items",
      ja: "失敗一覧",
      ko: "실패 목록",
    },
    failedEmpty: {
      "zh-CN": "当前没有失败项。",
      "zh-TW": "目前沒有失敗項。",
      en: "No failed items.",
      ja: "失敗項目はありません。",
      ko: "실패 항목이 없습니다.",
    },
    dailyTitle: {
      "zh-CN": "日报摘要",
      "zh-TW": "日報摘要",
      en: "Daily Summary",
      ja: "日次サマリー",
      ko: "일일 요약",
    },
    markdownPlaceholder: {
      "zh-CN": "点击“生成日报 Markdown”后显示导出内容。",
      "zh-TW": "點擊「生成日報 Markdown」後顯示導出內容。",
      en: "Generated Markdown will appear here.",
      ja: "生成したMarkdownがここに表示されます。",
      ko: "생성된 Markdown이 여기에 표시됩니다.",
    },
    total: {
      "zh-CN": "总数",
      "zh-TW": "總數",
      en: "Total",
      ja: "合計",
      ko: "총계",
    },
    ready: {
      "zh-CN": "已完成",
      "zh-TW": "已完成",
      en: "Ready",
      ja: "完了",
      ko: "완료",
    },
    pending: {
      "zh-CN": "处理中",
      "zh-TW": "處理中",
      en: "Pending",
      ja: "処理中",
      ko: "처리중",
    },
    failed: {
      "zh-CN": "失败",
      "zh-TW": "失敗",
      en: "Failed",
      ja: "失敗",
      ko: "실패",
    },
    ocr: {
      "zh-CN": "OCR 入库",
      "zh-TW": "OCR 入庫",
      en: "OCR Ingest",
      ja: "OCR取り込み",
      ko: "OCR 수집",
    },
    messageCopied: {
      "zh-CN": "Markdown 已复制到剪贴板。",
      "zh-TW": "Markdown 已複製到剪貼簿。",
      en: "Markdown copied to clipboard.",
      ja: "Markdownをクリップボードにコピーしました。",
      ko: "Markdown이 클립보드에 복사되었습니다.",
    },
    source: {
      "zh-CN": "来源",
      "zh-TW": "來源",
      en: "Source",
      ja: "ソース",
      ko: "출처",
    },
    titleCol: {
      "zh-CN": "标题",
      "zh-TW": "標題",
      en: "Title",
      ja: "タイトル",
      ko: "제목",
    },
    error: {
      "zh-CN": "错误",
      "zh-TW": "錯誤",
      en: "Error",
      ja: "エラー",
      ko: "오류",
    },
  };
  return pickText(language, map[key] || {}, key);
}

function formatTs(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "-";
  const safe = Math.max(0, Math.floor(seconds));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function shortText(value: string | null, maxLength = 96): string {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "-";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const size = Number(value);
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

function formatPointPairs<T extends Record<string, number>>(
  points: T[] | undefined,
  xKey: keyof T,
  yKey: keyof T,
): string {
  if (!Array.isArray(points) || !points.length) return "";
  return points
    .map((point) => `${Number(point[xKey]) || 0}:${Number(point[yKey]) || 0}`)
    .join(", ");
}

function parsePointPairs(
  value: string,
  options: {
    xKey: string;
    yKey: string;
  },
): Array<Record<string, number>> | null {
  const { xKey, yKey } = options;
  const parts = String(value || "")
    .split(/[,\n]+/)
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (!parts.length) return [];
  const parsed: Array<Record<string, number>> = [];
  for (const part of parts) {
    const [xRaw, yRaw] = part.split(":").map((entry) => entry.trim());
    const x = Number.parseInt(xRaw || "", 10);
    const y = Number.parseInt(yRaw || "", 10);
    if (Number.isNaN(x) || Number.isNaN(y)) {
      return null;
    }
    parsed.push({ [xKey]: x, [yKey]: y });
  }
  return parsed;
}

export function CollectorOpsPanel() {
  const { preferences } = useAppPreferences();
  const language = preferences.language;

  const [status, setStatus] = useState<CollectorStatus | null>(null);
  const [daemonStatus, setDaemonStatus] = useState<CollectorDaemonStatus | null>(null);
  const [wechatAgentStatus, setWechatAgentStatus] = useState<WechatAgentStatus | null>(null);
  const [wechatAgentBatchStatus, setWechatAgentBatchStatus] = useState<WechatAgentBatchStatus | null>(null);
  const [wechatAgentHealth, setWechatAgentHealth] = useState<WechatAgentHealth | null>(null);
  const [wechatAgentConfig, setWechatAgentConfig] = useState<WechatAgentConfig | null>(null);
  const [wechatAgentDedupSummary, setWechatAgentDedupSummary] = useState<WechatAgentDedupSummary | null>(null);
  const [wechatAgentBatchItems, setWechatAgentBatchItems] = useState<ApiItem[]>([]);
  const [wechatAgentCapturePreview, setWechatAgentCapturePreview] =
    useState<WechatAgentCapturePreview | null>(null);
  const [wechatAgentOCRPreview, setWechatAgentOCRPreview] = useState<WechatAgentOCRPreview | null>(null);
  const [failedItems, setFailedItems] = useState<CollectorFailedItem[]>([]);
  const [dailySummary, setDailySummary] = useState<CollectorDailySummary | null>(null);
  const [message, setMessage] = useState<string>("");
  const [commandOutput, setCommandOutput] = useState<string>("");
  const [wechatAgentOutput, setWechatAgentOutput] = useState<string>("");
  const [loadingState, setLoadingState] = useState(false);
  const [startingDaemon, setStartingDaemon] = useState(false);
  const [stoppingDaemon, setStoppingDaemon] = useState(false);
  const [runningOnce, setRunningOnce] = useState(false);
  const [startingWechatAgent, setStartingWechatAgent] = useState(false);
  const [stoppingWechatAgent, setStoppingWechatAgent] = useState(false);
  const [runningWechatAgentOnce, setRunningWechatAgentOnce] = useState(false);
  const [runningWechatAgentBatch, setRunningWechatAgentBatch] = useState(false);
  const [checkingWechatAgentHealth, setCheckingWechatAgentHealth] = useState(false);
  const [healingWechatAgent, setHealingWechatAgent] = useState(false);
  const [savingWechatAgentConfig, setSavingWechatAgentConfig] = useState(false);
  const [capturingWechatPreview, setCapturingWechatPreview] = useState(false);
  const [runningWechatOCRPreview, setRunningWechatOCRPreview] = useState(false);
  const [resettingWechatDedup, setResettingWechatDedup] = useState(false);
  const [resettingWechatDedupHard, setResettingWechatDedupHard] = useState(false);
  const [processingPending, setProcessingPending] = useState(false);
  const [retryingFailed, setRetryingFailed] = useState(false);
  const [generatingDaily, setGeneratingDaily] = useState(false);
  const [wechatHotspotsText, setWechatHotspotsText] = useState("");
  const [wechatMenuOffsetsText, setWechatMenuOffsetsText] = useState("");

  const deferredMarkdown = useDeferredValue(dailySummary?.markdown || "");

  const refreshStatus = async () => {
    setLoadingState(true);
    setMessage("");
    try {
      const [statusRes, failedRes, daemonRes, wechatAgentRes, wechatAgentBatchRes, wechatAgentHealthRes, wechatAgentConfigRes, wechatAgentDedupRes] = await Promise.all([
        getCollectorStatus(),
        listCollectorFailed(12),
        getCollectorDaemonStatus(),
        getWechatAgentStatus(),
        getWechatAgentBatchStatus(),
        getWechatAgentHealth(),
        getWechatAgentConfig(),
        getWechatAgentDedupSummary(),
      ]);
      startTransition(() => {
        setStatus(statusRes);
        setFailedItems(failedRes.items || []);
        setDaemonStatus(daemonRes);
        setWechatAgentStatus(wechatAgentRes);
        setWechatAgentBatchStatus(wechatAgentBatchRes);
        setWechatAgentHealth(wechatAgentHealthRes);
        setWechatAgentConfig(wechatAgentConfigRes);
        setWechatAgentDedupSummary(wechatAgentDedupRes);
      });
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setLoadingState(false);
    }
  };

  useEffect(() => {
    void refreshStatus();
  }, []);

  useEffect(() => {
    if (!wechatAgentBatchStatus?.running) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [wechatAgentBatchStatus?.running]);

  useEffect(() => {
    setWechatHotspotsText(
      formatPointPairs(wechatAgentConfig?.article_link_hotspots, "right_inset", "top_offset"),
    );
    setWechatMenuOffsetsText(
      formatPointPairs(wechatAgentConfig?.article_link_menu_offsets, "dx", "dy"),
    );
  }, [wechatAgentConfig]);

  useEffect(() => {
    const itemIds = Array.isArray(wechatAgentBatchStatus?.new_item_ids)
      ? wechatAgentBatchStatus?.new_item_ids.slice(0, 8)
      : [];
    if (!itemIds.length) {
      setWechatAgentBatchItems([]);
      return;
    }

    let cancelled = false;
    const loadBatchItems = async () => {
      try {
        const results = await Promise.all(itemIds.map((itemId) => getItem(itemId)));
        if (!cancelled) {
          startTransition(() => {
            setWechatAgentBatchItems(results);
          });
        }
      } catch {
        if (!cancelled) {
          setWechatAgentBatchItems([]);
        }
      }
    };

    void loadBatchItems();
    return () => {
      cancelled = true;
    };
  }, [wechatAgentBatchStatus?.new_item_ids]);

  const handleFlushPending = async () => {
    setProcessingPending(true);
    try {
      const result = await processCollectorPending(80);
      setMessage(
        `pending scanned=${result.scanned}, processed=${result.processed}, failed=${result.failed}, remaining=${result.remaining_pending}`,
      );
      setCommandOutput("");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setProcessingPending(false);
    }
  };

  const handleRetryFailed = async () => {
    setRetryingFailed(true);
    try {
      const result = await retryCollectorFailed(30);
      setMessage(`retry scanned=${result.scanned}, ready=${result.ready}, failed=${result.failed}`);
      setCommandOutput("");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRetryingFailed(false);
    }
  };

  const handleGenerateDaily = async () => {
    setGeneratingDaily(true);
    try {
      const result = await getCollectorDailySummary(24, 12);
      startTransition(() => {
        setDailySummary(result);
      });
      setMessage(
        `daily generated: total=${result.total_ingested}, ready=${result.ready_count}, failed=${result.failed_count}`,
      );
      setCommandOutput("");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setGeneratingDaily(false);
    }
  };

  const handleStartDaemon = async () => {
    setStartingDaemon(true);
    try {
      const result = await startCollectorDaemon();
      setMessage(result.message);
      setCommandOutput(result.output || "");
      setDaemonStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStartingDaemon(false);
    }
  };

  const handleStopDaemon = async () => {
    setStoppingDaemon(true);
    try {
      const result = await stopCollectorDaemon();
      setMessage(result.message);
      setCommandOutput(result.output || "");
      setDaemonStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStoppingDaemon(false);
    }
  };

  const handleRunOnce = async () => {
    setRunningOnce(true);
    try {
      const result = await runCollectorDaemonOnce({
        output_language: language,
        max_collect_per_cycle: 30,
      });
      setMessage(result.message);
      setCommandOutput(result.output || "");
      setDaemonStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningOnce(false);
    }
  };

  const handleStartWechatAgent = async () => {
    setStartingWechatAgent(true);
    try {
      const result = await startWechatAgent();
      setMessage(result.message);
      setWechatAgentOutput(result.output || "");
      setWechatAgentStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStartingWechatAgent(false);
    }
  };

  const handleStopWechatAgent = async () => {
    setStoppingWechatAgent(true);
    try {
      const result = await stopWechatAgent();
      setMessage(result.message);
      setWechatAgentOutput(result.output || "");
      setWechatAgentStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStoppingWechatAgent(false);
    }
  };

  const handleRunWechatAgentOnce = async () => {
    setRunningWechatAgentOnce(true);
    try {
      const result = await runWechatAgentOnce({
        output_language: language,
        max_items: 12,
        wait: false,
      });
      setMessage(result.message);
      setWechatAgentOutput(result.output || "");
      setWechatAgentStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningWechatAgentOnce(false);
    }
  };

  const handleRunWechatAgentBatch = async () => {
    setRunningWechatAgentBatch(true);
    try {
      const result = await runWechatAgentBatch({
        output_language: language,
        total_items: 18,
        segment_items: 6,
      });
      setMessage(result.message);
      setWechatAgentBatchStatus(result.batch_status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningWechatAgentBatch(false);
    }
  };

  const handleResetWechatDedup = async (clearRuns: boolean) => {
    const confirmed = window.confirm(
      clearRuns
        ? `${localText(language, "wechatAgentDedupResetHard")}？`
        : `${localText(language, "wechatAgentDedupReset")}？`,
    );
    if (!confirmed) {
      return;
    }
    if (clearRuns) {
      setResettingWechatDedupHard(true);
    } else {
      setResettingWechatDedup(true);
    }
    try {
      const result = await resetWechatAgentDedupSummary({ clear_runs: clearRuns });
      setWechatAgentDedupSummary(result);
      setMessage(
        `${clearRuns ? localText(language, "wechatAgentDedupResetHard") : localText(language, "wechatAgentDedupReset")} ok`,
      );
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      if (clearRuns) {
        setResettingWechatDedupHard(false);
      } else {
        setResettingWechatDedup(false);
      }
    }
  };

  const handleCheckWechatAgentHealth = async () => {
    setCheckingWechatAgentHealth(true);
    try {
      const health = await getWechatAgentHealth({
        stale_minutes: wechatAgentConfig?.health_stale_minutes ?? undefined,
      });
      setWechatAgentHealth(health);
      setWechatAgentStatus(health.status);
      setMessage(
        `wechat agent health=${health.healthy ? "ok" : "bad"} reasons=${health.reasons.join(",") || "-"}`,
      );
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setCheckingWechatAgentHealth(false);
    }
  };

  const handleWechatAgentSelfHeal = async () => {
    setHealingWechatAgent(true);
    try {
      const result = await runWechatAgentSelfHeal();
      setWechatAgentOutput(result.output || "");
      setWechatAgentHealth(result.health_after);
      setWechatAgentStatus(result.health_after.status);
      setMessage(result.message);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setHealingWechatAgent(false);
    }
  };

  const handleWechatPreviewCapture = async () => {
    setCapturingWechatPreview(true);
    try {
      const preview = await getWechatAgentCapturePreview();
      setWechatAgentCapturePreview(preview);
      setMessage(
        `${localText(language, "wechatAgentPreviewImage")}: ${preview.region.width}x${preview.region.height}, ${formatBytes(preview.image_size_bytes)}`,
      );
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setCapturingWechatPreview(false);
    }
  };

  const handleWechatPreviewOCR = async () => {
    setRunningWechatOCRPreview(true);
    try {
      const preview = await getWechatAgentOCRPreview({ output_language: language });
      setWechatAgentOCRPreview(preview);
      setMessage(
        `${localText(language, "wechatAgentPreviewOCRTitle")}: ${preview.provider}, conf=${preview.confidence.toFixed(3)}`,
      );
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningWechatOCRPreview(false);
    }
  };

  const handleSaveWechatAgentConfig = async () => {
    if (!wechatAgentConfig) return;
    setSavingWechatAgentConfig(true);
    try {
      const parsedHotspots = parsePointPairs(wechatHotspotsText, {
        xKey: "right_inset",
        yKey: "top_offset",
      });
      const parsedMenuOffsets = parsePointPairs(wechatMenuOffsetsText, {
        xKey: "dx",
        yKey: "dy",
      });
      if (!parsedHotspots || !parsedMenuOffsets) {
        throw new Error(localText(language, "wechatAgentConfigMenuHint"));
      }
      const saved = await updateWechatAgentConfig({
        ...wechatAgentConfig,
        article_link_profile: wechatAgentConfig.article_link_profile,
        article_link_hotspots: parsedHotspots as WechatAgentConfig["article_link_hotspots"],
        article_link_menu_offsets: parsedMenuOffsets as WechatAgentConfig["article_link_menu_offsets"],
      });
      setWechatAgentConfig(saved);
      setMessage("wechat agent config saved");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setSavingWechatAgentConfig(false);
    }
  };

  const handleCopyMarkdown = async () => {
    if (!deferredMarkdown) return;
    try {
      await navigator.clipboard.writeText(deferredMarkdown);
      setMessage(localText(language, "messageCopied"));
    } catch {
      setMessage("copy failed");
    }
  };

  const updateWechatAgentIntField = (
    key:
      | "rows_per_batch"
      | "batches_per_cycle"
      | "article_row_height"
      | "min_capture_file_size_kb"
      | "loop_interval_sec"
      | "health_stale_minutes",
    value: string,
  ) => {
    setWechatAgentConfig((prev) => {
      if (!prev) return prev;
      const parsed = Number.parseInt(value, 10);
      if (Number.isNaN(parsed)) return prev;
      return { ...prev, [key]: parsed };
    });
  };

  const batchProgress =
    wechatAgentBatchStatus && wechatAgentBatchStatus.total_segments > 0
      ? wechatAgentBatchStatus.running
        ? Math.max(
            8,
            Math.min(
              96,
              Math.round(
                (Math.max(wechatAgentBatchStatus.current_segment_index, 1) /
                  wechatAgentBatchStatus.total_segments) *
                  100,
              ),
            ),
          )
        : wechatAgentBatchStatus.finished_at
          ? 100
          : 0
        : 0;
  const submittedUrlDirect = Math.max(
    wechatAgentBatchStatus?.submitted_url_direct || 0,
    wechatAgentBatchStatus?.live_report_submitted_url_direct || 0,
  );
  const submittedUrlShareCopy = Math.max(
    wechatAgentBatchStatus?.submitted_url_share_copy || 0,
    wechatAgentBatchStatus?.live_report_submitted_url_share_copy || 0,
  );
  const submittedUrlResolved = Math.max(
    wechatAgentBatchStatus?.submitted_url_resolved || 0,
    wechatAgentBatchStatus?.live_report_submitted_url_resolved || 0,
  );

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <p className="af-kicker">{localText(language, "title")}</p>
      <p className="mt-2 text-sm text-slate-500">{localText(language, "description")}</p>

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        <p className="text-sm font-semibold text-slate-800">{localText(language, "daemonTitle")}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
              daemonStatus?.running
                ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border border-slate-200 bg-slate-100 text-slate-600"
            }`}
          >
            {daemonStatus?.running
              ? localText(language, "daemonRunning")
              : localText(language, "daemonStopped")}
          </span>
          <button
            type="button"
            onClick={() => void handleStartDaemon()}
            disabled={startingDaemon}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {startingDaemon ? "..." : localText(language, "startDaemon")}
          </button>
          <button
            type="button"
            onClick={() => void handleStopDaemon()}
            disabled={stoppingDaemon}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {stoppingDaemon ? "..." : localText(language, "stopDaemon")}
          </button>
          <button
            type="button"
            onClick={() => void handleRunOnce()}
            disabled={runningOnce}
            className="af-btn af-btn-primary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningOnce ? "..." : localText(language, "runOnce")}
          </button>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <StatCard label={localText(language, "daemonPid")} value={String(daemonStatus?.pid ?? "-")} />
          <StatCard label={localText(language, "daemonUptime")} value={formatDuration(daemonStatus?.uptime_seconds ?? null)} />
          <StatCard
            label={localText(language, "daemonSources")}
            value={daemonStatus?.source_file_count ?? 0}
          />
          <StatCard
            label={localText(language, "daemonLastReport")}
            value={formatTs(daemonStatus?.last_report_at ?? null)}
          />
          <StatCard
            label={localText(language, "daemonLastDaily")}
            value={formatTs(daemonStatus?.last_daily_summary_at ?? null)}
          />
        </div>

        <p className="mt-2 text-[11px] text-slate-500">{daemonStatus?.log_file || "-"}</p>
        <div className="mt-2 rounded-xl border border-white/80 bg-slate-950 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
            {localText(language, "daemonLogTail")}
          </p>
          <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-200">
            {(daemonStatus?.log_tail || []).join("\n") || "-"}
          </pre>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        <p className="text-sm font-semibold text-slate-800">{localText(language, "wechatAgentTitle")}</p>
        <p className="mt-1 text-xs text-slate-500">{localText(language, "wechatAgentHint")}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
              wechatAgentStatus?.running
                ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border border-slate-200 bg-slate-100 text-slate-600"
            }`}
          >
            {wechatAgentStatus?.running
              ? localText(language, "daemonRunning")
              : localText(language, "daemonStopped")}
          </span>
          <button
            type="button"
            onClick={() => void handleStartWechatAgent()}
            disabled={startingWechatAgent}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {startingWechatAgent ? "..." : localText(language, "wechatAgentStart")}
          </button>
          <button
            type="button"
            onClick={() => void handleStopWechatAgent()}
            disabled={stoppingWechatAgent}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {stoppingWechatAgent ? "..." : localText(language, "wechatAgentStop")}
          </button>
          <button
            type="button"
            onClick={() => void handleRunWechatAgentOnce()}
            disabled={runningWechatAgentOnce}
            className="af-btn af-btn-primary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningWechatAgentOnce ? "..." : localText(language, "wechatAgentRunOnce")}
          </button>
          <button
            type="button"
            onClick={() => void handleRunWechatAgentBatch()}
            disabled={runningWechatAgentBatch}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningWechatAgentBatch ? "..." : localText(language, "wechatAgentRunBatch")}
          </button>
          <button
            type="button"
            onClick={() => void handleCheckWechatAgentHealth()}
            disabled={checkingWechatAgentHealth}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {checkingWechatAgentHealth ? "..." : localText(language, "wechatAgentHealthCheck")}
          </button>
          <button
            type="button"
            onClick={() => void handleWechatAgentSelfHeal()}
            disabled={healingWechatAgent}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {healingWechatAgent ? "..." : localText(language, "wechatAgentSelfHeal")}
          </button>
          <button
            type="button"
            onClick={() => void handleWechatPreviewCapture()}
            disabled={capturingWechatPreview}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {capturingWechatPreview ? "..." : localText(language, "wechatAgentPreviewCapture")}
          </button>
          <button
            type="button"
            onClick={() => void handleWechatPreviewOCR()}
            disabled={runningWechatOCRPreview}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningWechatOCRPreview ? "..." : localText(language, "wechatAgentPreviewOCR")}
          </button>
        </div>

        {wechatAgentHealth ? (
          <div className="mt-2 rounded-xl border border-white/80 bg-white/70 px-3 py-2 text-xs text-slate-600">
            <p className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 ${
                  wechatAgentHealth.healthy
                    ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                {wechatAgentHealth.healthy
                  ? localText(language, "wechatAgentHealthHealthy")
                  : localText(language, "wechatAgentHealthUnhealthy")}
              </span>
              <span>
                {localText(language, "wechatAgentHealthCheckedAt")}: {formatTs(wechatAgentHealth.checked_at)}
              </span>
            </p>
            {!wechatAgentHealth.healthy ? (
              <p className="mt-1 text-amber-700">
                {localText(language, "wechatAgentHealthReasons")}:
                {" "}
                {wechatAgentHealth.reasons.length ? wechatAgentHealth.reasons.join(", ") : "-"}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <StatCard label={localText(language, "daemonPid")} value={String(wechatAgentStatus?.pid ?? "-")} />
          <StatCard label={localText(language, "daemonUptime")} value={formatDuration(wechatAgentStatus?.uptime_seconds ?? null)} />
          <StatCard
            label={localText(language, "wechatAgentProcessedHashes")}
            value={wechatAgentStatus?.processed_hashes ?? 0}
          />
          <StatCard
            label={localText(language, "wechatAgentLastCycle")}
            value={formatTs(wechatAgentStatus?.last_cycle_at ?? null)}
          />
          <StatCard
            label={localText(language, "wechatAgentRunOncePid")}
            value={wechatAgentStatus?.run_once_running ? String(wechatAgentStatus?.run_once_pid ?? "-") : "-"}
          />
          <StatCard
            label={localText(language, "wechatAgentCycleSubmitted")}
            value={wechatAgentStatus?.last_cycle_submitted ?? 0}
          />
          <StatCard
            label={localText(language, "wechatAgentCycleFailed")}
            value={wechatAgentStatus?.last_cycle_failed ?? 0}
          />
          <StatCard
            label={localText(language, "wechatAgentCycleSkippedSeen")}
            value={wechatAgentStatus?.last_cycle_skipped_seen ?? 0}
          />
          <StatCard
            label={localText(language, "wechatAgentCycleLowQuality")}
            value={wechatAgentStatus?.last_cycle_skipped_low_quality ?? 0}
          />
        </div>
        <div className="mt-3 rounded-xl border border-white/80 bg-white/70 p-3 text-xs text-slate-600">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-slate-800">{localText(language, "wechatAgentDedupTitle")}</p>
              <p className="mt-1 text-slate-500">{localText(language, "wechatAgentDedupResetHint")}</p>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => void handleResetWechatDedup(false)}
                disabled={resettingWechatDedup || resettingWechatDedupHard}
                className="rounded-full border border-slate-200 bg-white/85 px-3 py-1 text-slate-700 transition hover:border-slate-300 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resettingWechatDedup ? `${localText(language, "wechatAgentDedupReset")}...` : localText(language, "wechatAgentDedupReset")}
              </button>
              <button
                type="button"
                onClick={() => void handleResetWechatDedup(true)}
                disabled={resettingWechatDedup || resettingWechatDedupHard}
                className="rounded-full border border-amber-200 bg-amber-50/90 px-3 py-1 text-amber-700 transition hover:border-amber-300 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resettingWechatDedupHard ? `${localText(language, "wechatAgentDedupResetHard")}...` : localText(language, "wechatAgentDedupResetHard")}
              </button>
            </div>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <StatCard label={localText(language, "wechatAgentProcessedHashes")} value={wechatAgentDedupSummary?.processed_hashes ?? 0} />
            <StatCard label={localText(language, "wechatAgentDedupRuns")} value={wechatAgentDedupSummary?.run_count ?? 0} />
            <StatCard label={localText(language, "wechatAgentDedupLastRun")} value={formatTs(wechatAgentDedupSummary?.last_run_finished_at ?? null)} />
          </div>
        </div>
        {wechatAgentBatchStatus ? (
          <div className="mt-3 rounded-xl border border-white/80 bg-white/70 p-3 text-xs text-slate-600">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-slate-800">
                  {localText(language, "wechatAgentBatchTitle")}
                </p>
                <p className="mt-1 text-slate-500">
                  {localText(language, "wechatAgentBatchProgress")}: {batchProgress}% ·
                  {" "}
                  {wechatAgentBatchStatus.current_segment_index}/{Math.max(
                    wechatAgentBatchStatus.total_segments,
                    1,
                  )}
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 ${
                  wechatAgentBatchStatus.running
                    ? "border border-sky-200 bg-sky-50 text-sky-700"
                    : "border border-slate-200 bg-slate-100 text-slate-600"
                }`}
              >
                {wechatAgentBatchStatus.running
                  ? localText(language, "daemonRunning")
                  : localText(language, "daemonStopped")}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-cyan-400 transition-all duration-500"
                style={{ width: `${batchProgress}%` }}
              />
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
              <StatCard label={localText(language, "wechatAgentBatchSubmittedNew")} value={wechatAgentBatchStatus.submitted_new} />
              <StatCard label={localText(language, "wechatAgentBatchSubmittedUrl")} value={wechatAgentBatchStatus.submitted_url} />
              <StatCard label={localText(language, "wechatAgentBatchSubmittedOcr")} value={wechatAgentBatchStatus.submitted_ocr} />
              <StatCard label={localText(language, "wechatAgentBatchDedup")} value={wechatAgentBatchStatus.deduplicated_existing} />
              <StatCard label={localText(language, "wechatAgentBatchSeen")} value={wechatAgentBatchStatus.skipped_seen} />
              <StatCard label={localText(language, "wechatAgentBatchFailed")} value={wechatAgentBatchStatus.failed} />
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <StatCard
                label={localText(language, "focus.collectorUrlDirect")}
                value={submittedUrlDirect}
              />
              <StatCard
                label={localText(language, "focus.collectorUrlShareCopy")}
                value={submittedUrlShareCopy}
              />
              <StatCard
                label={localText(language, "focus.collectorUrlResolved")}
                value={submittedUrlResolved}
              />
            </div>
            {(wechatAgentBatchStatus.live_report_batch || wechatAgentBatchStatus.live_report_stage) ? (
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-xs text-slate-600">
                <p className="font-semibold text-slate-800">{localText(language, "wechatAgentBatchLive")}</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-4">
                  <StatCard label="Batch" value={wechatAgentBatchStatus.live_report_batch ?? "-"} />
                  <StatCard label="Row" value={wechatAgentBatchStatus.live_report_row ?? "-"} />
                  <StatCard label="Stage" value={wechatAgentBatchStatus.live_report_stage ?? "-"} />
                  <StatCard label={localText(language, "wechatAgentBatchLiveCheckpoint")} value={formatTs(wechatAgentBatchStatus.live_report_checkpoint_at ?? null)} />
                </div>
                {wechatAgentBatchStatus.live_report_detail ? (
                  <p className="mt-2 text-slate-500">{shortText(wechatAgentBatchStatus.live_report_detail, 180)}</p>
                ) : null}
              </div>
            ) : null}
            {wechatAgentBatchStatus.last_message ? (
              <p className="mt-2 text-slate-500">
                {localText(language, "wechatAgentBatchMessage")}: {shortText(wechatAgentBatchStatus.last_message, 180)}
              </p>
            ) : null}
            {wechatAgentBatchStatus.last_error ? (
              <p className="mt-1 text-amber-700">
                {localText(language, "wechatAgentCycleError")}: {shortText(wechatAgentBatchStatus.last_error, 180)}
              </p>
            ) : null}
            {wechatAgentBatchItems.length ? (
              <div className="mt-4 rounded-2xl border border-white/80 bg-white/72 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      {localText(language, "wechatAgentBatchItemsTitle")}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      {localText(language, "wechatAgentBatchItemsHint")}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href="/session-summary"
                      className="af-btn af-btn-secondary border border-white/80 px-3 py-1.5 text-xs"
                    >
                      <AppIcon name="summary" className="h-3.5 w-3.5" />
                      {localText(language, "wechatAgentBatchOpenSummary")}
                    </Link>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {wechatAgentBatchItems.map((item) => (
                    <article
                      key={item.id}
                      className="rounded-2xl border border-slate-200/80 bg-slate-50/82 p-4 shadow-[0_20px_40px_-34px_rgba(15,23,42,0.35)]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="rounded-full border border-white/80 bg-white/85 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                          {item.source_domain || localText(language, "unknownSource")}
                        </span>
                        <span className="text-[11px] font-medium text-slate-400">
                          {(item.action_suggestion || "later").replace("_", " ")}
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 font-semibold text-sky-700">
                          route · {item.ingest_route || "unknown"}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">
                          body · {item.content_acquisition_status || "pending"}
                        </span>
                        {item.fallback_used ? (
                          <span className="rounded-full bg-amber-50 px-2.5 py-1 font-semibold text-amber-700">
                            fallback
                          </span>
                        ) : null}
                      </div>
                      <h4 className="mt-3 text-sm font-semibold leading-6 text-slate-900">
                        {item.title || localText(language, "untitled")}
                      </h4>
                      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
                        {item.short_summary || item.long_summary || "-"}
                      </p>
                      {item.content_acquisition_note ? (
                        <p className="mt-2 text-xs leading-5 text-slate-500">
                          {item.content_acquisition_note}
                        </p>
                      ) : null}
                      <div className="mt-4">
                        <Link
                          href={`/items/${item.id}`}
                          className="af-btn af-btn-secondary border border-white/80 px-3 py-1.5 text-xs"
                        >
                          <AppIcon name="summary" className="h-3.5 w-3.5" />
                          {localText(language, "wechatAgentBatchOpenItem")}
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
        {wechatAgentStatus?.last_cycle_error ? (
          <p className="mt-2 text-xs text-amber-700">
            {localText(language, "wechatAgentCycleError")}: {shortText(wechatAgentStatus.last_cycle_error, 180)}
          </p>
        ) : null}

        <p className="mt-2 text-[11px] text-slate-500">{wechatAgentStatus?.log_file || "-"}</p>
        <div className="mt-2 rounded-xl border border-white/80 bg-slate-950 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
            {localText(language, "daemonLogTail")}
          </p>
          <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-200">
            {wechatAgentOutput || (wechatAgentStatus?.log_tail || []).join("\n") || "-"}
          </pre>
        </div>

        {wechatAgentCapturePreview ? (
          <div className="mt-3 rounded-xl border border-white/80 bg-white/70 p-3">
            <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
              {localText(language, "wechatAgentPreviewImage")}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {localText(language, "wechatAgentPreviewSize")}: {formatBytes(wechatAgentCapturePreview.image_size_bytes)}
            </p>
            <img
              src={`data:${wechatAgentCapturePreview.mime_type};base64,${wechatAgentCapturePreview.image_base64}`}
              alt="wechat-capture-preview"
              className="mt-2 w-full rounded-lg border border-slate-200 object-cover"
            />
          </div>
        ) : null}

        {wechatAgentOCRPreview ? (
          <div className="mt-3 rounded-xl border border-white/80 bg-white/70 p-3 text-xs text-slate-600">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-800">{localText(language, "wechatAgentPreviewOCRTitle")}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] ${
                  wechatAgentOCRPreview.quality_ok
                    ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                {localText(language, "wechatAgentPreviewOCRQuality")}:
                {" "}
                {wechatAgentOCRPreview.quality_ok
                  ? localText(language, "wechatAgentPreviewOCRQualityOK")
                  : localText(language, "wechatAgentPreviewOCRQualityBad")}
              </span>
            </div>
            <p className="mt-2">
              {localText(language, "wechatAgentPreviewOCRProvider")}: {wechatAgentOCRPreview.provider}
              {" · "}
              conf={wechatAgentOCRPreview.confidence.toFixed(3)}
              {" · "}
              len={wechatAgentOCRPreview.text_length}
            </p>
            {wechatAgentOCRPreview.quality_reason ? (
              <p className="mt-1 text-amber-700">
                {localText(language, "wechatAgentPreviewOCRReason")}: {wechatAgentOCRPreview.quality_reason}
              </p>
            ) : null}
            <p className="mt-2 font-semibold text-slate-800">{shortText(wechatAgentOCRPreview.title, 140)}</p>
            <p className="mt-2 whitespace-pre-wrap leading-6 text-slate-700">
              {shortText(wechatAgentOCRPreview.body_preview, 480)}
            </p>
            <p className="mt-2 text-slate-500">
              {localText(language, "wechatAgentPreviewOCRKeywords")}:
              {" "}
              {wechatAgentOCRPreview.keywords.length ? wechatAgentOCRPreview.keywords.join(", ") : "-"}
            </p>
          </div>
        ) : null}
      </div>

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        <p className="text-sm font-semibold text-slate-800">
          {localText(language, "wechatAgentConfigTitle")}
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigProfile")}
            <select
              value={wechatAgentConfig?.article_link_profile ?? "auto"}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        article_link_profile: event.target.value as WechatAgentConfig["article_link_profile"],
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            >
              <option value="auto">{localText(language, "wechatAgentConfigProfileAuto")}</option>
              <option value="compact">{localText(language, "wechatAgentConfigProfileCompact")}</option>
              <option value="standard">{localText(language, "wechatAgentConfigProfileStandard")}</option>
              <option value="wide">{localText(language, "wechatAgentConfigProfileWide")}</option>
              <option value="manual">{localText(language, "wechatAgentConfigProfileManual")}</option>
            </select>
            <span className="text-[11px] text-slate-400">
              {localText(language, "wechatAgentConfigProfileHint")}
            </span>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigRows")}
            <input
              type="number"
              value={wechatAgentConfig?.rows_per_batch ?? ""}
              onChange={(event) => updateWechatAgentIntField("rows_per_batch", event.target.value)}
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigBatches")}
            <input
              type="number"
              value={wechatAgentConfig?.batches_per_cycle ?? ""}
              onChange={(event) => updateWechatAgentIntField("batches_per_cycle", event.target.value)}
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigRowHeight")}
            <input
              type="number"
              value={wechatAgentConfig?.article_row_height ?? ""}
              onChange={(event) => updateWechatAgentIntField("article_row_height", event.target.value)}
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigMinFileSize")}
            <input
              type="number"
              value={wechatAgentConfig?.min_capture_file_size_kb ?? ""}
              onChange={(event) => updateWechatAgentIntField("min_capture_file_size_kb", event.target.value)}
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigInterval")}
            <input
              type="number"
              value={wechatAgentConfig?.loop_interval_sec ?? ""}
              onChange={(event) => updateWechatAgentIntField("loop_interval_sec", event.target.value)}
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigHealthStale")}
            <input
              type="number"
              value={wechatAgentConfig?.health_stale_minutes ?? ""}
              onChange={(event) => updateWechatAgentIntField("health_stale_minutes", event.target.value)}
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigListOrigin")} x
            <input
              type="number"
              value={wechatAgentConfig?.list_origin?.x ?? ""}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        list_origin: { ...prev.list_origin, x: Number.parseInt(event.target.value || "0", 10) || 0 },
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigListOrigin")} y
            <input
              type="number"
              value={wechatAgentConfig?.list_origin?.y ?? ""}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        list_origin: { ...prev.list_origin, y: Number.parseInt(event.target.value || "0", 10) || 0 },
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigCapture")} x
            <input
              type="number"
              value={wechatAgentConfig?.article_capture_region?.x ?? ""}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        article_capture_region: {
                          ...prev.article_capture_region,
                          x: Number.parseInt(event.target.value || "0", 10) || 0,
                        },
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigCapture")} y
            <input
              type="number"
              value={wechatAgentConfig?.article_capture_region?.y ?? ""}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        article_capture_region: {
                          ...prev.article_capture_region,
                          y: Number.parseInt(event.target.value || "0", 10) || 0,
                        },
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigCapture")} w
            <input
              type="number"
              value={wechatAgentConfig?.article_capture_region?.width ?? ""}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        article_capture_region: {
                          ...prev.article_capture_region,
                          width: Number.parseInt(event.target.value || "0", 10) || 0,
                        },
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigCapture")} h
            <input
              type="number"
              value={wechatAgentConfig?.article_capture_region?.height ?? ""}
              onChange={(event) =>
                setWechatAgentConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        article_capture_region: {
                          ...prev.article_capture_region,
                          height: Number.parseInt(event.target.value || "0", 10) || 0,
                        },
                      }
                    : prev,
                )
              }
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
          </label>
        </div>
        <div className="mt-3 grid gap-2 lg:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigHotspots")}
            <input
              type="text"
              value={wechatHotspotsText}
              onChange={(event) => setWechatHotspotsText(event.target.value)}
              placeholder="44:26, 84:26, 124:26, 44:58"
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
            <span className="text-[11px] text-slate-400">
              {localText(language, "wechatAgentConfigHotspotsHint")}
            </span>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-600">
            {localText(language, "wechatAgentConfigMenuOffsets")}
            <input
              type="text"
              value={wechatMenuOffsetsText}
              onChange={(event) => setWechatMenuOffsetsText(event.target.value)}
              placeholder="0:42, 0:78, 0:112, -52:78, 52:78"
              className="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            />
            <span className="text-[11px] text-slate-400">
              {localText(language, "wechatAgentConfigMenuHint")}
            </span>
          </label>
        </div>
        <div className="mt-3">
          <button
            type="button"
            onClick={() => void handleSaveWechatAgentConfig()}
            disabled={!wechatAgentConfig || savingWechatAgentConfig}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {savingWechatAgentConfig ? "..." : localText(language, "wechatAgentConfigSave")}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void refreshStatus()}
          disabled={loadingState}
          className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loadingState ? "..." : localText(language, "refresh")}
        </button>
        <button
          type="button"
          onClick={() => void handleFlushPending()}
          disabled={processingPending}
          className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {processingPending ? "..." : localText(language, "flushPending")}
        </button>
        <button
          type="button"
          onClick={() => void handleRetryFailed()}
          disabled={retryingFailed}
          className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {retryingFailed ? "..." : localText(language, "retryFailed")}
        </button>
        <button
          type="button"
          onClick={() => void handleGenerateDaily()}
          disabled={generatingDaily}
          className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {generatingDaily ? "..." : localText(language, "generateDaily")}
        </button>
      </div>

      {message ? <p className="mt-3 text-xs text-slate-500">{message}</p> : null}
      {commandOutput ? (
        <div className="mt-2 rounded-xl border border-white/80 bg-slate-950 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
            {localText(language, "daemonOutput")}
          </p>
          <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-200">
            {commandOutput}
          </pre>
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        <p className="text-sm font-semibold text-slate-800">{localText(language, "statusTitle")}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label={localText(language, "total")} value={status?.last_24h_total ?? 0} />
          <StatCard label={localText(language, "ready")} value={status?.last_24h_ready ?? 0} />
          <StatCard label={localText(language, "pending")} value={status?.last_24h_processing ?? 0} />
          <StatCard label={localText(language, "failed")} value={status?.last_24h_failed ?? 0} />
          <StatCard label={localText(language, "ocr")} value={status?.last_24h_ocr_items ?? 0} />
        </div>
        <p className="mt-2 text-xs text-slate-500">{formatTs(status?.latest_item_at || null)}</p>
      </div>

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        <p className="text-sm font-semibold text-slate-800">{localText(language, "failedTitle")}</p>
        {failedItems.length ? (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-xs text-slate-600">
              <thead>
                <tr className="text-slate-500">
                  <th className="px-2 py-1">{localText(language, "titleCol")}</th>
                  <th className="px-2 py-1">{localText(language, "source")}</th>
                  <th className="px-2 py-1">{localText(language, "error")}</th>
                </tr>
              </thead>
              <tbody>
                {failedItems.slice(0, 12).map((item) => (
                  <tr key={item.id} className="border-t border-white/75">
                    <td className="px-2 py-2">{shortText(item.title, 60)}</td>
                    <td className="px-2 py-2">{item.source_domain || "-"}</td>
                    <td className="px-2 py-2">{shortText(item.processing_error, 84)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-2 text-xs text-slate-500">{localText(language, "failedEmpty")}</p>
        )}
      </div>

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold text-slate-800">{localText(language, "dailyTitle")}</p>
          <button
            type="button"
            onClick={() => void handleCopyMarkdown()}
            disabled={!deferredMarkdown}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {localText(language, "copy")}
          </button>
        </div>
        <textarea
          readOnly
          rows={12}
          value={deferredMarkdown || localText(language, "markdownPlaceholder")}
          className="mt-3 w-full rounded-2xl border border-white/85 bg-white/70 px-4 py-3 font-mono text-xs leading-6 text-slate-700 outline-none"
        />
      </div>
    </section>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-xl border border-white/75 bg-white/70 px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.15em] text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
