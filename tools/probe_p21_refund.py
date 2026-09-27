"""临时探针 2：M03 差异 + 非法日期。"""

from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "pos.db"
CURRENCY = str.maketrans("", "", "¥￥ \t\u3000")
ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def main() -> int:
    conn = sqlite3.connect(SRC.as_posix())
    conn.row_factory = sqlite3.Row

    print("-- 可疑 ISO 日期（月/日越界）--")
    bad = 0
    for r in conn.execute("SELECT date, COUNT(*) c FROM sales GROUP BY date"):
        m = ISO_RE.match((r["date"] or "").strip())
        if m:
            y, mo, d = (int(x) for x in m.groups())
            if not (1 <= mo <= 12 and 1 <= d <= 31):
                print("   %-14r x%d" % (r["date"], r["c"]))
                bad += r["c"]
    print("   合计行数：%d" % bad)

    print("\n-- 所有 date 里不含预期分隔的写法 --")
    for r in conn.execute(
        "SELECT date, COUNT(*) c FROM sales WHERE date NOT LIKE '____-__-__' AND date NOT LIKE '____/__/__' AND date NOT LIKE '__-__-____' GROUP BY date"
    ):
        print("   %-14r x%d" % (r["date"], r["c"]))

    print("\n-- 8 月 P21（含大小写变体）全部行 --")
    rows = list(
        conn.execute(
            "SELECT order_id, date, store_id, product_id, qty, amount, payment FROM sales "
            "WHERE UPPER(TRIM(product_id))='P21'"
        )
    )
    print("   P21 总行数：%d" % len(rows))
    neg = [r for r in rows if (r["amount"] or "").translate(CURRENCY).strip().startswith("-")]
    print("   P21 负金额行：%d" % len(neg))
    for r in neg:
        print("      %s | %s | %s | qty=%s | amount=%r | %s" % (r["order_id"], r["date"], r["store_id"], r["qty"], r["amount"], r["payment"]))

    print("\n-- P21 各 date 写法分布 --")
    c = Counter()
    for r in rows:
        t = (r["date"] or "").strip()
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", t):
            c["YYYY-MM-DD"] += 1
        elif re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", t):
            c["YYYY/M/D"] += 1
        elif re.match(r"^\d{1,2}-\d{1,2}-\d{4}$", t):
            c["DD-MM-YYYY"] += 1
        else:
            c["bad:%r" % t] += 1
    for k, v in c.most_common():
        print("   %-14s %d" % (k, v))

    print("\n-- P21 amount 形态 --")
    c = Counter()
    for r in rows:
        t = (r["amount"] or "").translate(CURRENCY).strip()
        if not t:
            c["empty"] += 1
        elif t.startswith("¥"):
            c["yen"] += 1
        else:
            c["plain"] += 1
    for k, v in c.most_common():
        print("   %-14s %d" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
