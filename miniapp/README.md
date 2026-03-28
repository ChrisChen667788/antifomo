# AntiFomo Mini Program

This directory contains the WeChat Mini Program client for AntiFomo.

## Import Into WeChat DevTools

1. Start the backend locally.
2. Open WeChat DevTools and choose `Import Project`.
3. Select this `miniapp/` directory.
4. Fill in your own Mini Program `AppID` in `project.config.json`.
5. In local development, disable domain and TLS checks if you are targeting `localhost` or a LAN backend.

## API Base

The mini program defaults to a local backend:

- local: `http://127.0.0.1:8000`
- device preview: `http://<your-lan-ip>:8000`

You can also update the backend connection from the in-app settings page.

## Supported Areas

- Feed browsing and preference feedback
- Inbox URL/text submission
- Research center and topic workspace
- Focus sessions and session summary
- Collector status and operations
- WeChat PC agent visibility and control hooks

## Public Release Note

The public repository intentionally removes the original `AppID`. Replace it with your own before compiling in WeChat DevTools.
