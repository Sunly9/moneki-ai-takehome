"""临时探针：按 KB-001 §2/§3/§4 从原始 pos.db 重算，验证口径理解。

不属于交付物，放在 scratch/（已 gitignore）。用完删。
"""

from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "pos.db"

CURRENCY = str.maketrans("", "", "¥￥ \t\u3000")

ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
SLASH_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
DMY_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")


def norm_id(value) -> str:
    return (value or "").strip().upper()


def parse_date(value):
    """KB-001 §2.2：YYYY-MM-DD、YYYY/M/D、DD-MM-YYYY（日在前）。要做范围校验。"""
    text = (value or "").strip()
    if not text:
        return None, None
    for rx, fmt, order in ((ISO_RE, "YYYY-MM-DD", "ymd"), (SLASH_RE, "YYYY/M/D", "ymd"), (DMY_RE, "DD-MM-YYYY", "dmy")):
        m = rx.match(text)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        y, mo, d = (a, b, c) if order == "ymd" else (c, b, a)
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None, "bad"
        try:
            from datetime import date as _date

            _date(y, mo, d)
        except ValueError:
            return None, "bad"
        return f"{y:04d}-{mo:02d}-{d:02d}", fmt
    return None, "bad"


def parse_amount(value):
    text = (value or "").translate(CURRENCY).strip()
    if not text:
        return None, "empty"
    try:
        return int((Decimal(text) * 100).to_integral_value()), "ok"
    except (InvalidOperation, ValueError):
        return None, "bad"


def parse_qty(value):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def main() -> int:
    conn = sqlite3.connect(SRC.as_posix())
    conn.row_factory = sqlite3.Row

    stores = {norm_id(r["store_id"]) for r in conn.execute("SELECT store_id FROM stores")}
    products = {norm_id(r["product_id"]) for r in conn.execute("SELECT product_id FROM products")}

    raw = list(conn.execute("SELECT order_id, date, store_id, product_id, qty, amount, payment FROM sales"))
    print("原始行数：%d" % len(raw))

    date_fmt = Counter()
    amount_shape = Counter()
    store_raw = Counter()
    product_raw = Counter()
    qty_bad = 0

    removed = Counter()
    kept = []
    seen = set()
    for row in raw:
        iso, fmt = parse_date(row["date"])
        date_fmt[fmt] += 1
        cents, status = parse_amount(row["amount"])
        amount_shape[status] += 1
        if status == "ok":
            amount_shape["neg" if cents < 0 else ("zero" if cents == 0 else "pos")] += 1
        sid = norm_id(row["store_id"])
        pid = norm_id(row["product_id"])
        store_raw[row["store_id"]] += 1
        product_raw[row["product_id"]] += 1
        qty = parse_qty(row["qty"])
        if qty is None:
            qty_bad += 1

        if fmt in (None, "bad"):
            removed["1_unparseable_date"] += 1
            continue
        if status == "empty":
            removed["2_empty_amount"] += 1
            continue
        if status == "bad":
            removed["2b_amount_unparseable"] += 1
            continue
        if qty is None or qty <= 0:
            removed["3_qty_le_zero"] += 1
            continue
        if sid not in stores:
            removed["4_store_not_in_stores"] += 1
            continue
        if pid not in products:
            removed["5_product_not_in_products"] += 1
            continue
        key = (sid, iso, pid, qty, cents, (row["payment"] or "").strip(), (row["order_id"] or "").strip())
        if key in seen:
            removed["6_duplicate_row"] += 1
            continue
        seen.add(key)
        kept.append(key)

    print("\n-- 日期格式分布 --")
    for k, v in date_fmt.most_common():
        print("  %-12s %d" % (k, v))
    print("\n-- 金额形态 --")
    for k, v in amount_shape.most_common():
        print("  %-12s %d" % (k, v))
    print("\n-- store_id 原始写法（前 15）--")
    for k, v in store_raw.most_common(15):
        print("  %-12r %d" % (k, v))
    print("\n-- product_id 原始写法（前 10）--")
    for k, v in product_raw.most_common(10):
        print("  %-12r %d" % (k, v))
    print("\nqty 解析失败：%d" % qty_bad)

    print("\n-- 剔除统计 --")
    for k in sorted(removed):
        print("  %-26s %d" % (k, removed[k]))
    print("  保留行数：%d" % len(kept))

    # 指标（全区间 + 6 月）
    def metrics(rows, start, end, store=None, product=None):
        sales = [r for r in rows if start <= r[1] <= end and (store is None or r[0] == store) and (product is None or r[2] == product)]
        pos = [r for r in sales if r[4] > 0]
        neg = [r for r in sales if r[4] < 0]
        net = sum(r[4] for r in sales) / 100
        refund = abs(sum(r[4] for r in neg)) / 100
        orders = len({r[6] for r in pos})
        qty = sum(r[3] for r in pos) - sum(r[3] for r in neg)
        aov = round(net / orders, 2) if orders else None
        return dict(net_revenue=net, refund_amount=refund, orders=orders, qty=qty, aov=aov)

    print("\n-- 6 月全店 --")
    print("  ", metrics(kept, "2026-06-01", "2026-06-30"))
    print("  期望(题库 M01)：net 156757.0 refund 953.0 orders 4311 qty 6496 aov 36.36")
    print("\n-- 7 月 S02 --")
    print("  ", metrics(kept, "2026-07-01", "2026-07-31", store="S02"))
    print("  期望(题库 M02)：net 41740.0 refund 107.0 orders 875 qty 1395 aov 47.7")
    print("\n-- 8 月 P21 --")
    print("  ", metrics(kept, "2026-08-01", "2026-08-31", product="P21"))
    print("  期望(题库 M03)：net 11024.0 refund 16.0 orders 461 qty 689 aov 23.91")

    # 日期区间
    dates = sorted(r[1] for r in kept)
    print("\n数据区间：%s ~ %s" % (dates[0], dates[-1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
