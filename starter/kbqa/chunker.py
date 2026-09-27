"""把文档切成检索用的小块。

三件事：
1. **一个字都不能丢**。原先用 `range(0, len(text) - CHUNK_SIZE, CHUNK_SIZE)`，
   每篇文档最后不足一块的尾巴会被静默截掉，答案可能正好就在那段里。
2. 尽量在段落边界切。句子被拦腰截断会让 BM25 打分变差，也会让引用取到半句话。
3. **识别 Markdown 表格**，整块不拆，并把表头记在 `table_header` 上。
   表格的列名（“麸质”“大豆”“芝麻”）在表头行，值在数据行；
   不把表头带上的话，`| P06 | 牛肉poke | ✓ | ✓ | ...` 这行永远回答不了
   “牛肉poke 里有哪些过敏原”—— `units.py` 的表格分支和
   `docfacts.render_row` 都要靠 `kind="table"` 与 `table_header` 才能工作。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import Document

#: 切块参数变了，索引缓存必须失效，所以写进缓存键里。
CHUNKER_VERSION = "chunker-4"

CHUNK_SIZE = 300
#: 单块上限：段落边界凑不满时允许略微超过 CHUNK_SIZE，但不能无限涨。
CHUNK_MAX = 420

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
#: Markdown 表格的分隔行，例如 `| --- | :---: |`。
_TABLE_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    source_text: str
    heading: str = ""
    kind: str = "text"
    table_header: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source_text": self.source_text,
            "heading": self.heading,
            "kind": self.kind,
            "table_header": self.table_header,
        }


def _split_long(paragraph: str) -> list[str]:
    """单段本身超过 CHUNK_MAX 时按长度硬切，保证不丢字。"""
    if len(paragraph) <= CHUNK_MAX:
        return [paragraph]
    return [paragraph[start : start + CHUNK_SIZE] for start in range(0, len(paragraph), CHUNK_SIZE)]


def _blocks(text: str) -> list[str]:
    """按空行切段。"""
    pieces: list[str] = []
    for paragraph in _PARAGRAPH_SPLIT.split(text):
        paragraph = paragraph.strip("\n")
        if not paragraph.strip():
            continue
        pieces.extend(_split_long(paragraph))
    return pieces


def _pack(pieces: list[str]) -> list[str]:
    """把段落贪心地装进块里，尽量接近 CHUNK_SIZE 又不越过 CHUNK_MAX。"""
    packed: list[str] = []
    buffer = ""
    for piece in pieces:
        if not buffer:
            buffer = piece
            continue
        if len(buffer) + len(piece) + 2 <= CHUNK_MAX:
            buffer = buffer + "\n\n" + piece
            continue
        packed.append(buffer)
        buffer = piece
    if buffer:
        packed.append(buffer)
    return packed


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_start(lines: list[str], position: int) -> bool:
    """`| 表头 | ... |` 后面紧跟一行 `| --- | --- |`，才当成表格。"""
    if position + 1 >= len(lines):
        return False
    head, separator = lines[position].strip(), lines[position + 1].strip()
    return head.startswith("|") and head.endswith("|") and bool(_TABLE_SEPARATOR.match(separator))


def _segments(text: str) -> list[tuple[str, list[str], str]]:
    """切成（kind, 表头, 正文）三类段：表格整块一段，其余按空行分段。

    表格块里保留表头行与分隔行，`units.py` 靠它把 ✓ 翻成列名。
    """
    lines = text.split("\n")
    segments: list[tuple[str, list[str], str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        joined = "\n".join(buffer).strip("\n")
        buffer.clear()
        if joined.strip():
            for piece in _blocks(joined):
                segments.append(("text", [], piece))

    position = 0
    while position < len(lines):
        if _is_table_start(lines, position):
            flush()
            header = _table_cells(lines[position])
            block = [lines[position], lines[position + 1]]
            position += 2
            while position < len(lines) and lines[position].strip().startswith("|"):
                block.append(lines[position])
                position += 1
            segments.append(("table", header, "\n".join(block)))
            continue
        buffer.append(lines[position])
        position += 1
    flush()
    return segments


def chunk_document(document: Document) -> list[Chunk]:
    """把一篇文档切成若干块。每块是原文的一段连续文字，便于逐字引用。"""
    text = document.text or ""
    chunks: list[Chunk] = []
    for kind, header, body in _segments(text):
        chunks.append(
            Chunk(
                doc_id=document.doc_id,
                chunk_id="%s#%d" % (document.doc_id, len(chunks) + 1),
                text=body,
                # 引用要逐字核对，所以 source_text 必须是这一块在原文里的原样切片。
                source_text=body,
                heading=document.title,
                kind=kind,
                table_header=header,
            )
        )
    if not chunks:
        piece = text.strip() or document.title
        chunks.append(
            Chunk(
                doc_id=document.doc_id,
                chunk_id="%s#1" % document.doc_id,
                text=piece,
                source_text=piece,
                heading=document.title,
            )
        )
    return chunks


def chunk_documents(documents: list[Document]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_document(document))
    return chunks
