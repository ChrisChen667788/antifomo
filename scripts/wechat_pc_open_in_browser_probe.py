"""End-to-end verification: right-click article tab -> popup menu ->
keyboard-navigate to "使用默认浏览器打开" -> wait for browser -> read URL.

Prerequisite (manual setup, do this once before each run):
  1. Open WeChat.
  2. Click any public-account article so the dedicated article window
     opens (the one whose top has the Safari-style tab title).
  3. Make sure the article window is visible on screen (it can be
     anywhere — the script detects its position dynamically).
  4. DO NOT focus the terminal yet.

Usage:
  python3 scripts/wechat_pc_open_in_browser_probe.py

Output:
  .tmp/wechat_open_browser_probe/run_<ts>.json
  .tmp/wechat_open_browser_probe/step_*.png

This does NOT modify the main agent. It is a dry-run end-to-end test.
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / ".tmp" / "wechat_open_browser_probe"
WECHAT_APP = "WeChat"

# Window names that are part of the persistent WeChat shell — anything
# else (especially anonymous "微信 (窗口)" duplicates) is likely the
# article reading window.
KNOWN_SHELL_TITLES = {
    "微信",
    "与“陈皓锐”的聊天记录",
    "存储空间",
    "设置",
}

BROWSER_NAMES = {
    "Safari",
    "Google Chrome",
    "Chromium",
    "Arc",
    "Brave Browser",
    "Microsoft Edge",
    "Opera",
    "Vivaldi",
}


class Result:
    __slots__ = ("stdout", "stderr", "rc")

    def __init__(self, stdout="", stderr="", rc=0):
        self.stdout = stdout
        self.stderr = stderr
        self.rc = rc


def run(cmd, *, timeout=8):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return Result(r.stdout, r.stderr, r.returncode)
    except subprocess.TimeoutExpired as exc:
        return Result("", f"TIMEOUT {timeout}s: {exc}", 124)
    except Exception as exc:
        return Result("", f"EXC: {exc}", 1)


def applescript(script, *, timeout=8):
    return run(["osascript", "-e", script], timeout=timeout)


def cliclick(*args, timeout=4):
    bin_ = shutil.which("cliclick")
    if not bin_:
        raise RuntimeError("cliclick not installed; brew install cliclick")
    return run([bin_, *args], timeout=timeout)


def screenshot(path):
    run(["screencapture", "-x", str(path)], timeout=8)


def list_wechat_windows():
    """Return list of (role, name, x, y, w, h)."""
    res = applescript(
        '''
        tell application "System Events"
          tell process "WeChat"
            set out to ""
            try
              set ws to windows
              repeat with w in ws
                try
                  set wn to name of w as text
                on error
                  set wn to ""
                end try
                try
                  set p to position of w
                  set sz to size of w
                  set out to out & wn & "|" & ((item 1 of p) as text) & "|" & ((item 2 of p) as text) & "|" & ((item 1 of sz) as text) & "|" & ((item 2 of sz) as text) & linefeed
                end try
              end repeat
            end try
            return out
          end tell
        end tell
        ''',
        timeout=6,
    )
    rows = []
    for line in (res.stdout or "").splitlines():
        parts = line.split("|")
        if len(parts) != 5:
            continue
        try:
            x, y, w, h = (int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]))
        except ValueError:
            continue
        rows.append({"name": parts[0], "x": x, "y": y, "w": w, "h": h})
    return rows


def detect_article_window(windows):
    """Pick the article window. WeChat 4.x opens articles as a new
    `微信 (窗口)` AXWindow that overlays the main window. System Events
    returns `windows` in z-index order (topmost first), so after
    skipping shells and popups, the first remaining candidate is the
    front article window.
    """
    for w in windows:
        if w["name"] in KNOWN_SHELL_TITLES:
            continue
        if w["w"] < 400 or w["h"] < 500:
            continue  # popups / dialogs
        return w
    return None


def detect_popup_window(windows):
    """Popup menu is small (w<400, h<800), often anonymous."""
    for w in windows:
        if w["w"] < 400 and 80 < w["h"] < 800 and not w["name"]:
            return w
    return None


def get_front_process():
    res = applescript(
        '''
        tell application "System Events"
          set p to first process whose frontmost is true
          return name of p
        end tell
        ''',
        timeout=4,
    )
    return (res.stdout or "").strip()


def read_browser_url(front):
    if front == "Safari":
        res = applescript(
            'tell application "Safari" to return URL of current tab of front window',
            timeout=4,
        )
    elif front in {"Google Chrome", "Chromium", "Brave Browser", "Arc"}:
        res = applescript(
            f'tell application "{front}" to return URL of active tab of front window',
            timeout=4,
        )
    elif front == "Microsoft Edge":
        res = applescript(
            'tell application "Microsoft Edge" to return URL of active tab of front window',
            timeout=4,
        )
    else:
        return ""
    return (res.stdout or "").strip()


def activate_wechat():
    applescript('tell application "WeChat" to activate', timeout=3)
    time.sleep(0.3)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    log = {"timestamp": ts, "steps": []}

    def step(name, **data):
        entry = {"at": time.strftime("%H:%M:%S"), "name": name, **data}
        log["steps"].append(entry)
        print(f"[{entry['at']}] {name}: {json.dumps(data, ensure_ascii=False)}")

    print("=== End-to-end open-in-browser probe ===")
    print("Make sure an article window is already open in WeChat.")
    print("(left-click any public-account article, then come back here)")
    print()
    try:
        input("Press Enter to start... ")
    except KeyboardInterrupt:
        print("aborted")
        sys.exit(1)

    # 1. Activate WeChat so its windows come to the front, but don't
    # overshadow detection.
    activate_wechat()

    # 2. List windows + detect article window.
    wins_before = list_wechat_windows()
    step("windows_before", windows=wins_before)
    article = detect_article_window(wins_before)
    if not article:
        step("FAIL", reason="no article window detected — open one in WeChat first")
        save_log(log, ts)
        sys.exit(1)
    step("article_window", window=article)

    # 3. Right-click on tab title (relative offsets, fall back through
    # multiple x positions if the first attempt misses the tab).
    pre_path = OUT_DIR / f"step_{ts}_1_pre_rc.png"
    screenshot(pre_path)
    step("pre_screenshot", path=str(pre_path.name))

    candidate_offsets = [(316, 25), (200, 30), (450, 30), (150, 25)]
    popup = None
    last_click = None
    for off_x, off_y in candidate_offsets:
        tab_x = article["x"] + off_x
        tab_y = article["y"] + off_y
        last_click = (tab_x, tab_y)
        rc_res = cliclick(f"rc:{tab_x},{tab_y}")
        step("right_click_attempt", x=tab_x, y=tab_y, off=(off_x, off_y),
             rc=rc_res.rc, stderr=rc_res.stderr[:80])
        time.sleep(0.6)
        wins_after = list_wechat_windows()
        popup = detect_popup_window(wins_after)
        if popup:
            step("popup_detection_hit", popup=popup, off=(off_x, off_y))
            break
        # Dismiss any stray hover/popup before trying the next position.
        applescript('tell application "System Events" to key code 53', timeout=3)
        time.sleep(0.2)

    popup_path = OUT_DIR / f"step_{ts}_2_popup.png"
    screenshot(popup_path)

    if not popup:
        step("FAIL", reason="no popup after trying all 4 offsets — tab position unknown",
             last_click=last_click)
        save_log(log, ts)
        sys.exit(1)

    # 5. Keyboard navigate to "使用默认浏览器打开" (item index 4 in the
    # observed menu, counting visible items including the leading three
    # share-related items). We press Down 4 times slowly, then Return.
    target_index = 4
    for i in range(target_index):
        applescript('tell application "System Events" to key code 125', timeout=3)  # Down
        time.sleep(0.18)
    step("keyboard_down", times=target_index)

    nav_path = OUT_DIR / f"step_{ts}_3_after_down.png"
    screenshot(nav_path)
    step("after_down_screenshot", path=str(nav_path.name))

    applescript('tell application "System Events" to key code 36', timeout=3)  # Return
    step("keyboard_return")

    # 6. Wait for browser to come front, capture URL.
    deadline = time.time() + 6.0
    front_seen = ""
    url = ""
    while time.time() < deadline:
        time.sleep(0.4)
        front = get_front_process()
        if front and front != front_seen:
            front_seen = front
            step("front_process_change", front=front)
        if front in BROWSER_NAMES:
            time.sleep(0.4)  # let URL settle
            url = read_browser_url(front)
            step("browser_url_read", front=front, url=url)
            if url:
                break

    final_path = OUT_DIR / f"step_{ts}_4_final.png"
    screenshot(final_path)
    step("final_screenshot", path=str(final_path.name))

    if url and "weixin" in url.lower():
        step("SUCCESS", url=url)
    elif url:
        step("PARTIAL", reason="browser opened, but URL not weixin", url=url)
    else:
        step("FAIL", reason="browser never came front / no URL captured", front_seen=front_seen)

    save_log(log, ts)


def save_log(log, ts):
    p = OUT_DIR / f"run_{ts}.json"
    p.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nLog saved: {p}")


if __name__ == "__main__":
    main()
