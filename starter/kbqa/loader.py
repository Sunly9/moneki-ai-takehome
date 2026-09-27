"""读知识库目录，把文件变成文档对象，顺手认出编号、标题、生效日期。"""

from __future__ import annotations

import codecs
import html as html_module
import re
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

#: 知识库里 `.md`、`.txt`、`.html` 三种格式都有（目录说明 §2.3）。
#: 只收 `.md` 会让 `.txt` / `.html` 的老文件整份进不了索引。
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}

#: 文件名开头的编号就是 doc_id，与文件格式无关（契约 §0）。
_DOC_ID = re.compile(r"^(KB-\d+)")
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
_STORE_CODE = re.compile(r"\bS\d{2}\b")

#: 正文里的生效日期：优先“自 2026 年 8 月 15 日起”“生效日期：2026-07-01”这类明确写法。
_CN_DATE = r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})\s*日?"
_EFFECTIVE_PATTERNS = (
    re.compile(r"(?:自|从)\s*" + _CN_DATE + r"\s*(?:起|开始)"),
    re.compile(r"生效(?:日期)?[：: ]\s*" + _CN_DATE),
    re.compile(r"(?:执行|实施)(?:日期)?[：: ]\s*" + _CN_DATE),
)
_ANY_DATE = re.compile(_CN_DATE)
_EMAIL_DATE = re.compile(r"^Date:\s*(.+)$", re.M)
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()

#: KB-001 §5.2：周报、会议纪要、活动复盘里的数字是人工估算，不能当答案。
ESTIMATE_TYPES = {"周报", "会议纪要", "复盘", "活动复盘"}


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    path: Path
    fmt: str
    doc_type: str = ""
    status: str = "现行"
    effective_from: Optional[date] = None
    superseded_by: Optional[str] = None
    stores: list[str] = field(default_factory=list)
    #: `stores` 是不是文档自己声明的。正文里认出来的门店只能当线索，
    #: 不能当硬过滤条件——KB-001 的正文里就举了 `s01` 当例子。
    stores_explicit: bool = False
    updated_at: Optional[date] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def estimates_only(self) -> bool:
        return self.doc_type in ESTIMATE_TYPES

    @property
    def title_year(self) -> Optional[int]:
        match = re.search(r"(20\d{2})", self.title)
        return int(match.group(1)) if match else None

    def meta(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "type": self.doc_type,
            "state": self.status,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "superseded_by": self.superseded_by,
            "stores": self.stores,
            "stores_explicit": self.stores_explicit,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "estimates_only": self.estimates_only,
            "title_year": self.title_year,
            "format": self.fmt,
            "filename": self.path.name,
        }


_HTML_TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)

#: 这些标签里的内容不是正文，取正文时整段跳过。
_HTML_SKIP_TAGS = frozenset({"script", "style", "noscript", "template", "head"})
#: 块级标签前后补换行，免得相邻两段文字被粘成一个词。
_HTML_BLOCK_TAGS = frozenset(
    {
        "p", "div", "br", "li", "tr", "td", "th", "table", "section", "article",
        "header", "footer", "ul", "ol", "blockquote", "pre", "hr",
        "h1", "h2", "h3", "h4", "h5", "h6",
    }
)


class _HtmlTextExtractor(HTMLParser):
    """把 HTML 取成“可见正文”。

    评测做 quote 逐字校验时就是**去掉标签与 script/style 之后再比对**的。
    这里必须用同一套口径，否则索引里存的是带标签的原文，
    引用要么带上标签、要么把标签当成正文，怎么都对不上。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):  # noqa: D102 - HTMLParser 回调
        if tag in _HTML_SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _HTML_BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):  # noqa: D102 - HTMLParser 回调
        if tag in _HTML_SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _HTML_BLOCK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(self, tag, attrs):  # noqa: D102 - HTMLParser 回调
        if tag in _HTML_BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):  # noqa: D102 - HTMLParser 回调
        if self._skip_depth == 0:
            self._parts.append(data)

    def visible_text(self) -> str:
        raw = "".join(self._parts).replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"\n{3,}", "\n\n", raw)


def html_to_text(markup: str) -> str:
    """HTML → 可见正文。解析失败时退回正则去标签，不抛异常。"""
    parser = _HtmlTextExtractor()
    try:
        parser.feed(markup)
        parser.close()
        text = parser.visible_text()
    except Exception:  # pragma: no cover - 兜底，坏 HTML 不该让整份知识库加载失败
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html_module.unescape(text)
    return text


def decode_bytes(raw: bytes, path: Path, warnings: list[str]) -> str:
    """按文件真实编码解码。

    知识库里有旧系统导出的 GBK 文件（如 `KB-062`）。原实现一律按 UTF-8 加
    `errors="ignore"` 读，GBK 文件会变成乱码甚至空串，引用自然对不上。
    评测的逐字校验也是按 GBK 解码这些文件的，所以这里必须一致。
    """
    if raw.startswith(codecs.BOM_UTF8):
        raw = raw[len(codecs.BOM_UTF8) :]
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    warnings.append("无法按 utf-8/gb18030 解码，已用替换字符兜底：%s" % path.name)
    return raw.decode("utf-8", errors="replace")


def parse_front_matter(text: str) -> tuple[dict, str]:
    """极简 YAML 头解析：`key: value` 与 `key: [a, b]`，够用且不引依赖。"""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [
                item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()
            ]
        else:
            meta[key.strip()] = value.strip().strip("'\"")
    return meta, text[match.end():]


def _as_date(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    match = _ANY_DATE.search(text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _effective_from_body(text: str) -> Optional[date]:
    """没有 YAML 头时，从正文里认生效日期。"""
    for pattern in _EFFECTIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                continue
    mail = _EMAIL_DATE.search(text)
    if mail:
        parts = mail.group(1).replace(",", " ").split()
        day = month = year = None
        for token in parts:
            low = token.lower()[:3]
            if low in _MONTHS:
                month = _MONTHS.index(low) + 1
            elif token.isdigit() and len(token) == 4:
                year = int(token)
            elif token.isdigit() and len(token) <= 2:
                day = int(token)
        if day and month and year:
            return date(year, month, day)
    match = _ANY_DATE.search(text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def _title_from_body(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if not stripped or set(stripped) <= set("=-*_ "):
            continue
        if stripped.startswith(("From:", "To:", "Cc:", "Date:")):
            continue
        if stripped.startswith("Subject:"):
            return stripped.split(":", 1)[1].strip()
        if stripped.startswith("标题：") or stripped.startswith("标题:"):
            return stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
        return stripped[:80]
    return fallback


def load_document(path: Path) -> Optional[Document]:
    """读一个文件。不是知识库文档（没有 KB 编号）时返回 None。"""
    warnings: list[str] = []
    raw = path.read_bytes()
    text = decode_bytes(raw, path, warnings)
    suffix = path.suffix.lower()
    fmt = {".md": "md", ".markdown": "md", ".txt": "txt", ".html": "html", ".htm": "html"}.get(
        suffix, "txt"
    )

    meta: dict = {}
    if fmt == "md":
        meta, text = parse_front_matter(text)
    elif fmt == "html":
        # 取“可见正文”，与评测的 quote 逐字校验口径保持一致。
        match_title = _HTML_TITLE.search(text)
        html_title = html_module.unescape(match_title.group(1).strip()) if match_title else ""
        meta = {"title": html_title.split("-")[0].strip() or html_title}
        text = html_to_text(text)

    match = _DOC_ID.match(path.name)
    doc_id = str(meta.get("doc_id") or (match.group(1) if match else "")).strip()
    if not doc_id:
        return None

    declared = meta.get("stores")
    stores = declared or _sorted_unique(_STORE_CODE.findall(text))
    doc_type = str(meta.get("type") or "").strip()
    if not doc_type:
        doc_type = _guess_type(path.name, text)
    return Document(
        doc_id=doc_id,
        title=str(meta.get("title") or _title_from_body(text, path.stem)).strip(),
        text=text.strip("\n"),
        path=path,
        fmt=fmt,
        doc_type=doc_type,
        status=str(meta.get("status") or "现行").strip(),
        effective_from=_as_date(meta.get("effective_from")) or _effective_from_body(text),
        superseded_by=(str(meta.get("superseded_by")).strip() if meta.get("superseded_by") else None),
        stores=[s.upper() for s in stores],
        stores_explicit=bool(declared),
        updated_at=_as_date(meta.get("updated_at")),
        warnings=warnings,
    )


def _sorted_unique(values) -> list[str]:
    return sorted({value.upper() for value in values})


def _guess_type(filename: str, text: str) -> str:
    head = filename + " " + text[:200]
    for marker in ("周报", "通知", "政策", "手册", "纪要", "报告", "FAQ", "档案"):
        if marker in head:
            return marker
    return "文档"


def load_knowledge_base(kb_dir: Path) -> tuple[list[Document], list[str]]:
    """加载整个知识库目录，返回（文档列表，告警列表）。"""
    documents: list[Document] = []
    warnings: list[str] = []
    seen: dict[str, Path] = {}
    if not kb_dir.exists():
        return documents, ["知识库目录不存在：%s" % kb_dir]
    for path in sorted(kb_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        document = load_document(path)
        if document is None:
            warnings.append("跳过没有 KB 编号的文件：%s" % path.name)
            continue
        if document.doc_id in seen:
            warnings.append(
                "doc_id 重复：%s 同时出现在 %s 与 %s"
                % (document.doc_id, seen[document.doc_id].name, path.name)
            )
            continue
        seen[document.doc_id] = path
        warnings.extend(document.warnings)
        documents.append(document)
    return documents, warnings
