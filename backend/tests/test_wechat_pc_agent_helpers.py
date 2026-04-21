from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image, ImageDraw


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wechat_pc_full_auto_agent.py"
SPEC = importlib.util.spec_from_file_location("wechat_pc_full_auto_agent", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_test_frame(path: Path, *, offset_x: int, offset_y: int) -> None:
    image = Image.new("RGB", (220, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36 + offset_x, 28 + offset_y, 186 + offset_x, 132 + offset_y), radius=16, outline="black", width=4)
    draw.ellipse((164 + offset_x, 40 + offset_y, 172 + offset_x, 48 + offset_y), fill="black")
    draw.ellipse((176 + offset_x, 40 + offset_y, 184 + offset_x, 48 + offset_y), fill="black")
    draw.ellipse((188 + offset_x, 40 + offset_y, 196 + offset_x, 48 + offset_y), fill="black")
    image.save(path)


@pytest.mark.skipif(MODULE.Image is None, reason="Pillow unavailable for agent helper test")
def test_perceptual_hash_detects_similar_capture(tmp_path: Path) -> None:
    base = tmp_path / "base.png"
    shifted = tmp_path / "shifted.png"
    different = tmp_path / "different.png"

    _write_test_frame(base, offset_x=0, offset_y=0)
    _write_test_frame(shifted, offset_x=3, offset_y=2)

    image = Image.new("RGB", (220, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 90, 150), fill="black")
    image.save(different)

    base_hash = MODULE.file_perceptual_hash(base)
    shifted_hash = MODULE.file_perceptual_hash(shifted)
    different_hash = MODULE.file_perceptual_hash(different)

    assert base_hash and shifted_hash and different_hash

    state = {"processed_hashes": {base_hash: "2026-03-29T00:00:00+00:00"}}
    matched_hash, distance = MODULE.find_similar_perceptual_hash(state, shifted_hash, threshold=10)
    assert matched_hash == base_hash
    assert distance is not None and distance <= 10

    unmatched_hash, unmatched_distance = MODULE.find_similar_perceptual_hash(state, different_hash, threshold=4)
    assert unmatched_hash is None
    assert unmatched_distance is None


def test_build_article_row_click_points_rotates_after_route_issues() -> None:
    baseline = MODULE._build_article_row_click_points(
        row_x=1200,
        row_y=320,
        row_height=140,
        route_issue_streak=0,
        duplicate_article_streak=0,
    )
    routed = MODULE._build_article_row_click_points(
        row_x=1200,
        row_y=320,
        row_height=140,
        route_issue_streak=3,
        duplicate_article_streak=0,
    )

    assert baseline[0] == (1200, 320)
    assert routed[0] != baseline[0]
    assert set(routed) == set(baseline)


def test_select_unblocked_candidate_index_skips_trapped_hotspots() -> None:
    assert MODULE._select_unblocked_candidate_index(
        total_candidates=4,
        blocked_candidates={0, 2},
        attempt_idx=0,
    ) == 1
    assert MODULE._select_unblocked_candidate_index(
        total_candidates=4,
        blocked_candidates={0, 2},
        attempt_idx=1,
    ) == 3
    assert MODULE._select_unblocked_candidate_index(
        total_candidates=3,
        blocked_candidates={0, 1, 2},
        attempt_idx=0,
    ) == -1


def test_try_extract_article_url_prefers_open_in_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 360, "y": 110, "width": 1020, "height": 860},
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [(1300, 138)])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [])
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(
        MODULE,
        "wait_for_article_destination",
        lambda *_args, **_kwargs: ("Safari", ["WeChat", "Safari"]),
    )
    monkeypatch.setattr(
        MODULE,
        "wait_for_allowed_front_browser_url",
        lambda *_args, **_kwargs: "https://mp.weixin.qq.com/s?__biz=demo&mid=1&idx=1&sn=2",
    )

    calls: list[tuple[str, ...]] = []

    def fake_click_named(_app_name: str, names: tuple[str, ...]) -> bool:
        calls.append(names)
        return names == MODULE.OPEN_IN_BROWSER_KEYWORDS

    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", fake_click_named)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 360, "y": 110, "width": 1020, "height": 860},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=1&idx=1&sn=2"
    assert meta["used_accessibility"] is True
    assert meta["used_browser_open"] is True
    assert MODULE.OPEN_IN_BROWSER_KEYWORDS in calls


def test_find_accessibility_action_points_prefers_actionable_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_find_accessibility_action_candidates",
        lambda *_args, **_kwargs: [
            {"center_x": 1302, "center_y": 144},
            {"center_x": 1288, "center_y": 144},
        ],
    )

    points = MODULE._find_accessibility_action_points(
        "WeChat",
        region={"x": 360, "y": 110, "width": 1020, "height": 860},
        limit=4,
    )

    assert points == [(1302, 144), (1288, 144)]


def test_try_extract_article_url_uses_accessibility_action_candidate_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    front_process = {"name": "WeChat"}

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: front_process["name"])
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 360, "y": 110, "width": 1020, "height": 860},
    )
    monkeypatch.setattr(
        MODULE,
        "_find_accessibility_action_candidates",
        lambda *_args, **_kwargs: [
            {
                "role": "AXMenuButton",
                "subrole": "",
                "name": "更多",
                "description": "",
                "actions": ["AXShowMenu", "AXPress"],
                "x": 1280,
                "y": 128,
                "width": 40,
                "height": 28,
                "center_x": 1300,
                "center_y": 142,
            }
        ],
    )
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [])
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("click_at should not run")))
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("Safari", ["WeChat", "Safari"]))
    monkeypatch.setattr(
        MODULE,
        "wait_for_allowed_front_browser_url",
        lambda *_args, **_kwargs: "https://mp.weixin.qq.com/s?__biz=demo&mid=10&idx=1&sn=11",
    )
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)

    def fake_trigger(_app_name: str, _candidate: dict[str, object]) -> str:
        front_process["name"] = "Safari"
        return "AXShowMenu"

    monkeypatch.setattr(MODULE, "_trigger_accessibility_action_candidate", fake_trigger)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 360, "y": 110, "width": 1020, "height": 860},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=10&idx=1&sn=11"
    assert meta["used_accessibility"] is True


def test_try_extract_article_url_falls_back_to_app_menu_browser_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 360, "y": 110, "width": 1020, "height": 860},
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [])
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(
        MODULE,
        "wait_for_article_destination",
        lambda *_args, **_kwargs: ("Safari", ["WeChat", "Safari"]),
    )
    monkeypatch.setattr(
        MODULE,
        "wait_for_allowed_front_browser_url",
        lambda *_args, **_kwargs: "https://mp.weixin.qq.com/s?__biz=demo&mid=12&idx=1&sn=13",
    )
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        MODULE,
        "_click_app_menu_item_by_keywords",
        lambda *_args, **_kwargs: "查看:在默认浏览器打开",
    )

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 360, "y": 110, "width": 1020, "height": 860},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=12&idx=1&sn=13"
    assert meta["used_browser_open"] is True


def test_run_command_reports_timeout() -> None:
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["osascript"], timeout=4.0)

    original_run = MODULE.subprocess.run
    MODULE.subprocess.run = fake_run
    try:
        with pytest.raises(RuntimeError, match="applescript_timeout:4.0s"):
            MODULE._run_command(["osascript"], timeout_sec=4.0, error_label="applescript")
    finally:
        MODULE.subprocess.run = original_run


def test_try_extract_article_url_ignores_initial_clipboard_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 360, "y": 110, "width": 1020, "height": 860},
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_build_article_link_points", lambda **_kwargs: ([], [], "manual"))
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [])
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: (_ for _ in ()).throw(RuntimeError("clipboard_timeout:2.0s")))

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 360, "y": 110, "width": 1020, "height": 860},
        link_profile="manual",
        share_hotspots=[],
        menu_offsets=[],
    )

    assert article_url is None
    assert meta["accessibility_candidates"] == 0
    assert meta["template_candidates"] == 0


def test_try_extract_article_url_attaches_debug_artifact_on_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 688, "y": 110, "width": 1607, "height": 1152},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([(2196, 136)], [(0, 42)], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [(2196, 136)])
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "_write_url_probe_debug_artifact", lambda **_kwargs: ".tmp/wechat_agent_debug/url_probe_test.png")

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 688, "y": 110, "width": 1607, "height": 1152},
        link_profile="standard",
    )

    assert article_url is None
    assert meta["debug_artifact"] == ".tmp/wechat_agent_debug/url_probe_test.png"


def test_try_extract_article_url_skips_no_signal_probe_for_dark_blank_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicks: list[tuple[int, int]] = []

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 688, "y": 110, "width": 1607, "height": 1152},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([(2196, 136)], [(0, 42)], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [])
    monkeypatch.setattr(MODULE, "_classify_url_probe_surface", lambda **_kwargs: "dark_blank")
    monkeypatch.setattr(MODULE, "_write_url_probe_debug_artifact", lambda **_kwargs: ".tmp/wechat_agent_debug/url_probe_dark.png")
    monkeypatch.setattr(MODULE, "click_at", lambda x, y, **_kwargs: clicks.append((x, y)))
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 688, "y": 110, "width": 1607, "height": 1152},
        link_profile="standard",
    )

    assert article_url is None
    assert clicks == []
    assert meta["surface_state"] == "dark_blank"
    assert meta["debug_artifact"] == ".tmp/wechat_agent_debug/url_probe_dark.png"


def test_try_extract_article_url_uses_multiple_manual_hotspots_when_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    current_share_click: list[tuple[int, int]] = []
    share_points = [(1200, 120), (1186, 132), (1172, 144)]

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 360, "y": 110, "width": 1020, "height": 860},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: (share_points, [], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_build_no_signal_menu_probe_points", lambda: [])
    monkeypatch.setattr(MODULE, "_classify_url_probe_surface", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [])
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_share_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_share_click and current_share_click[0] == share_points[1]:
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=1&idx=1&sn=2"
        return ""

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 360, "y": 110, "width": 1020, "height": 860},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=1&idx=1&sn=2"
    assert meta["accessibility_candidates"] == 0
    assert meta["template_candidates"] == 0


def test_try_extract_article_url_tries_more_menu_offsets_when_template_signal_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_click: list[tuple[int, int]] = []
    share_point = (1298, 136)
    menu_offsets = [(0, 42), (0, 78), (0, 112)]

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 688, "y": 110, "width": 1607, "height": 1152},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], menu_offsets, "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(MODULE, "_build_template_action_target_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "strong_change", "diff_mean": 18.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_click and current_click[0] == (share_point[0] - 96, share_point[1] + 78):
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=2&idx=1&sn=3"
        return ""

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 688, "y": 110, "width": 1607, "height": 1152},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=2&idx=1&sn=3"
    assert meta["used_template_match"] is True
    assert meta["accessibility_candidates"] == 0
    assert meta["template_candidates"] == 1


def test_try_extract_article_url_prefers_left_expanded_menu_for_template_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_click: list[tuple[int, int]] = []
    share_point = (2196, 136)

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 688, "y": 110, "width": 1607, "height": 1152},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], [(0, 42)], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(MODULE, "_build_template_action_target_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "strong_change", "diff_mean": 18.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_click and current_click[0] == (share_point[0] - 128, share_point[1] + 78):
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=3&idx=1&sn=4"
        return ""

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 688, "y": 110, "width": 1607, "height": 1152},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=3&idx=1&sn=4"
    assert meta["used_template_match"] is True


def test_try_extract_article_url_reclicks_template_point_before_menu_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    share_clicks: list[tuple[int, int]] = []
    share_point = (2196, 136)

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 688, "y": 110, "width": 1607, "height": 1152},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], [], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(MODULE, "_build_template_action_target_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "strong_change", "diff_mean": 18.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        share_clicks.append((x, y))

    def fake_click_named(_app_name: str, names: tuple[str, ...]) -> bool:
        return names == MODULE.COPY_LINK_KEYWORDS and len(share_clicks) >= 2

    def fake_read_clipboard_text() -> str:
        if len(share_clicks) >= 2:
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=4&idx=1&sn=5"
        return ""

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", fake_click_named)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 688, "y": 110, "width": 1607, "height": 1152},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=4&idx=1&sn=5"
    assert len(share_clicks) >= 2
    assert meta["used_template_match"] is True


def test_try_extract_article_url_browser_first_uses_calibrated_template_hotspot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_share_click: list[tuple[int, int]] = []
    template_points = [(1951, 205), (1957, 205), (1963, 205)]

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 749, "y": 191, "width": 1548, "height": 1094},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: (template_points, [], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: template_points)
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "strong_change", "diff_mean": 18.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_share_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_share_click and current_share_click[0] == (1941, 213):
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=5&idx=1&sn=6"
        return ""

    def fake_click_named(_app_name: str, names: tuple[str, ...]) -> bool:
        return names == MODULE.COPY_LINK_KEYWORDS and bool(current_share_click) and current_share_click[0] == (1941, 213)

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", fake_click_named)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        url_strategy="browser_first",
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=5&idx=1&sn=6"
    assert meta["used_template_match"] is True
    assert meta["template_candidates"] == 3


def test_build_template_action_target_points_biases_left_and_lower_near_right_edge() -> None:
    points = MODULE._build_template_action_target_points(
        region_x=749,
        region_y=191,
        region_width=1548,
        share_x=1951,
        share_y=205,
    )

    assert points[0] == (1951, 205)
    assert (1941, 213) in points
    assert (1933, 217) in points
    assert len(points) >= 5


def test_prime_article_action_surface_biases_right_header_for_right_edge_share(monkeypatch: pytest.MonkeyPatch) -> None:
    clicks: list[tuple[int, int]] = []

    monkeypatch.setattr(MODULE, "click_at", lambda x, y, **_kwargs: clicks.append((x, y)))
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    profile = MODULE._prime_article_action_surface(
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        share_point=(1951, 205),
    )

    assert profile == "mid_header"
    assert len(clicks) == 2
    assert clicks[0][0] > 1700
    assert clicks[0][1] > 300


def test_try_extract_article_url_uses_template_action_target_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_share_click: list[tuple[int, int]] = []
    template_points = [(1951, 205)]

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 749, "y": 191, "width": 1548, "height": 1094},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: (template_points, [], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: template_points)
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "strong_change", "diff_mean": 18.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_share_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_share_click and current_share_click[0] == (1941, 213):
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=55&idx=1&sn=66"
        return ""

    def fake_click_named(_app_name: str, names: tuple[str, ...]) -> bool:
        return names == MODULE.COPY_LINK_KEYWORDS and bool(current_share_click) and current_share_click[0] == (1941, 213)

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", fake_click_named)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=55&idx=1&sn=66"
    assert meta["used_template_match"] is True


def test_try_extract_article_url_records_action_surface_prime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    share_point = (1951, 205)

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 749, "y": 191, "width": 1548, "height": 1094},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], [], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(MODULE, "_prime_article_action_surface", lambda **_kwargs: "mid_header")
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "no_change", "diff_mean": 0.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        link_profile="standard",
    )

    assert article_url is None
    assert meta["action_surface_prime"] == "mid_header"


def test_try_extract_article_url_browser_first_uses_deeper_template_menu_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_click: list[tuple[int, int]] = []
    share_point = (1951, 205)

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 749, "y": 191, "width": 1548, "height": 1094},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], [(0, 42)], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "strong_change", "diff_mean": 18.0},
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_click and current_click[0] == (share_point[0] - 208, share_point[1] + 78):
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=6&idx=1&sn=7"
        return ""

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        url_strategy="browser_first",
        link_profile="standard",
    )

    assert article_url == "https://mp.weixin.qq.com/s?__biz=demo&mid=6&idx=1&sn=7"
    assert meta["used_template_match"] is True


def test_analyze_visual_region_transition_detects_change(tmp_path: Path) -> None:
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    _write_test_frame(before_path, offset_x=0, offset_y=0)
    _write_test_frame(after_path, offset_x=24, offset_y=18)

    analysis = MODULE._analyze_visual_region_transition(before_path, after_path)

    assert analysis is not None
    assert analysis["changed"] is True
    assert analysis["state"] in {"weak_change", "strong_change"}
    assert float(analysis["diff_mean"]) > 0


def test_try_extract_article_url_records_menu_visual_probe_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    share_point = (1951, 205)

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 749, "y": 191, "width": 1548, "height": 1094},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], [], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {
            "state": "strong_change",
            "diff_mean": 19.5,
            "debug_artifact": ".tmp/wechat_agent_debug/url_menu_demo.png",
        },
    )
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "read_clipboard_text", lambda: "")
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        url_strategy="browser_first",
        link_profile="standard",
    )

    assert article_url is None
    assert meta["menu_visual_state"] == "strong_change"
    assert meta["menu_visual_change"] == 19.5
    assert meta["menu_debug_artifact"] == ".tmp/wechat_agent_debug/url_menu_demo.png"


def test_try_extract_article_url_skips_template_menu_offsets_when_no_visual_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_click: list[tuple[int, int]] = []
    share_point = (1951, 205)

    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(
        MODULE,
        "resolve_region",
        lambda article_region, **_kwargs: {"x": 749, "y": 191, "width": 1548, "height": 1094},
    )
    monkeypatch.setattr(
        MODULE,
        "_build_article_link_points",
        lambda **_kwargs: ([share_point], [(0, 42)], "standard"),
    )
    monkeypatch.setattr(MODULE, "_find_accessibility_action_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(MODULE, "_locate_visual_action_points", lambda **_kwargs: [share_point])
    monkeypatch.setattr(
        MODULE,
        "_probe_template_menu_visual_state",
        lambda **_kwargs: {"state": "no_change", "diff_mean": 0.0},
    )
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "_click_accessibility_named_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE, "_dismiss_wechat_overlay", lambda: None)
    monkeypatch.setattr(MODULE, "write_clipboard_text", lambda _value: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_click_at(x: int, y: int, **_kwargs) -> None:
        current_click[:] = [(x, y)]

    def fake_read_clipboard_text() -> str:
        if current_click and current_click[0] == (share_point[0] - 128, share_point[1] + 78):
            return "https://mp.weixin.qq.com/s?__biz=demo&mid=7&idx=1&sn=8"
        return ""

    monkeypatch.setattr(MODULE, "click_at", fake_click_at)
    monkeypatch.setattr(MODULE, "read_clipboard_text", fake_read_clipboard_text)

    article_url, meta = MODULE.try_extract_article_url_from_wechat_ui(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 749, "y": 191, "width": 1548, "height": 1094},
        link_profile="standard",
    )

    assert article_url is None
    assert meta["menu_visual_state"] == "no_change"


def test_calibrate_article_capture_region_repositions_legacy_region_on_wide_window() -> None:
    calibrated = MODULE._calibrate_article_capture_region(
        {"x": 360, "y": 110, "width": 1020, "height": 860},
        coordinate_mode="auto",
        window_rect=(2, 33, 2550, 1342),
    )

    assert calibrated["x"] >= 680
    assert calibrated["y"] >= 110
    assert calibrated["width"] >= 1500
    assert calibrated["height"] >= 1100
    assert calibrated["x"] + calibrated["width"] <= 2550
    assert calibrated["y"] + calibrated["height"] <= 1342


def test_calibrate_article_capture_region_keeps_normal_window_region() -> None:
    calibrated = MODULE._calibrate_article_capture_region(
        {"x": 360, "y": 110, "width": 1020, "height": 860},
        coordinate_mode="auto",
        window_rect=(0, 0, 1440, 900),
    )

    assert calibrated == {"x": 360, "y": 110, "width": 1020, "height": 860}


def test_ensure_wechat_front_ready_falls_back_to_open(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    ready_after_open = {"value": False}

    monkeypatch.setattr(MODULE, "_is_wechat_front_ready", lambda _app_name: (ready_after_open["value"], (0, 0, 1440, 900) if ready_after_open["value"] else None))
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: calls.append("activate"))

    def fake_open(_app_name: str) -> None:
        calls.append("open")
        ready_after_open["value"] = True

    monkeypatch.setattr(MODULE, "_activate_wechat_via_open", fake_open)
    monkeypatch.setattr(MODULE, "_set_wechat_process_frontmost", lambda _app_name: calls.append("frontmost"))
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: ready_after_open["value"])
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: calls.append("switch"))
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    ready, rect = MODULE._ensure_wechat_front_ready("com.tencent.xinWeChat", "WeChat")

    assert ready is True
    assert rect == (0, 0, 1440, 900)
    assert calls[:3] == ["activate", "open", "switch"]


def test_targeted_ocr_fallback_reason_only_triggers_without_action_signal() -> None:
    assert (
        MODULE._targeted_ocr_fallback_reason(
            allow_ocr_fallback=False,
            allow_targeted_ocr_fallback=True,
            article_url=None,
            route_meta={"accessibility_candidates": 0, "template_candidates": 0},
        )
        == "url_probe_no_action_signal"
    )
    assert (
        MODULE._targeted_ocr_fallback_reason(
            allow_ocr_fallback=False,
            allow_targeted_ocr_fallback=True,
            article_url=None,
            route_meta={"accessibility_candidates": 1, "template_candidates": 0},
        )
        == "url_probe_no_url_after_ui_probe"
    )
    assert (
        MODULE._targeted_ocr_fallback_reason(
            allow_ocr_fallback=False,
            allow_targeted_ocr_fallback=True,
            article_url=None,
            route_meta={"accessibility_candidates": 0, "template_candidates": 0, "surface_state": "dark_blank"},
        )
        is None
    )


def test_should_stop_profile_probe_after_standard_template_only_miss() -> None:
    should_stop, reason = MODULE._should_stop_profile_probe_after_miss(
        profile_name="standard",
        route_meta={"accessibility_candidates": 0, "template_candidates": 3, "budget_exhausted": False},
        template_only_miss_streak=1,
    )

    assert should_stop is True
    assert reason == "template_only_no_accessibility"


def test_should_stop_profile_probe_after_standard_template_menu_budget_hit() -> None:
    should_stop, reason = MODULE._should_stop_profile_probe_after_miss(
        profile_name="standard",
        route_meta={"accessibility_candidates": 0, "template_candidates": 3, "budget_exhausted": True},
        template_only_miss_streak=1,
    )

    assert should_stop is True
    assert reason == "template_menu_probe_exhausted"


def test_should_stop_profile_probe_after_standard_strong_ui_signal_miss() -> None:
    should_stop, reason = MODULE._should_stop_profile_probe_after_miss(
        profile_name="standard",
        route_meta={"accessibility_candidates": 3, "template_candidates": 3, "budget_exhausted": False},
        template_only_miss_streak=0,
    )

    assert should_stop is True
    assert reason == "standard_ui_signal_exhausted"


def test_plan_preview_url_resolve_budget_skips_placeholder_title_after_targeted_fallback() -> None:
    candidate_limit, timeout_sec, skip_reason = MODULE._plan_preview_url_resolve_budget(
        preview={
            "title": "WeChat Auto 04-10 16:19 B1R1",
            "body_preview": "项目进入方案评估阶段",
            "body_text": "项目进入方案评估阶段，相关正文仍较短。",
            "text_length": 96,
        },
        title_hint="WeChat Auto 04-10 16:19 B1R1",
        targeted_fallback=True,
        targeted_timeout_sec=MODULE.DEFAULT_TARGETED_URL_RESOLVE_TIMEOUT_SEC,
    )

    assert candidate_limit == 0
    assert timeout_sec == 0
    assert skip_reason == "placeholder_title_short_preview"


def test_classify_preview_article_recency_detects_same_day_and_old() -> None:
    same_day_status, same_day_detail = MODULE._classify_preview_article_recency(
        {
            "title": "某医院 AI 影像试点",
            "body_text": "发布于 2026年4月10日 上海某三甲医院启动 AI 影像试点项目",
        },
        now=datetime(2026, 4, 10, 10, 0, 0),
    )
    old_status, old_detail = MODULE._classify_preview_article_recency(
        {
            "title": "某医院 AI 影像试点",
            "body_text": "发布于 2026年4月8日 上海某三甲医院启动 AI 影像试点项目",
        },
        now=datetime(2026, 4, 10, 10, 0, 0),
    )

    assert same_day_status == "same_day"
    assert "2026-04-10" in same_day_detail
    assert old_status == "old"
    assert "2026-04-08" in old_detail


@pytest.mark.skipif(MODULE.Image is None, reason="Pillow unavailable for agent helper test")
def test_materialize_capture_variant_crops_right_focus(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    image = Image.new("RGB", (1000, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 280, 800), fill="black")
    draw.rectangle((420, 80, 960, 720), fill="gray")
    image.save(source)

    cropped = MODULE._materialize_capture_variant(
        source,
        variant_name="article_right_focus",
        temp_root=tmp_path,
    )

    assert cropped is not None
    assert cropped.exists()
    with Image.open(cropped) as cropped_image:
        assert cropped_image.size[0] < 1000
        assert cropped_image.size[1] < 800


def test_focus_article_body_view_uses_far_right_profile_for_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    clicks: list[tuple[int, int]] = []

    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE, "click_at", lambda x, y, **_kwargs: clicks.append((x, y)))
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    profile = MODULE._focus_article_body_view(
        wechat_app_name="WeChat",
        coordinate_mode="absolute",
        article_region={"x": 360, "y": 110, "width": 1020, "height": 860},
        reason="timeline_feed",
    )

    assert profile == "far_right"
    assert len(clicks) == 3
    assert clicks[0][0] > 1100


def test_run_cycle_uses_targeted_ocr_fallback_when_url_probe_has_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (None, {"accessibility_candidates": 0, "template_candidates": 0, "budget_exhausted": False}),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_capture(_region, output_path):
        output_path.write_bytes(b"x" * 4096)

    monkeypatch.setattr(MODULE, "capture_region", fake_capture)
    monkeypatch.setattr(MODULE, "to_base64", lambda _path: "ZmFrZQ==")
    resolve_calls: list[int] = []
    monkeypatch.setattr(
        MODULE,
        "request_ocr_preview",
        lambda *_args, **_kwargs: {
            "title": "项目调研纪要",
            "body_text": "该项目已进入方案评估阶段。正文信息完整，包含多句内容。该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
            "body_preview": "项目已进入方案评估阶段",
            "text_length": 128,
            "quality_ok": True,
            "quality_reason": "ok",
        },
    )
    monkeypatch.setattr(
        MODULE,
        "request_url_resolve",
        lambda *_args, **kwargs: (resolve_calls.append(int(kwargs.get("timeout_sec") or 0)) or {}),
    )
    monkeypatch.setattr(MODULE, "file_sha1", lambda _path: "sha1-demo")
    monkeypatch.setattr(MODULE, "file_perceptual_hash", lambda _path: None)

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        if route == "/api/collector/ocr/ingest":
            return {"item": {"id": "ocr-item-1"}, "deduplicated": False}
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_ocr"] == 1
    assert report["submitted_new"] == 1
    assert any(
        log["stage"] == "ocr_fallback" and log["detail"] == "targeted:url_probe_no_action_signal"
        for log in report["stage_logs"]
    )
    expected_candidate_limit, expected_timeout_sec, expected_skip_reason = MODULE._plan_preview_url_resolve_budget(
        preview={
            "title": "项目调研纪要",
            "body_text": "该项目已进入方案评估阶段。正文信息完整，包含多句内容。该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
            "body_preview": "项目已进入方案评估阶段",
            "text_length": 128,
        },
        title_hint="WeChat Auto 04-10 16:19 B1R1",
        targeted_fallback=True,
        targeted_timeout_sec=MODULE.DEFAULT_TARGETED_URL_RESOLVE_TIMEOUT_SEC,
    )
    assert expected_skip_reason is None
    assert expected_candidate_limit == 2
    assert resolve_calls == [expected_timeout_sec]


def test_run_cycle_browser_first_disables_ocr_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "article_url_strategy": "browser_first",
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": True,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (None, {"accessibility_candidates": 0, "template_candidates": 0, "budget_exhausted": False}),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        MODULE,
        "request_ocr_preview",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ocr preview should not run")),
    )

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["article_url_strategy"] == "browser_first"
    assert report["submitted"] == 0
    assert report["submitted_ocr"] == 0
    assert any(
        log["stage"] == "ocr_fallback" and log["detail"] == "disabled:url_only_mode"
        for log in report["stage_logs"]
    )


def test_run_cycle_skips_ocr_for_dark_blank_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (
            None,
            {
                "accessibility_candidates": 0,
                "template_candidates": 0,
                "budget_exhausted": False,
                "surface_state": "dark_blank",
            },
        ),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        MODULE,
        "request_ocr_preview",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ocr preview should not run")),
    )

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 0
    assert report["submitted_ocr"] == 0
    assert report["skipped_invalid_article"] == 1
    assert any(
        log["stage"] == "url_extract_surface" and log["detail"] == "dark_blank"
        for log in report["stage_logs"]
    )
    assert any(
        row["status"] == "skipped_invalid_article" and row["detail"] == "dark_blank_surface"
        for batch in report["batch_results"]
        for row in batch["rows"]
    )


def test_run_cycle_recovers_from_small_wechat_popup_window(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "_ensure_wechat_front_ready", lambda *_args, **_kwargs: (False, (0, 0, 280, 380)))
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (None, {"accessibility_candidates": 0, "template_candidates": 0, "budget_exhausted": False}),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_capture(_region, output_path):
        output_path.write_bytes(b"x" * 4096)

    monkeypatch.setattr(MODULE, "capture_region", fake_capture)
    monkeypatch.setattr(MODULE, "to_base64", lambda _path: "ZmFrZQ==")
    monkeypatch.setattr(
        MODULE,
        "request_ocr_preview",
        lambda *_args, **_kwargs: {
            "title": "项目调研纪要",
            "body_text": "该项目已进入方案评估阶段。正文信息完整，包含多句内容。该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
            "body_preview": "项目已进入方案评估阶段",
            "text_length": 128,
            "quality_ok": True,
            "quality_reason": "ok",
        },
    )
    monkeypatch.setattr(MODULE, "request_url_resolve", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(MODULE, "file_sha1", lambda _path: "sha1-demo")
    monkeypatch.setattr(MODULE, "file_perceptual_hash", lambda _path: None)

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        if route == "/api/collector/ocr/ingest":
            return {"item": {"id": "ocr-item-popup"}, "deduplicated": False}
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_ocr"] == 1


def test_run_cycle_prefers_browser_ingest_for_article_url(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_verify_retries": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(
        MODULE,
        "try_copy_current_article_url",
        lambda **_kwargs: "https://mp.weixin.qq.com/s/browser-ingest-direct",
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    route_calls: list[str] = []

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        route_calls.append(route)
        if route == "/api/collector/browser/ingest":
            return {
                "item": {"id": "browser-item-1"},
                "deduplicated": False,
                "ingest_route": "browser_plugin",
            }
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_url"] == 1
    assert route_calls == ["/api/collector/browser/ingest"]


def test_run_cycle_falls_back_to_url_ingest_when_browser_ingest_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_verify_retries": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(
        MODULE,
        "try_copy_current_article_url",
        lambda **_kwargs: "https://mp.weixin.qq.com/s/browser-ingest-fallback",
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    route_calls: list[str] = []

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        route_calls.append(route)
        if route == "/api/collector/browser/ingest":
            raise RuntimeError("404 not found")
        if route == "/api/collector/url/ingest":
            return {
                "item": {"id": "url-item-1"},
                "deduplicated": False,
                "ingest_route": "direct_url",
            }
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_url"] == 1
    assert route_calls == ["/api/collector/browser/ingest", "/api/collector/browser/ingest", "/api/collector/url/ingest"]
    assert any(
        log["stage"] == "url_ingest" and "browser_ingest_unavailable" in (log.get("detail") or "")
        for log in report["stage_logs"]
    )


def test_run_cycle_stops_profile_expansion_after_standard_template_only_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard", "wide", "compact"])
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    extract_calls: list[str] = []

    def fake_try_extract(**kwargs):
        extract_calls.append(str(kwargs.get("link_profile") or ""))
        return None, {"accessibility_candidates": 0, "template_candidates": 3, "budget_exhausted": False}

    monkeypatch.setattr(MODULE, "try_extract_article_url_from_wechat_ui", fake_try_extract)

    def fake_capture(_region, output_path):
        output_path.write_bytes(b"x" * 4096)

    monkeypatch.setattr(MODULE, "capture_region", fake_capture)
    monkeypatch.setattr(MODULE, "to_base64", lambda _path: "ZmFrZQ==")
    monkeypatch.setattr(
        MODULE,
        "request_ocr_preview",
        lambda *_args, **_kwargs: {
            "title": "项目调研纪要",
            "body_text": "该项目已进入方案评估阶段。正文信息完整，包含多句内容。该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
            "body_preview": "项目已进入方案评估阶段",
            "text_length": 128,
            "quality_ok": True,
            "quality_reason": "ok",
        },
    )
    monkeypatch.setattr(MODULE, "request_url_resolve", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(MODULE, "file_sha1", lambda _path: "sha1-demo")
    monkeypatch.setattr(MODULE, "file_perceptual_hash", lambda _path: None)

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        if route == "/api/collector/ocr/ingest":
            return {"item": {"id": "ocr-item-1"}, "deduplicated": False}
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert extract_calls == ["standard"]
    assert report["submitted"] == 1
    assert report["submitted_ocr"] == 1
    assert any(
        log["stage"] == "url_extract_profile_stop" and "template_only_no_accessibility" in (log.get("detail") or "")
        for log in report["stage_logs"]
    )


def test_run_cycle_skips_url_resolve_for_placeholder_preview_title(monkeypatch: pytest.MonkeyPatch) -> None:
    today = datetime.now().strftime("%Y年%-m月%-d日")
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (None, {"accessibility_candidates": 0, "template_candidates": 0, "budget_exhausted": False}),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_capture(_region, output_path):
        output_path.write_bytes(b"x" * 4096)

    monkeypatch.setattr(MODULE, "capture_region", fake_capture)
    monkeypatch.setattr(MODULE, "to_base64", lambda _path: "ZmFrZQ==")
    monkeypatch.setattr(
        MODULE,
        "request_ocr_preview",
        lambda *_args, **_kwargs: {
            "title": "WeChat Auto 04-10 16:19 B1R1",
            "body_text": f"发布于 {today}。项目进入方案评估阶段，正文仍较短，但已包含多句有效正文信息，可用于后续 OCR 入库和卡片生成。阅读 分享。",
            "body_preview": f"发布于 {today}。项目进入方案评估阶段",
            "text_length": 128,
            "quality_ok": True,
            "quality_reason": "ok",
        },
    )
    resolve_calls: list[int] = []
    monkeypatch.setattr(
        MODULE,
        "request_url_resolve",
        lambda *_args, **kwargs: (resolve_calls.append(int(kwargs.get("timeout_sec") or 0)) or {}),
    )
    monkeypatch.setattr(MODULE, "file_sha1", lambda _path: "sha1-demo")
    monkeypatch.setattr(MODULE, "file_perceptual_hash", lambda _path: None)

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        if route == "/api/collector/ocr/ingest":
            return {"item": {"id": "ocr-item-skip"}, "deduplicated": False}
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_ocr"] == 1
    assert resolve_calls == []
    assert any(log["stage"] == "url_resolve_skip" for log in report["stage_logs"])


@pytest.mark.skipif(MODULE.Image is None, reason="Pillow unavailable for agent helper test")
def test_run_cycle_retries_with_capture_variant_after_timeline_preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (None, {"accessibility_candidates": 0, "template_candidates": 0, "budget_exhausted": False}),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_capture(_region, output_path):
        image = Image.new("RGB", (1000, 800), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 300, 800), fill="black")
        draw.rectangle((360, 60, 950, 740), fill="gray")
        image.save(output_path)

    monkeypatch.setattr(MODULE, "capture_region", fake_capture)
    preview_calls: list[str] = []

    def fake_preview(*_args, **_kwargs):
        preview_calls.append("preview")
        if len(preview_calls) == 1:
            return {
                "title": "01:13",
                "body_text": "01:13 01:53 昨天 23:35 00:08 00:03 昨天 22:41 昨天 21:05 昨天 20:57 昨天 19:33",
                "body_preview": "01:13 01:53 昨天 23:35 00:08",
                "text_length": 180,
                "quality_ok": False,
                "quality_reason": "timeline_feed",
            }
        return {
            "title": "项目调研纪要",
            "body_text": "该项目已进入方案评估阶段。正文信息完整，包含多句内容。该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
            "body_preview": "项目已进入方案评估阶段",
            "text_length": 128,
            "quality_ok": True,
            "quality_reason": "ok",
        }

    monkeypatch.setattr(MODULE, "request_ocr_preview", fake_preview)
    monkeypatch.setattr(MODULE, "request_url_resolve", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(MODULE, "file_sha1", lambda _path: f"sha1-{_path.stem}")
    monkeypatch.setattr(MODULE, "file_perceptual_hash", lambda _path: None)

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        if route == "/api/collector/ocr/ingest":
            return {"item": {"id": "ocr-item-variant"}, "deduplicated": False}
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_ocr"] == 1
    assert len(preview_calls) == 2
    assert any(log["stage"] == "capture_variant" for log in report["stage_logs"])


def test_run_cycle_refocuses_article_body_after_invalid_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    config = dict(MODULE.DEFAULT_CONFIG)
    config.update(
        {
            "rows_per_batch": 1,
            "batches_per_cycle": 1,
            "article_allow_ocr_fallback": False,
            "article_allow_targeted_ocr_fallback": True,
            "article_verify_retries": 1,
            "min_capture_file_size_kb": 1,
        }
    )
    state = {"processed_hashes": {}}

    monkeypatch.setattr(MODULE, "_check_required_binaries", lambda: None)
    monkeypatch.setattr(MODULE, "activate_wechat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "wait_for_front_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(MODULE, "switch_to_main_wechat_window", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_usable_window_rect", lambda *_args, **_kwargs: (True, (0, 0, 1440, 900)))
    monkeypatch.setattr(MODULE, "resolve_point", lambda x, y, **_kwargs: (x, y))
    monkeypatch.setattr(MODULE, "click_at", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_code", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "key_combo_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "get_front_process_name", lambda: "WeChat")
    monkeypatch.setattr(MODULE, "wait_for_article_destination", lambda *_args, **_kwargs: ("WeChat", ["WeChat"]))
    monkeypatch.setattr(MODULE, "try_copy_current_article_url", lambda **_kwargs: None)
    monkeypatch.setattr(MODULE, "_expand_article_link_profiles", lambda *_args, **_kwargs: ["standard"])
    monkeypatch.setattr(
        MODULE,
        "try_extract_article_url_from_wechat_ui",
        lambda **_kwargs: (None, {"accessibility_candidates": 0, "template_candidates": 0, "budget_exhausted": False}),
    )
    monkeypatch.setattr(MODULE, "resolve_region", lambda region, **_kwargs: region)
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(MODULE, "_select_capture_variant_profiles", lambda _reason: [])

    def fake_capture(_region, output_path):
        output_path.write_bytes(b"x" * 4096)

    monkeypatch.setattr(MODULE, "capture_region", fake_capture)
    monkeypatch.setattr(MODULE, "to_base64", lambda path: path.stem)
    monkeypatch.setattr(MODULE, "file_sha1", lambda path: f"sha1-{path.stem}")
    monkeypatch.setattr(MODULE, "file_perceptual_hash", lambda _path: None)

    focus_reasons: list[str] = []
    monkeypatch.setattr(
        MODULE,
        "_focus_article_body_view",
        lambda **kwargs: (focus_reasons.append(str(kwargs.get("reason") or "")) or "far_right"),
    )

    preview_calls: list[str] = []

    def fake_preview(*_args, **kwargs):
        preview_calls.append(str(kwargs.get("image_base64") or ""))
        if "focus" in preview_calls[-1]:
            return {
                "title": "项目调研纪要",
                "body_text": "该项目已进入方案评估阶段。正文信息完整，包含多句内容。该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
                "body_preview": "项目已进入方案评估阶段",
                "text_length": 128,
                "quality_ok": True,
                "quality_reason": "ok",
            }
        return {
            "title": "01:13",
            "body_text": "01:13 01:53 昨天 23:35 00:08 00:03 昨天 22:41 昨天 21:05 昨天 20:57",
            "body_preview": "01:13 01:53 昨天 23:35 00:08",
            "text_length": 180,
            "quality_ok": False,
            "quality_reason": "timeline_feed",
        }

    monkeypatch.setattr(MODULE, "request_ocr_preview", fake_preview)
    monkeypatch.setattr(MODULE, "request_url_resolve", lambda *_args, **_kwargs: {})

    def fake_post_json(_api_base, route, _payload, timeout_sec=120):
        assert timeout_sec >= 0
        if route == "/api/collector/ocr/ingest":
            return {"item": {"id": "ocr-item-refocus"}, "deduplicated": False}
        raise AssertionError(f"unexpected route: {route}")

    monkeypatch.setattr(MODULE, "post_json", fake_post_json)

    report = MODULE.run_cycle(config, state, max_items=1)

    assert report["submitted"] == 1
    assert report["submitted_ocr"] == 1
    assert report["captured"] == 2
    assert focus_reasons == ["ocr_quality:timeline_feed"]
    assert len(preview_calls) == 2
    assert any(log["stage"] == "article_refocus" for log in report["stage_logs"])



def test_validate_article_preview_rejects_public_account_hub() -> None:
    ok, reason = MODULE.validate_article_preview(
        {
            "title": "某公众号主页",
            "body_text": "查看历史消息 全部消息 进入公众号 最近更新 相关文章",
            "text_length": 120,
            "quality_ok": True,
        },
        min_text_length=80,
    )

    assert ok is False
    assert reason.startswith("non_article_hub")


def test_validate_article_preview_rejects_image_viewer() -> None:
    ok, reason = MODULE.validate_article_preview(
        {
            "title": "图片详情",
            "body_text": "保存图片 识别图中二维码 轻触两下关闭 下一张",
            "text_length": 96,
            "quality_ok": True,
        },
        min_text_length=80,
    )

    assert ok is False
    assert reason.startswith("image_viewer")
