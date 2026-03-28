# AntiFomo Browser Extension

Chrome extension for sending the current page into AntiFomo.

## Location

`browser-extension/chrome`

## What It Does

- sends the current page URL into AntiFomo
- extracts title and body when possible
- uses richer page payloads on `mp.weixin.qq.com` article pages

## Install Locally

1. Start the AntiFomo backend.
2. Open `chrome://extensions/`.
3. Enable `Developer mode`.
4. Choose `Load unpacked`.
5. Select `browser-extension/chrome`.

## Usage

1. Open a supported page in Chrome.
2. Click the extension icon.
3. Confirm the `API Base` points to your backend, for example `http://127.0.0.1:8000`.
4. Send the page to AntiFomo.

## Public Release Note

The extension ships without any hard-coded personal credentials. Adjust the API base locally after installation.
