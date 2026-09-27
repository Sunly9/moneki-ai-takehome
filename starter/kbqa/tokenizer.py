"""分词。

中文没有词间空格，按空白切词等于把整句话当成一个词，BM25 永远匹配不上。
这里走标准的无依赖做法：**二元组（bigram）+ 单字**。
`retriever.SINGLE_CHAR_WEIGHT` 就是为这个粒度准备的。
"""

from __future__ import annotations

import re
import unicodedata

#: 分词规则变了，索引缓存必须失效。
TOKENIZER_VERSION = "tokenizer-3"

#: 中文里几乎不携带信息的字。只用在“查询覆盖率”上，索引照常保留全部词。
STOP_CHARS = frozenset(
    "的了吗呢是在有和与及或就都也还把被给对从向于个些这那哪什么怎样如何多少几请帮我你他它可以能要想会一下少吧啊呀们么样过得着为所"
)
STOP_WORDS = frozenset("the a an of to in is are and or for on at it this that how what".split())

#: CJK 统一表意文字（含扩展 A）与兼容区。
_CJK = (
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "\U00020000-\U0002a6df"
)
_CJK_RE = re.compile("[%s]" % _CJK)
#: 非中日韩的“词”：字母、数字、下划线，以及带音调的拉丁字母。
_WORD_RE = re.compile(r"[0-9a-z_]+")


def normalise(text: str) -> str:
    """全角转半角、统一大小写，比较与分词都走这一层。"""
    return unicodedata.normalize("NFKC", text or "").lower()


def tokenize(text: str) -> list[str]:
    """把文本切成 BM25 用的词。

    - CJK 连续段：输出每个单字，以及每一对相邻字组成的二元组。
      以标点和空白为界，二元组不跨句拼接（否则会造出「款政」这种噪声词）。
    - 拉丁字母与数字：整段作为一个词。
    """
    normalized = normalise(text)
    tokens: list[str] = []
    position = 0
    length = len(normalized)
    while position < length:
        char = normalized[position]
        if _CJK_RE.match(char):
            run = []
            while position < length and _CJK_RE.match(normalized[position]):
                run.append(normalized[position])
                position += 1
            for index, single in enumerate(run):
                tokens.append(single)
                if index + 1 < len(run):
                    tokens.append(single + run[index + 1])
            continue
        match = _WORD_RE.match(normalized, position)
        if match:
            tokens.append(match.group(0))
            position = match.end()
            continue
        position += 1
    return tokens


def content_tokens(text: str) -> list[str]:
    """去掉虚词之后的查询词，用来算“这个问题被文档覆盖了多少”。"""
    kept = []
    for token in tokenize(text):
        if token in STOP_WORDS:
            continue
        if all(char in STOP_CHARS for char in token):
            continue
        kept.append(token)
    return kept
