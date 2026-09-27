"""把原始 sales 导进 var/clean.db，指标都查这张表。

清洗规则全部来自知识库 KB-001《指标口径手册 v3》§2「规范化」与 §3「剔除」。
手册是唯一权威：要改这里的规则，先改手册。
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

#: KB-001 §2.3：`¥38.00` 与 `38.00` 是同一个金额，去掉符号与空白之后照常参与统计。
_CURRENCY = str.maketrans("", "", "¥￥ \t　")

#: KB-001 §2.2：接受三种日期格式。第三种是旧 POS 导出格式，**日在前、月在后**：
#: `25-07-2026` 是 2026 年 7 月 25 日。数据里有「日」大于 12 的样本，可以验证方向。
_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_SLASH_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
_DMY_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
_DATE_FORMATS = (
    (_ISO_RE, "YYYY-MM-DD", "ymd"),
    (_SLASH_RE, "YYYY/M/D", "ymd"),
    (_DMY_RE, "DD-MM-YYYY", "dmy"),
)

REMOVAL_REASONS = (
    "1_unparseable_date",
    "2_empty_amount",
    "3_qty_le_zero",
    "4_store_not_in_stores",
    "5_product_not_in_products",
    "6_duplicate_row",
)


def normalise_id(value: Optional[str]) -> str:
    """KB-001 §2.1：`store_id` / `product_id` 去掉首尾空白并转大写。

    `s01`、`S01 `、` s03` 规范化之后都是合法编号，**不是**脏数据。
    """
    return (value or "").strip().upper()


def parse_date(value: Optional[str]) -> tuple[Optional[str], str]:
    """按 KB-001 §2.2 解析日期，返回 (ISO 日期, 命中的格式名)。

    解析不出来或月/日越界（数据里有 `2026-13-45` 这种假日期）时返回 (None, "bad")。
    """
    text = (value or "").strip()
    if not text:
        return None, "missing"
    for pattern, name, order in _DATE_FORMATS:
        match = pattern.match(text)
        if not match:
            continue
        first, second, third = (int(part) for part in match.groups())
        if order == "ymd":
            year, month, day = first, second, third
        else:
            day, month, year = first, second, third
        try:
            # 走一遍 date() 才能真正挡住 2026-13-45、2026-02-30 这类越界值。
            resolved = _date(year, month, day)
        except ValueError:
            return None, "bad"
        return resolved.isoformat(), name
    return None, "bad"


def parse_amount(value: Optional[str]) -> tuple[Optional[int], str]:
    """返回 (分, 状态)。状态取值：`ok`、`empty`、`bad`。

    KB-001 §2.3 与 §3.2：`¥38.00` 与 `38.00` 是同一个金额；空金额直接剔除，**不回填**。
    """
    text = (value or "").translate(_CURRENCY).strip()
    if not text:
        return None, "empty"
    try:
        cents = int((Decimal(text) * 100).to_integral_value())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None, "bad"
    return cents, "ok"


def parse_qty(value: Optional[str]) -> Optional[int]:
    """KB-001 §2.4：按整数解析。解析不了的返回 None，交给 §3.3 剔除。"""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


@dataclass
class CleaningReport:
    raw_rows: int = 0
    kept_rows: int = 0
    kept_sales_rows: int = 0
    kept_refund_rows: int = 0
    removed: dict[str, int] = field(default_factory=lambda: {k: 0 for k in REMOVAL_REASONS})
    note_unparseable_amount: int = 0
    date_formats: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "raw_rows": self.raw_rows,
            "removed": dict(self.removed, note_unparseable_amount=self.note_unparseable_amount),
            "kept_rows": self.kept_rows,
            "kept_sales_rows": self.kept_sales_rows,
            "kept_refund_rows": self.kept_refund_rows,
            "date_formats": dict(self.date_formats),
        }


def open_readonly(path: Path) -> sqlite3.Connection:
    """打开源库。指标一律从清洗后的库查，源库只读。

    `PRAGMA query_only` 让这条连接在 SQLite 层面就写不进去，
    配合 `tools.run_sql` 的语句白名单，一起保证「数据库不能有任何改动」。
    """
    conn = sqlite3.connect(path.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def clean_rows(
    rows: Iterable[sqlite3.Row],
    store_ids: Optional[set[str]] = None,
    product_ids: Optional[set[str]] = None,
) -> tuple[list[tuple], CleaningReport]:
    """按 KB-001 §2 + §3 清洗明细行，剔除顺序与手册一致。

    §3 的六条按顺序执行，前一条剔除掉的行不再参与后面的判断。
    §3.6 的重复行判定用「订单号、日期、门店、商品、数量、金额、支付方式」七个字段：
    只有七项规范化之后完全一致才算重复；一张订单点两个不同商品的合法多行订单必须保留。
    """
    report = CleaningReport()
    kept: list[tuple] = []
    seen: set[tuple] = set()

    for row in rows:
        report.raw_rows += 1

        # §3.1 日期无法解析（含月/日越界）。
        iso_date, date_format = parse_date(row["date"])
        report.date_formats[date_format] = report.date_formats.get(date_format, 0) + 1
        if iso_date is None:
            report.removed["1_unparseable_date"] += 1
            continue

        # §3.2 amount 为空的行，不回填，直接剔除。
        cents, status = parse_amount(row["amount"])
        if status == "empty":
            report.removed["2_empty_amount"] += 1
            continue
        if status != "ok":
            report.note_unparseable_amount += 1
            report.removed["2_empty_amount"] += 1
            continue

        # §3.3 qty ≤ 0。
        qty = parse_qty(row["qty"])
        if qty is None or qty <= 0:
            report.removed["3_qty_le_zero"] += 1
            continue

        # §2.1 先规范化编号，再判断是不是脏外键；顺序反了会误删真实订单。
        store_id = normalise_id(row["store_id"])
        product_id = normalise_id(row["product_id"])
        order_id = (row["order_id"] or "").strip()
        payment = (row["payment"] or "").strip()

        # §3.4 / §3.5 脏外键。
        if store_ids is not None and store_id not in store_ids:
            report.removed["4_store_not_in_stores"] += 1
            continue
        if product_ids is not None and product_id not in product_ids:
            report.removed["5_product_not_in_products"] += 1
            continue

        # §3.6 全字段一致的重复行，只保留 1 条。
        fingerprint = (order_id, iso_date, store_id, product_id, qty, cents, payment)
        if fingerprint in seen:
            report.removed["6_duplicate_row"] += 1
            continue
        seen.add(fingerprint)

        kept.append(
            (
                order_id,
                iso_date,
                store_id,
                product_id,
                qty,
                cents,
                payment,
                # §4：退款行 = amount < 0，销售行 = amount > 0。
                1 if cents < 0 else 0,
            )
        )

    report.kept_rows = len(kept)
    report.kept_refund_rows = sum(1 for row in kept if row[-1])
    report.kept_sales_rows = report.kept_rows - report.kept_refund_rows
    return kept, report


_SCHEMA = """
CREATE TABLE stores (store_id TEXT PRIMARY KEY, store_name TEXT, category TEXT, district TEXT);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT,
                       product_category TEXT, unit_price REAL);
CREATE TABLE sales_clean (
    order_id TEXT, date TEXT, store_id TEXT, product_id TEXT,
    qty INTEGER, amount_cents INTEGER, payment TEXT, is_refund INTEGER
);
CREATE INDEX idx_clean_date ON sales_clean(date);
CREATE INDEX idx_clean_store ON sales_clean(store_id);
CREATE INDEX idx_clean_product ON sales_clean(product_id);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


_DROP_SCHEMA = """
DROP TABLE IF EXISTS sales_clean;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS meta;
"""


def build_clean_db(source: Path, target: Path) -> CleaningReport:
    """从只读的源库重建清洗表。返回清洗台账，供 `/api/health` 与数据质量面板使用。"""
    if not source.exists():
        raise FileNotFoundError("找不到源数据库：%s" % source)
    src = open_readonly(source)
    try:
        stores = [
            (normalise_id(row["store_id"]), row["store_name"], row["category"], row["district"])
            for row in src.execute("SELECT store_id, store_name, category, district FROM stores")
        ]
        products = [
            (
                normalise_id(row["product_id"]),
                row["product_name"],
                row["product_category"],
                row["unit_price"],
            )
            for row in src.execute(
                "SELECT product_id, product_name, product_category, unit_price FROM products"
            )
        ]
        store_ids = {row[0] for row in stores}
        product_ids = {row[0] for row in products}
        rows, report = clean_rows(
            src.execute("SELECT order_id, date, store_id, product_id, qty, amount, payment FROM sales"),
            store_ids,
            product_ids,
        )
    finally:
        src.close()

    target.parent.mkdir(parents=True, exist_ok=True)
    # 服务正在运行时 clean.db 被它占着，Windows 上 unlink 会直接抛 WinError 32。
    # 那种情况下改成原地重建表，结果一样，但不会让 rebuild 莫名其妙失败。
    removed = False
    if target.exists():
        try:
            target.unlink()
            removed = True
        except PermissionError:
            removed = False
    out = sqlite3.connect(target)
    try:
        if not removed:
            out.executescript(_DROP_SCHEMA)
        out.executescript(_SCHEMA)
        out.executemany("INSERT INTO stores VALUES (?,?,?,?)", stores)
        out.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
        out.executemany("INSERT INTO sales_clean VALUES (?,?,?,?,?,?,?,?)", rows)
        out.execute(
            "INSERT INTO meta VALUES ('cleaning_report', ?)",
            (json.dumps(report.as_dict(), ensure_ascii=False),),
        )
        out.execute("INSERT INTO meta VALUES ('source_db', ?)", (source.name,))
        # 数据区间由清洗后的数据决定，不写死；契约 §1 的 data_period 用它。
        bounds = out.execute("SELECT MIN(date), MAX(date) FROM sales_clean").fetchone()
        out.execute(
            "INSERT INTO meta VALUES ('data_period', ?)",
            (json.dumps({"start": bounds[0] or "", "end": bounds[1] or ""}, ensure_ascii=False),),
        )
        out.commit()
    finally:
        out.close()
    return report
