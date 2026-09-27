"""测试夹具。

两套夹具：
* `client` —— 接口层用。检索被换成固定命中，只测路由与序列化。
* `real_service` / `real_client` —— 回归测试用。清洗、索引、检索、作答全走真实实现。

原来的 `client` 直接改 `Retriever.search` 这个类属性而且**不还原**，等于把同一次
pytest 会话里后面的所有检索都变成假命中 —— 拿它写检索回归测试永远测不出东西。
现在改成退出时还原；真实链路的断言一律走 `real_*` 那套。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAKE_TEXT = "退款政策 v2 > 三、时限：外卖订单在订单送达后 24 小时内可以申请退款。"

#: 真实的检索实现，在 conftest 导入时（任何替换发生之前）留一份。
#: 夹具是 session 作用域的，拆卸发生在**整个会话结束**时，
#: 所以 `client` 装上的假检索会一直留到会话结束，污染后面的真实链路测试。
#: `real_*` 那套夹具用它无条件还原。
from kbqa.retriever import Retriever as _Retriever  # noqa: E402

REAL_SEARCH = _Retriever.search


def _restore_real_search() -> None:
    _Retriever.search = REAL_SEARCH


def _clear_llm_env() -> None:
    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        os.environ.pop(key, None)


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    os.environ["VAR_DIR"] = str(tmp_path_factory.mktemp("var"))
    _clear_llm_env()

    from fastapi.testclient import TestClient

    from kbqa import retriever as retriever_module
    from kbqa import server

    original = retriever_module.Retriever.search

    def fake_search(self, query, top_k=5, **kwargs):
        hit = retriever_module.Hit(
            doc_id="KB-013",
            chunk_id="KB-013#1",
            score=42.0,
            text=FAKE_TEXT,
            source_text=FAKE_TEXT,
            meta={"title": "退款政策 v2", "state": "现行"},
        )
        return retriever_module.SearchResult(
            hits=[hit][:top_k],
            query=query,
            terms=[],
            expansions=[],
            filtered=[],
            coverage=1.0,
        )

    retriever_module.Retriever.search = fake_search
    try:
        yield TestClient(server.app)
    finally:
        retriever_module.Retriever.search = original


@pytest.fixture(scope="session")
def real_service(tmp_path_factory):
    """真实链路：真清洗、真索引、真检索、真作答。"""
    os.environ["VAR_DIR"] = str(tmp_path_factory.mktemp("var_real"))
    _clear_llm_env()
    _restore_real_search()
    from kbqa.service import Service

    return Service()


@pytest.fixture(scope="session")
def real_client(real_service):
    from fastapi.testclient import TestClient

    from kbqa import server

    _restore_real_search()
    server._service = real_service
    return TestClient(server.app)
