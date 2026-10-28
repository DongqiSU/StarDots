from datetime import datetime
import unittest

from stardot.text_processing import capture_text, due_display, parse_schedule, shift_schedule, summarize, validate_schedule


class TextProcessingTests(unittest.TestCase):
    reference = datetime(2026, 9, 16, 10, 30)

    def test_explicit_dates_and_times(self):
        cases = [
            ("明天开会", "2026-09-17", None),
            ("今天15:30讨论", "2026-09-16", "15:30"),
            ("明天下午三点半讨论预算", "2026-09-17", "15:30"),
            ("下周一上午九点十分开会", "2026-09-21", "09:10"),
            ("9月18日09:00提交报告", "2026-09-18", "09:00"),
            ("2028-02-29 18:05做记录", "2028-02-29", "18:05"),
            ("2026年9月18日下午三点", "2026-09-18", "15:00"),
            ("本周一下午两点", "2026-09-14", "14:00"),
            ("周一下午两点", "2026-09-21", "14:00"),
            ("后天下午三点", "2026-09-18", "15:00"),
            ("明天下午开会", "2026-09-17", None),
            ("明天会议持续3小时", "2026-09-17", None),
            ("明天三点开会", "2026-09-17", None),
            ("明天晚上十二点", "2026-09-17", None),
            ("下星期一下午三点一刻", "2026-09-21", "15:15"),
            ("下周星期一下午三点三刻", "2026-09-21", "15:45"),
        ]
        for text, day, time in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_schedule(text, self.reference)[:2], (day, time))

    def test_ambiguity_does_not_pick_first_date(self):
        cases = ["明天或后天开会", "9月18日至20日出差", "每周五开会", "大概明天下午三点",
                 "下下周一开会", "2026-02-30开会", "明后天交稿", "会议持续3小时",
                 "版本3.14", "大后天开会", "15:30开会", "3-5个工作日", "2026-09-1812编号"]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_schedule(text, self.reference)[:2], (None, None))
        self.assertEqual(parse_schedule("明天14:00到16:00开会", self.reference)[:2],
                         ("2026-09-17", None))

    def test_summary_preserves_conditions_negation_and_details(self):
        source = "大家好！\n任务：如果方案没通过，不要发送预算；先找小王核实。\n谢谢大家！"
        self.assertEqual(summarize(source), "如果方案没通过，不要发送预算；先找小王核实。")
        long_text = "请保持原文信息完整，地点在三楼，不要遗漏第二项。\n" * 80
        self.assertEqual(summarize(long_text), long_text.strip())
        self.assertEqual(summarize("文件名是谢谢。"), "文件名是谢谢。")
        self.assertEqual(summarize("你好世界程序需要修复"), "你好世界程序需要修复")
        result = capture_text("提醒：明天下午三点带预算表开会。谢谢！", self.reference)
        self.assertEqual(result.body, "明天下午三点带预算表开会。")
        self.assertEqual((result.due_date, result.due_time), ("2026-09-17", "15:00"))

    def test_rollover_and_color_boundaries(self):
        self.assertEqual(shift_schedule("2028-01-31", None, "month", 1), ("2028-02-29", None))
        self.assertEqual(shift_schedule("2028-02-29", "23:59", "minute", 1), ("2028-03-01", "00:00"))
        self.assertEqual(shift_schedule("2028-02-29", None, "year", 1), ("2029-02-28", None))
        self.assertEqual(shift_schedule("2026-12-31", None, "day", 1), ("2027-01-01", None))
        self.assertEqual(due_display("2026-09-16", "09:00", self.reference)[1], "#302a24")
        self.assertEqual(due_display("2026-09-16", None, self.reference)[1], "#c77c2c")
        self.assertEqual(due_display("2026-09-17", None, self.reference)[1], "#a18a2b")
        self.assertEqual(due_display("2026-09-18", None, self.reference)[1], "#879344")
        self.assertEqual(due_display("2026-09-16", "15:00", self.reference)[0], "15:00")

    def test_manual_date_validation(self):
        self.assertEqual(validate_schedule("2028-02-29", ""), ("2028-02-29", None))
        for values in [(None, "15:00"), ("2026-02-29", None), ("2026-9-16", None),
                       ("2026-09-16", "25:00"), ("2026-09-16", "12:60")]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_schedule(*values)
