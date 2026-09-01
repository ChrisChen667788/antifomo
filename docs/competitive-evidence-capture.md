# `/competitive` 可复现浏览器证据采集

此工作流服务于 GitHub issue #6 的短演示素材，并为 `2.10.x` 竞品能力台账补足当前的桌面浏览器、移动 CSS 视口和本地浏览器性能证据。它是受限的演示/回归采集，不是生产验收或真机认证。

## 证据边界

- 采集器不会启动、停止、初始化或改写任何服务；开始前必须由操作者单独启动本地前端和后端。
- 默认且唯一支持的是 `preview` 模式。它检查四条只读 preview API（包含 `2.10.3-2.11.7` 迭代台账），并在浏览器中以对应 preview payload 替换持久化台账 GET 响应，所以即使本地开发数据库已初始化，页面也稳定呈现确定性的只读预览。
- 采集器拦截一切非 GET/OPTIONS 的产品策略请求；它不点击“初始化”或任何会写入的控件。
- `mobile_viewport` 是 `390 × 844` 的模拟移动 CSS 视口（`deviceScaleFactor=3`），不是物理手机、平板或云真机截图。
- 桌面采集统一为 `1600 × 1100` CSS 像素；演示 GIF/MP4 由 4 个桌面关键状态按每秒 1 帧组成，目标时长约 4 秒，便于 README 与 release 页面重复生成和快速预览。
- `competitive-browser-performance.json` 记录本地浏览器 Performance API 导航采样；它不是生产压测、服务端 SLA、网络基准或发布放行证据。
- Office、视觉人工验收、真实设备验证、独立竞品验证和 release-readiness 继续各自保持既有门禁，不能由这些素材替代。

## 前置条件

需要本地 Node.js、项目依赖、Chrome/Chromium 和（生成 GIF/MP4 时）`ffmpeg`。脚本不会隐式启动服务，因此先在另一个终端执行：

```bash
npm run demo:start
```

默认假定前端位于 `http://127.0.0.1:3010`，后端位于 `http://127.0.0.1:8000`。启动后确认健康检查：

```bash
curl -fsS http://127.0.0.1:8000/healthz
```

## 采集

```bash
npm run repo:competitive-evidence
```

该命令生成并覆盖经人工挑选后可发布的目录 `docs/assets/competitive-evidence/` 中的以下文件：

- `competitive-preview-desktop-browser.png`
- `competitive-source-matrix-desktop-browser.png`
- `competitive-artifact-gates-desktop-browser.png`
- `competitive-preview-mobile-viewport.png`
- `competitive-artifact-gates-mobile-viewport.png`
- `competitive-iteration-program-desktop-browser.png`
- `competitive-iteration-program-mobile-viewport.png`
- `competitive-preview-demo.gif` 与 `competitive-preview-demo.mp4`
- `competitive-browser-performance.json` 与 `competitive-browser-performance.svg`
- `competitive-evidence-manifest.json`（尺寸、SHA-256、视口、诊断和证据边界）

如果只需要 PNG、性能 JSON/SVG 和 manifest，而当前环境没有 `ffmpeg`：

```bash
npm run repo:competitive-evidence -- --no-motion
```

如本地端口不同：

```bash
npm run repo:competitive-evidence -- \
  --frontend-url http://127.0.0.1:3010 \
  --api-base http://127.0.0.1:8000 \
  --samples 3
```

默认每个视口运行 3 次独立浏览器上下文的导航采样，并写入中位数。`--headful` 仅供操作者在采集时目视检查，不会改变证据语义。

## 发布前人工检查

1. 打开 PNG 与 GIF，确认没有运行时错误、空白关键区域、私有数据或错误的产品声明。
2. 检查 manifest 的 `source_mode=read_only_preview`、`physical_device_capture=false` 和 SHA-256 是否与当前文件一致。
3. 把真实设备截图、Office roundtrip、视觉评审和独立竞品核查分别放入各自的可复核证据链；不要把本工作流标为“真机”或“生产性能”。
4. 仅在人工确认素材可公开后，将 `docs/assets/competitive-evidence/` 提交到 GitHub 和 ModelScope。
