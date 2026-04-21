# Anti-fomo Mini Program Demo

原生微信小程序版本路径：

`/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/miniapp`

## 在微信开发者工具中运行

1. 启动后端（必须，真机预览请确保监听局域网）：

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:backend
```

2. 打开微信开发者工具，选择 **导入项目**。
3. 项目目录选择上面的 `miniapp` 目录。
4. 项目已配置可用 AppID（`wx552c021a9fd2a12b`），也可以替换为你自己的。
5. 在开发者工具中勾选：
   - `详情 -> 本地设置 -> 不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书`
6. 编译后即可看到小程序版 Demo（Feed / Inbox / Saved / Focus / Session Summary）。

## API 地址

- 开发者工具默认可用：`http://127.0.0.1:8000`
- 真机预览必须改成：`http://你的Mac局域网IP:8000`
- 现在可以直接在小程序 `设置 -> 后端连接` 中保存和测试 API 地址，不需要再手动写 Console

## 功能范围（MVP）

- Feed：一屏一张卡片 + like / ignore / save / open_detail
- Inbox：URL / 文本提交 + 处理状态 + 失败重试
- Item：短/长摘要、标签、建议动作、反馈、重新处理
- Focus：25/50 分钟计时 + 目标输入 + 结束回流
- Session Summary：统计 + 导出 Markdown / 稍后读 / 待办草稿
- Saved：筛选/排序 + 详情跳转
- Collector：URL/正文直连优先，截图 OCR 作为补录兜底

## Focus 推荐模式

- Feed 接口支持 `mode=focus` 与 `goal_text` 参数。
- 当你在 Focus 页面启动专注后，Feed 会自动切为 Focus 排序（更偏向目标匹配）。

## 离线重试队列

- 当网络不可用时，反馈操作（like/ignore/save/inaccurate）、重处理、导出任务会进入本地队列。
- 恢复网络后，在 Feed/Inbox/详情页/Session Summary 会自动补发队列请求。

后端不可用时，小程序自动回退到本地 mock，保证可演示。

## OCR 采集入口（新增）

路径：`设置 -> 打开 OCR 采集器`

用途：
1. 手机端选取公众号截图（相册/拍照）
2. 提交到后端 `/api/collector/ocr/ingest`
3. 自动入库为 Item 并触发摘要、标签、建议动作

说明：电脑端常驻采集器在正文不足时会优先走 `/api/collector/url/ingest`，仅在移动端补录时使用 OCR。

状态接口：`/api/collector/status`
运维接口：
- `/api/collector/process-pending`
- `/api/collector/failed`
- `/api/collector/retry-failed`
- `/api/collector/daily-summary`

小程序 OCR 采集器页现在支持：
- 采集源管理（新增 / 批量导入 / 启停 / 删除）
- 守护进程控制（启动 / 停止 / 单轮执行 / 日志尾部）
- 微信 PC 全自动 Agent 运维（启动 / 停止 / 单轮执行 / 日志）
- 补偿 pending
- 重试 failed
- 生成日报 Markdown 并复制

守护进程接口：
- `/api/collector/daemon/status`
- `/api/collector/daemon/start`
- `/api/collector/daemon/stop`
- `/api/collector/daemon/run-once`

微信 PC Agent 接口：
- `/api/collector/wechat-agent/status`
- `/api/collector/wechat-agent/config`
- `/api/collector/wechat-agent/config` (PUT)
- `/api/collector/wechat-agent/health`
- `/api/collector/wechat-agent/self-heal`
- `/api/collector/wechat-agent/start`
- `/api/collector/wechat-agent/stop`
- `/api/collector/wechat-agent/run-once`

说明：
- 小程序无法在后台 24x7 自动浏览微信主 App 的公众号流；
- 建议搭配电脑端常驻采集器（`npm run collector:start`）使用。
