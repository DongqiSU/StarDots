"""保守的本地文字整理与明确日期解析，不上传内容、不截断任务语义。"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re


@dataclass(frozen=True)
class Capture:
    body: str
    due_date: str | None
    due_time: str | None
    note: str = ""


def summarize(text: str) -> str:
    """去掉确定的包裹语；无法安全精简时保留全文，不挑一半任务。"""
    body = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n[ \t]*\n+", "\n", body)
    body = re.sub(r"^(?:大家好|你好|您好)[，,:：!！。\n]+\s*", "", body)
    body = re.sub(r"^(?:待办|任务|提醒|通知)[：:]\s*", "", body)
    body = re.sub(r"([。！!\n])\s*(?:谢谢(?:大家)?|辛苦了)[！!。.\s]*$", r"\1", body)
    return body.strip() or text.strip()


DATE_PATTERN = re.compile(
    r"(?<![\d/年月-])(?:(?P<year>\d{4})(?P<ys>年|[-/]))?"
    r"(?P<month>\d{1,2})(?P<ms>月|/|-)(?P<day>\d{1,2})(?:日|号)?(?![\d/])"
)
RELATIVE_PATTERN = re.compile(r"(?<![大明])(?P<relative>今天|明天|后天)")
WEEK_PATTERN = re.compile(r"(?<![上下每])(?P<week>本周|这周|下周|本星期|这星期|下星期|周|星期)(?:星期)?(?P<weekday>[一二三四五六日天])")
NUMBER = r"[零〇一二两三四五六七八九十\d]{1,3}"
TIME_PATTERN = re.compile(
    rf"(?<![\d:：])(?P<period>凌晨|早上|早晨|上午|中午|下午|晚上|晚间)?\s*"
    rf"(?P<hour>{NUMBER})(?:(?P<colon>[:：])(?P<minute>\d{{2}})(?!\d)"
    rf"|[点时](?!长|间|候)(?:(?P<half>半)|(?P<quarter>一刻|三刻)|(?P<cnminute>{NUMBER})分?)?)(?!\d)"
)


def _number(text: str) -> int:
    if text.isdigit():
        return int(text)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if "十" in text:
        left, right = text.split("十", 1)
        return (digits[left] if left else 1) * 10 + (digits[right] if right else 0)
    return digits[text]


def parse_schedule(text: str, reference: datetime) -> tuple[str | None, str | None, str]:
    """相对日期固定以本次录入时间计算；不猜时段，不选多个候选中的第一个。"""
    if re.search(r"每[天周月年]|每逢|工作日|隔周|大概|可能|左右|待定|不确定|前后|明后天|下下周", text):
        return None, None, "含模糊或重复安排，请手动设置日期。"
    candidates: list[date] = []
    spans: list[tuple[int, int]] = []
    invalid = False
    for match in DATE_PATTERN.finditer(text):
        # 不把 3-5 个工作日、9/18 的评分之类直接当作日期。
        if match["ms"] == "-" and not match["year"]:
            continue
        if re.match(r"\s*(?:个|天|小时|分数|得分)", text[match.end():]):
            continue
        try:
            candidates.append(date(int(match["year"] or reference.year),
                                   int(match["month"]), int(match["day"])))
        except ValueError:
            invalid = True
        spans.append(match.span())
    for match in RELATIVE_PATTERN.finditer(text):
        offset = {"今天": 0, "明天": 1, "后天": 2}[match["relative"]]
        candidates.append(reference.date() + timedelta(days=offset))
        spans.append(match.span())
    for match in WEEK_PATTERN.finditer(text):
        weekday = "一二三四五六日".index(match["weekday"].replace("天", "日"))
        if match["week"].startswith(("本", "这", "下")):
            offset = weekday - reference.weekday() + (7 if match["week"].startswith("下") else 0)
        else:
            offset = (weekday - reference.weekday()) % 7
        candidates.append(reference.date() + timedelta(days=offset))
        spans.append(match.span())
    # 例如“9月18日至20日”：第二个省略月份的日期也构成歧义。
    leftover = list(text)
    for start, end in spans:
        leftover[start:end] = " " * (end - start)
    if re.search(r"\d{1,2}(?:日|号)", "".join(leftover)):
        invalid = True
    if invalid or len(candidates) != 1:
        note = "日期不唯一或无法确认，请手动设置。" if invalid or candidates else ""
        return None, None, note

    due_date = candidates[0].isoformat()
    matches = list(TIME_PATTERN.finditer(text))
    if not matches:
        return due_date, None, ""
    if len(matches) != 1:
        return due_date, None, "保留日期，多个时刻请手动选择。"
    match = matches[0]
    try:
        hour = _number(match["hour"])
        minute = (30 if match["half"] else {"一刻": 15, "三刻": 45}[match["quarter"]]
                  if match["quarter"] else _number(match["minute"] or match["cnminute"] or "0"))
        period = match["period"]
        if period in ("下午", "晚上", "晚间"):
            if not 1 <= hour <= 12 or (period != "下午" and hour == 12):
                raise ValueError
            hour = hour + 12 if hour < 12 else hour
        elif period in ("凌晨", "早上", "早晨", "上午"):
            if not 0 <= hour <= 11:
                raise ValueError
        elif period == "中午":
            if hour == 1:
                hour = 13
            elif hour not in (11, 12):
                raise ValueError
        elif not match["colon"] and 1 <= hour <= 12:
            raise ValueError  # “三点”没有说明上午或下午。
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError
    except (KeyError, ValueError):
        return due_date, None, "保留日期，时刻不明确，请手动设置。"
    return due_date, f"{hour:02d}:{minute:02d}", ""


def capture_text(text: str, reference: datetime) -> Capture:
    due_date, due_time, note = parse_schedule(text, reference)
    return Capture(summarize(text), due_date, due_time, note)


def validate_schedule(due_date: str | None, due_time: str | None) -> tuple[str | None, str | None]:
    if not due_date:
        if due_time:
            raise ValueError("请先设置日期，再设置时刻。")
        return None, None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
        raise ValueError("日期请使用 YYYY-MM-DD 格式。")
    try:
        date.fromisoformat(due_date)
    except ValueError:
        raise ValueError("这个日期不存在，请检查年月日。") from None
    if due_time and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", due_time):
        raise ValueError("时刻请使用 HH:MM 格式，例如 15:30。")
    return due_date, due_time or None


def shift_schedule(due_date: str, due_time: str | None, part: str, step: int):
    day = date.fromisoformat(due_date)
    if part in ("year", "month"):
        months = day.year * 12 + day.month - 1 + step * (12 if part == "year" else 1)
        year, month = divmod(months, 12)
        month += 1
        day = date(year, month, min(day.day, monthrange(year, month)[1]))
    elif part == "day":
        day += timedelta(days=step)
    elif part in ("hour", "minute") and due_time:
        stamp = datetime.fromisoformat(f"{due_date}T{due_time}")
        stamp += timedelta(minutes=step * (60 if part == "hour" else 1))
        return stamp.date().isoformat(), stamp.strftime("%H:%M")
    return day.isoformat(), due_time


def due_display(due_date: str | None, due_time: str | None, now: datetime):
    if not due_date:
        return "", "#a38b76", ""
    day = date.fromisoformat(due_date)
    days = (day - now.date()).days
    overdue = days < 0 or (days == 0 and due_time and
                          datetime.fromisoformat(f"{due_date}T{due_time}") < now)
    color = "#302a24" if overdue else ("#c77c2c" if days == 0 else "#a18a2b" if days == 1 else "#879344")
    label = due_time if days == 0 and due_time else f"{day.month}/{day.day}" + (f" {due_time}" if due_time else "")
    return label, color, due_date + (f" {due_time}" if due_time else "")
