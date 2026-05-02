"""WeChat right-click context-menu probe.

Goal: dump the actual menu items WeChat shows when you right-click on
a public-account article row, so we know the real localized labels
("在默认浏览器打开" vs "用浏览器打开" vs "复制链接" vs ...).

Usage:
  1. Open WeChat -> public-account feed view, articles visible.
  2. Hover your mouse cursor over an article row (do NOT click).
  3. Run: python3 scripts/wechat_pc_right_click_probe.py
  4. Press Enter when prompted; the script will right-click at the
     current cursor position, capture screenshots, and dump every
     menu / menu item it can find via AppleScript.

Output:
  .tmp/wechat_right_click_probe/probe_<ts>.json
  .tmp/wechat_right_click_probe/before_<ts>.png
  .tmp/wechat_right_click_probe/after_<ts>.png

Send the JSON + after_*.png back to continue.
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / ".tmp" / "wechat_right_click_probe"
WECHAT_APP = "WeChat"


def run(cmd, *, timeout=10):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class AppleScriptResult:
    __slots__ = ("stdout", "stderr", "returncode")

    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def applescript(script, *, timeout=8):
    try:
        r = run(["osascript", "-e", script], timeout=timeout)
        return AppleScriptResult(r.stdout, r.stderr, r.returncode)
    except subprocess.TimeoutExpired as exc:
        return AppleScriptResult("", f"TIMEOUT after {timeout}s: {exc}", 124)
    except Exception as exc:
        return AppleScriptResult("", f"EXCEPTION: {exc}", 1)


def get_cursor_position():
    cliclick = shutil.which("cliclick")
    if not cliclick:
        raise RuntimeError("cliclick not installed; run: brew install cliclick")
    res = run([cliclick, "p"])
    parts = (res.stdout or "").strip().split(",")
    if len(parts) != 2:
        raise RuntimeError(f"unexpected cliclick output: {res.stdout!r}")
    return int(parts[0]), int(parts[1])


def right_click_at(x, y):
    cliclick = shutil.which("cliclick")
    res = run([cliclick, f"rc:{x},{y}"])
    if res.returncode != 0:
        raise RuntimeError(f"cliclick rc failed: {res.stderr!r}")


def screenshot(path):
    try:
        run(["screencapture", "-x", str(path)], timeout=8)
    except Exception as exc:
        print(f"        WARN: screenshot failed: {exc}")


def list_windows():
    return applescript(
        '''
        tell application "System Events"
          tell process "WeChat"
            set out to ""
            repeat with w in windows
              try
                set nm to name of w as text
              on error
                set nm to ""
              end try
              try
                set p to position of w
                set sz to size of w
                set posText to ((item 1 of p) as text) & "," & ((item 2 of p) as text) & " " & ((item 1 of sz) as text) & "x" & ((item 2 of sz) as text)
              on error
                set posText to ""
              end try
              try
                set r to (value of attribute "AXRole" of w) as text
              on error
                set r to ""
              end try
              set out to out & r & tab & nm & tab & posText & linefeed
            end repeat
            return out
          end tell
        end tell
        '''
    )


def dump_popup_window():
    """WeChat 4.x renders right-click menus as a small borderless
    AXWindow (NOT a standard AXMenu), so we have to find that window
    and enumerate its UI elements one level deep."""
    return applescript(
        '''
        tell application "System Events"
          tell process "WeChat"
            set out to ""
            try
              set wlist to windows
              repeat with w in wlist
                try
                  set wn to name of w as text
                on error
                  set wn to ""
                end try
                try
                  set p to position of w
                  set sz to size of w
                  set ww to (item 1 of sz) as integer
                  set wh to (item 2 of sz) as integer
                  set wx to (item 1 of p) as integer
                  set wy to (item 2 of p) as integer
                on error
                  set ww to 0
                  set wh to 0
                  set wx to 0
                  set wy to 0
                end try
                -- popup heuristic: small, anonymous-ish window
                if (ww > 0 and ww < 400 and wh > 0 and wh < 800) then
                  set out to out & "POPUP_WIN" & tab & wn & tab & (wx as text) & "," & (wy as text) & " " & (ww as text) & "x" & (wh as text) & linefeed
                  try
                    set elems to UI elements of w
                    repeat with e in elems
                      try
                        set er to (value of attribute "AXRole" of e) as text
                      on error
                        set er to ""
                      end try
                      try
                        set en to name of e as text
                      on error
                        set en to ""
                      end try
                      try
                        set ed to (value of attribute "AXDescription" of e) as text
                      on error
                        set ed to ""
                      end try
                      try
                        set ev to (value of attribute "AXValue" of e) as text
                      on error
                        set ev to ""
                      end try
                      try
                        set ep to position of e
                        set es to size of e
                        set epos to ((item 1 of ep) as text) & "," & ((item 2 of ep) as text) & " " & ((item 1 of es) as text) & "x" & ((item 2 of es) as text)
                      on error
                        set epos to ""
                      end try
                      set out to out & "  L1" & tab & er & tab & en & tab & ed & tab & ev & tab & epos & linefeed
                      -- one more level deep
                      try
                        set kids to UI elements of e
                        repeat with k in kids
                          try
                            set kr to (value of attribute "AXRole" of k) as text
                          on error
                            set kr to ""
                          end try
                          try
                            set kn to name of k as text
                          on error
                            set kn to ""
                          end try
                          try
                            set kd to (value of attribute "AXDescription" of k) as text
                          on error
                            set kd to ""
                          end try
                          try
                            set kv to (value of attribute "AXValue" of k) as text
                          on error
                            set kv to ""
                          end try
                          try
                            set kp to position of k
                            set ks to size of k
                            set kpos to ((item 1 of kp) as text) & "," & ((item 2 of kp) as text) & " " & ((item 1 of ks) as text) & "x" & ((item 2 of ks) as text)
                          on error
                            set kpos to ""
                          end try
                          set out to out & "    L2" & tab & kr & tab & kn & tab & kd & tab & kv & tab & kpos & linefeed
                        end repeat
                      end try
                    end repeat
                  end try
                end if
              end repeat
            end try
            return out
          end tell
        end tell
        '''
    , timeout=10)


def dump_top_level_menus():
    """Right-click popups in macOS show up as `menu 1` of the process,
    or as a top-level AXMenu UI element. We only query these — never
    `entire contents`, which is way too slow on WeChat 4.x."""
    return applescript(
        '''
        tell application "System Events"
          tell process "WeChat"
            set out to ""
            -- Path A: directly query menu 1
            try
              set m to menu 1
              try
                set mr to (value of attribute "AXRole" of m) as text
              on error
                set mr to ""
              end try
              try
                set mn to name of m as text
              on error
                set mn to ""
              end try
              set out to out & "MENU1" & tab & mr & tab & mn & linefeed
              try
                set milist to menu items of m
                repeat with mi in milist
                  try
                    set inm to name of mi as text
                  on error
                    set inm to ""
                  end try
                  try
                    set ie to (value of attribute "AXEnabled" of mi) as text
                  on error
                    set ie to ""
                  end try
                  set out to out & "  MI" & tab & inm & tab & "enabled=" & ie & linefeed
                end repeat
              end try
            end try
            -- Path B: top-level UI elements; only recurse one level into AXMenu
            try
              set elems to UI elements
              repeat with e in elems
                try
                  set r to (value of attribute "AXRole" of e) as text
                on error
                  set r to ""
                end try
                try
                  set nm to name of e as text
                on error
                  set nm to ""
                end try
                set out to out & "TOP" & tab & r & tab & nm & linefeed
                if r is "AXMenu" then
                  try
                    set children to UI elements of e
                    repeat with c in children
                      try
                        set cr to (value of attribute "AXRole" of c) as text
                      on error
                        set cr to ""
                      end try
                      try
                        set cn to name of c as text
                      on error
                        set cn to ""
                      end try
                      try
                        set ce to (value of attribute "AXEnabled" of c) as text
                      on error
                        set ce to ""
                      end try
                      set out to out & "  ITEM" & tab & cr & tab & cn & tab & "enabled=" & ce & linefeed
                    end repeat
                  end try
                end if
              end repeat
            end try
            return out
          end tell
        end tell
        '''
    , timeout=6)


def dump_menubar():
    """Also probe the application menubar so we know if there is a
    'copy link' / 'open in browser' menu item available there."""
    return applescript(
        '''
        tell application "System Events"
          tell process "WeChat"
            set out to ""
            try
              set bars to menu bar 1
              set bm to menus of bars
              repeat with m in bm
                try
                  set nm to name of m as text
                on error
                  set nm to ""
                end try
                set out to out & "MENU" & tab & nm & linefeed
                try
                  set items_ to menu items of m
                  repeat with mi in items_
                    try
                      set inm to name of mi as text
                    on error
                      set inm to ""
                    end try
                    set out to out & "  ITEM" & tab & inm & linefeed
                    -- one level of submenu
                    try
                      set sub to menu of mi
                      set subitems to menu items of sub
                      repeat with sm in subitems
                        try
                          set snm to name of sm as text
                        on error
                          set snm to ""
                        end try
                        set out to out & "    SUB" & tab & snm & linefeed
                      end repeat
                    end try
                  end repeat
                end try
              end repeat
            end try
            return out
          end tell
        end tell
        '''
    )


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=== WeChat right-click context-menu probe ===")
    print()
    print("Steps:")
    print("  1. Open WeChat -> 公众号 feed.")
    print("  2. Press Enter below.")
    print("  3. You then have 6 seconds to switch to WeChat (Cmd+Tab) and")
    print("     HOVER (do NOT click) the mouse over an article row.")
    print("  4. Script will activate WeChat, right-click, and dump menus.")
    print()
    try:
        input("Press Enter to start countdown... ")
    except KeyboardInterrupt:
        print("\naborted")
        sys.exit(1)

    for n in range(6, 0, -1):
        print(f"  hover over WeChat article in {n}s ...", end="\r", flush=True)
        time.sleep(1)
    print()

    try:
        cx, cy = get_cursor_position()
    except Exception as exc:
        print(f"FATAL: cannot read cursor position: {exc}")
        sys.exit(1)
    print(f"Cursor at: ({cx}, {cy})")

    # Force WeChat to the front so the right-click hits it (mouse events are
    # routed by screen coordinate, but activating ensures any z-order overlay
    # from the terminal etc. is dismissed).
    applescript('tell application "WeChat" to activate')
    time.sleep(0.4)

    ts = int(time.time())
    pre_path = OUT_DIR / f"before_{ts}.png"
    post_path = OUT_DIR / f"after_{ts}.png"

    # Don't activate WeChat before reading cursor — user already had it focused.
    # But probe AppleScript needs WeChat to be the target; it's fine because
    # System Events targets the named process explicitly.

    print(f"  [1/6] pre-click screenshot -> {pre_path.name}")
    screenshot(pre_path)

    print(f"  [2/6] right-click at ({cx}, {cy}) ...")
    try:
        right_click_at(cx, cy)
    except Exception as exc:
        print(f"        WARN: right-click failed: {exc}")
    time.sleep(0.7)  # let the popup render

    # Dump menus FIRST — every other AppleScript query risks dismissing
    # the popup. Screenshot is taken in parallel via screencapture which
    # does not steal AX focus.
    print("  [3/7] dump popup AXWindow contents (timeout 10s) ...")
    popup_res = dump_popup_window()
    print(f"        popup dump: rc={popup_res.returncode} "
          f"stdout_len={len(popup_res.stdout)} stderr={popup_res.stderr[:120]!r}")

    print("  [4/7] dump top-level UI elements ...")
    top_res = dump_top_level_menus()
    print(f"        top_level dump: rc={top_res.returncode} "
          f"stdout_len={len(top_res.stdout)} stderr={top_res.stderr[:120]!r}")

    print(f"  [5/7] post-click screenshot -> {post_path.name}")
    screenshot(post_path)

    print("  [6/7] list windows ...")
    win_res = list_windows()
    bar_res = AppleScriptResult("", "skipped (known empty + slow)", 0)
    print("  [7/7] menubar dump skipped (already known)")

    # Dismiss the popup so we don't leave WeChat in a weird state.
    applescript('tell application "System Events" to key code 53')

    print()
    print("--- Windows after right-click ---")
    print(win_res.stdout or "(empty)")
    if win_res.stderr:
        print("STDERR:", win_res.stderr)

    print()
    print("--- Top-level UI elements + AXMenu items ---")
    print(top_res.stdout or "(empty)")
    if top_res.stderr:
        print("STDERR:", top_res.stderr)

    print()
    print("--- Menubar (one level deep) ---")
    print(bar_res.stdout or "(empty)")
    if bar_res.stderr:
        print("STDERR:", bar_res.stderr)

    out_json = OUT_DIR / f"probe_{ts}.json"
    out_json.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "cursor": {"x": cx, "y": cy},
                "before_screenshot": str(pre_path),
                "after_screenshot": str(post_path),
                "windows": win_res.stdout or "",
                "windows_stderr": win_res.stderr or "",
                "popup_window": popup_res.stdout or "",
                "popup_window_stderr": popup_res.stderr or "",
                "top_level": top_res.stdout or "",
                "top_level_stderr": top_res.stderr or "",
                "menubar": bar_res.stdout or "",
                "menubar_stderr": bar_res.stderr or "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print()
    print(f"Saved: {out_json}")
    print(f"Send back: {out_json.name} + {post_path.name}")


if __name__ == "__main__":
    main()
