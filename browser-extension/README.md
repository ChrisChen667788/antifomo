# Anti-fomo Browser Extension (Chrome)

路径：

`/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/browser-extension/chrome`

## 功能

- 一键把当前网页发送到 Anti-fomo：`POST /api/items`
- 在 `mp.weixin.qq.com` 页面优先抓取正文、标题、关键词线索，再提交
- payload 使用：
  - `source_type=plugin`
  - `source_url=当前标签页 URL`
  - `title=页面标题（优先正文提取结果）`
  - `raw_content=提取正文（失败时兜底为标题 + URL）`

> 说明：微信 App 本身不支持第三方“插件安装”。本工具的实际方式是：
> 在微信中点“在浏览器打开”公众号文章，然后用浏览器插件一键发送到 Anti-fomo。

## 本地安装（开发者模式）

1. 启动后端：`npm run demo:backend`
2. 打开 Chrome `chrome://extensions/`
3. 打开“开发者模式”
4. 点击“加载已解压的扩展程序”
5. 选择 `browser-extension/chrome`

## 使用

1. 在浏览器打开公众号文章页面（`mp.weixin.qq.com`）
2. 点击插件图标
3. 确认“正文提取”显示成功，且“提交时附带正文（推荐）”已勾选
4. 确认 `API Base`（默认 `http://127.0.0.1:8000`）
5. 点击“发送到 Inbox”
6. 打开 Web Feed（`http://localhost:3000`）或 Inbox 查看处理状态

通用网页也支持使用：
- 若正文提取失败，插件会回退为只提交标题与 URL
- 这时建议在 Inbox 手动粘贴正文，保证摘要质量

## 快速验证（建议）

1. 打开任意公众号文章页面
2. 确认 `API Base`（默认 `http://127.0.0.1:8000`）
3. 点击“发送到 Inbox”
4. 在 Feed 卡片确认出现：
   - 可读标题（不是 URL）
   - 标签（关键词）
   - 一句话概要（short summary）
