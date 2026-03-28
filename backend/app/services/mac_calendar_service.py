from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
import subprocess

from app.models.entities import FocusSession
from app.services.language import localized_text, normalize_output_language


DEFAULT_CALENDAR_NAME = "Anti-FOMO"
DEFAULT_EVENT_DURATION_MINUTES = 45
DEFAULT_DAY_START_HOUR = 9
DEFAULT_DAY_END_HOUR = 17


@dataclass(slots=True)
class TodoCalendarEventDraft:
    title: str
    notes: str
    start_time: datetime
    end_time: datetime


@dataclass(slots=True)
class TodoCalendarPreview:
    calendar_name: str
    summary_title: str
    task_count: int
    tasks: list[str]
    events: list[TodoCalendarEventDraft]
    markdown: str


def extract_todo_items(markdown: str) -> list[str]:
    items: list[str] = []
    for raw_line in str(markdown or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^[-*]\s+\[(?: |x|X)\]\s+(.+)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            items.append(value)
    return items


def _next_business_day(start_day: date) -> date:
    day = start_day
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _build_event_title(goal_text: str | None, item: str, index: int) -> str:
    goal = (goal_text or "").strip()
    prefix = f"Anti-FOMO {goal}" if goal else "Anti-FOMO 待办"
    title = f"{prefix} · {item}".strip()
    if len(title) > 96:
        title = title[:95].rstrip() + "…"
    return title or f"Anti-FOMO 待办 {index}"


def _build_event_notes(
    session: FocusSession,
    *,
    item: str,
    todo_markdown: str,
    output_language: str,
    index: int,
    total: int,
) -> str:
    resolved_language = normalize_output_language(output_language)
    goal = (session.goal_text or "").strip() or localized_text(
        resolved_language,
        {
            "zh-CN": "未设置目标",
            "zh-TW": "未設定目標",
            "en": "No goal set",
            "ja": "目標未設定",
            "ko": "목표 미설정",
        },
        "未设置目标",
    )
    lines = [
        f"{localized_text(resolved_language, {'zh-CN': '任务', 'zh-TW': '任務', 'en': 'Task', 'ja': 'タスク', 'ko': '작업'}, '任务')} {index}/{total}: {item}",
        f"{localized_text(resolved_language, {'zh-CN': '专注目标', 'zh-TW': '專注目標', 'en': 'Focus Goal', 'ja': '集中目標', 'ko': '집중 목표'}, '专注目标')}: {goal}",
        f"{localized_text(resolved_language, {'zh-CN': 'Session 时长', 'zh-TW': 'Session 時長', 'en': 'Session Duration', 'ja': 'Session 時間', 'ko': 'Session 시간'}, 'Session 时长')}: {session.duration_minutes}",
        "",
        localized_text(
            resolved_language,
            {
                "zh-CN": "原始待办草稿：",
                "zh-TW": "原始待辦草稿：",
                "en": "Original todo draft:",
                "ja": "元の TODO 草稿:",
                "ko": "원본 할 일 초안:",
            },
            "原始待办草稿：",
        ),
        todo_markdown.strip(),
    ]
    return "\n".join(lines).strip()


def build_todo_calendar_preview(
    *,
    session: FocusSession,
    todo_markdown: str,
    output_language: str = "zh-CN",
    calendar_name: str | None = None,
) -> TodoCalendarPreview:
    resolved_language = normalize_output_language(output_language)
    tasks = extract_todo_items(todo_markdown)
    if not tasks:
        fallback = localized_text(
            resolved_language,
            {
                "zh-CN": "复盘本轮重点内容并整理下一步行动",
                "zh-TW": "回顧本輪重點內容並整理下一步行動",
                "en": "Review this focus block and define the next action",
                "ja": "今回の集中を振り返り次のアクションを整理する",
                "ko": "이번 집중 세션을 복기하고 다음 행동을 정리하기",
            },
            "复盘本轮重点内容并整理下一步行动",
        )
        tasks = [fallback]

    local_now = datetime.now().astimezone()
    first_day = _next_business_day(local_now.date() + timedelta(days=1))
    slot_time = datetime.combine(first_day, time(hour=DEFAULT_DAY_START_HOUR, minute=0), tzinfo=local_now.tzinfo)

    events: list[TodoCalendarEventDraft] = []
    for index, item in enumerate(tasks, start=1):
        if slot_time.hour >= DEFAULT_DAY_END_HOUR:
            next_day = _next_business_day(slot_time.date() + timedelta(days=1))
            slot_time = datetime.combine(
                next_day,
                time(hour=DEFAULT_DAY_START_HOUR, minute=0),
                tzinfo=local_now.tzinfo,
            )
        start_time = slot_time
        end_time = start_time + timedelta(minutes=DEFAULT_EVENT_DURATION_MINUTES)
        slot_time = start_time + timedelta(hours=1)
        events.append(
            TodoCalendarEventDraft(
                title=_build_event_title(session.goal_text, item, index),
                notes=_build_event_notes(
                    session,
                    item=item,
                    todo_markdown=todo_markdown,
                    output_language=resolved_language,
                    index=index,
                    total=len(tasks),
                ),
                start_time=start_time,
                end_time=end_time,
            )
        )

    goal = (session.goal_text or "").strip()
    summary_title = (
        f"Anti-FOMO 待办导入 · {goal}" if goal else "Anti-FOMO 待办导入"
    )
    return TodoCalendarPreview(
        calendar_name=(calendar_name or DEFAULT_CALENDAR_NAME).strip() or DEFAULT_CALENDAR_NAME,
        summary_title=summary_title,
        task_count=len(tasks),
        tasks=tasks,
        events=events,
        markdown=todo_markdown,
    )


def _run_osascript(script: str, args: list[str]) -> str:
    run = subprocess.run(
        ["osascript", "-e", script, *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if run.returncode != 0:
        message = (run.stderr or run.stdout or "").strip() or "osascript failed"
        raise RuntimeError(message)
    return (run.stdout or "").strip()


def import_todo_preview_to_mac_calendar(preview: TodoCalendarPreview) -> list[str]:
    imported_titles: list[str] = []
    script = """
on run argv
  set calendarName to item 1 of argv
  set eventTitle to item 2 of argv
  set eventNotes to item 3 of argv
  set y1 to (item 4 of argv) as integer
  set m1 to (item 5 of argv) as integer
  set d1 to (item 6 of argv) as integer
  set hh1 to (item 7 of argv) as integer
  set mm1 to (item 8 of argv) as integer
  set y2 to (item 9 of argv) as integer
  set m2 to (item 10 of argv) as integer
  set d2 to (item 11 of argv) as integer
  set hh2 to (item 12 of argv) as integer
  set mm2 to (item 13 of argv) as integer

  tell application "Calendar"
    activate
    if not (exists calendar calendarName) then
      make new calendar at end of calendars with properties {name:calendarName}
    end if
    tell calendar calendarName
      set startDate to current date
      set year of startDate to y1
      set month of startDate to m1
      set day of startDate to d1
      set hours of startDate to hh1
      set minutes of startDate to mm1
      set seconds of startDate to 0

      set endDate to current date
      set year of endDate to y2
      set month of endDate to m2
      set day of endDate to d2
      set hours of endDate to hh2
      set minutes of endDate to mm2
      set seconds of endDate to 0

      make new event with properties {summary:eventTitle, start date:startDate, end date:endDate, description:eventNotes}
    end tell
  end tell
  return eventTitle
end run
""".strip()

    for event in preview.events:
        start_local = event.start_time.astimezone()
        end_local = event.end_time.astimezone()
        title = _run_osascript(
            script,
            [
                preview.calendar_name,
                event.title,
                event.notes,
                str(start_local.year),
                str(start_local.month),
                str(start_local.day),
                str(start_local.hour),
                str(start_local.minute),
                str(end_local.year),
                str(end_local.month),
                str(end_local.day),
                str(end_local.hour),
                str(end_local.minute),
            ],
        )
        imported_titles.append(title or event.title)
    return imported_titles
