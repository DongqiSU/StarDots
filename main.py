"""Stardot 的启动入口：uv run main.py。"""

import sys


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        # windowed EXE 没有控制台：导入失败也写报告，避免只弹出不可诊断的窗口。
        import json
        from pathlib import Path
        import traceback
        report = Path(sys.argv[2]).resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"ok": False, "stage": "import"}), encoding="utf-8")
        try:
            from stardot.smoke import run_smoke_test
            result = run_smoke_test(str(report))
        except Exception:
            report.write_text(json.dumps({"ok": False, "error": traceback.format_exc()}), encoding="utf-8")
            result = 1
        raise SystemExit(result)
    else:
        from stardot.app import main
        raise SystemExit(main())
