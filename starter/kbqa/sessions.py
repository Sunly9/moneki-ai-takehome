"""对话历史，按 session_id 隔离。

契约 §5：同一个 `session_id` 的多次请求视为同一段对话，要支持追问；
不同 `session_id` 之间不能串线。

原实现把 `session_id` 整个忽略掉，所有会话共用一条 `_turns`：
`append("A", ...)` 之后 `history("B")` 会返回 A 的那一轮。
`max_sessions` 也从未被使用过。
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Optional

MAX_TURNS = 6
MAX_SESSIONS = 500

#: 没有 session_id 时用的桶。匿名请求互相之间也当成同一段对话，
#: 否则「没有 session_id」的连续追问会各自孤立。
_ANONYMOUS = "\x00anonymous"


class SessionStore:
    """每个 session_id 各自保留最近几轮对话，够解追问就行。"""

    def __init__(self, max_sessions: int = MAX_SESSIONS, max_turns: int = MAX_TURNS) -> None:
        #: OrderedDict 当 LRU 用：最近用过的会话挪到末尾，超量时从头部淘汰。
        self._sessions: "OrderedDict[str, list[dict]]" = OrderedDict()
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.max_turns = max_turns

    @staticmethod
    def _key(session_id: Optional[str]) -> str:
        text = (session_id or "").strip()
        return text or _ANONYMOUS

    def history(self, session_id: Optional[str]) -> list[dict]:
        key = self._key(session_id)
        with self._lock:
            turns = self._sessions.get(key)
            if turns is None:
                return []
            self._sessions.move_to_end(key)
            return list(turns)

    def append(self, session_id: Optional[str], turn: dict) -> None:
        key = self._key(session_id)
        with self._lock:
            turns = self._sessions.setdefault(key, [])
            turns.append(turn)
            # 只裁这一段会话，不是全局共用 6 条。
            del turns[: max(0, len(turns) - self.max_turns)]
            self._sessions.move_to_end(key)
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)

    def clear(self, session_id: Optional[str] = None) -> None:
        with self._lock:
            if session_id is None:
                self._sessions.clear()
            else:
                self._sessions.pop(self._key(session_id), None)
