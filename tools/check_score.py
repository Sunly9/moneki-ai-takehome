"""读评测报告，断言总分不低于下限。CI 与本地都能用。

    python tools/check_score.py eval_reports/latest --min-score 99

分数掉下来就返回非零退出码，CI 直接红。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="校验评测报告的总分下限")
    parser.add_argument("report", help="报告目录或 report.json 路径")
    parser.add_argument("--min-score", type=float, default=99.0, help="总分下限，默认 99")
    args = parser.parse_args()

    path = Path(args.report)
    if path.is_dir():
        path = path / "report.json"
    if not path.exists():
        print("找不到报告：%s" % path, file=sys.stderr)
        return 2

    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)

    total = report.get("total") or {}
    earned = float(total.get("earned") or 0.0)
    points = float(total.get("points") or 0.0)
    failed = [q["id"] for q in report.get("questions", []) if not q.get("passed")]

    print("%s：总分 %.2f / %.2f（%.1f%%）" % (path, earned, points, (earned / points * 100) if points else 0.0))
    print("未通过：%s" % (" ".join(failed) or "无"))
    for name, item in (report.get("per_category") or {}).items():
        print("  %-12s %6.2f / %-6.2f  (%d/%d)" % (
            name, item["earned"], item["points"], item["passed"], item["questions"]
        ))

    if earned < args.min_score:
        print("分数低于下限 %.1f：实际 %.2f" % (args.min_score, earned), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
