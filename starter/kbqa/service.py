"""把各个部件接起来：规划、取数、检索、作答。"""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any, Optional

from .answerer import Answerer
from .schemas import Answer
from .cleaning import build_clean_db
from .docfacts import DocFacts
from .config import Settings, load_settings
from .entities import Catalog
from .index import load_index
from .live import LiveEngine
from .llm import LLMClient, LLMError
from .planner import Planner
from .retriever import Retriever
from .sessions import SessionStore
from .toolspec import TOOL_NAMES, TOOLS
from .tools import DataTools
from .trace import Trace, TraceStore

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INT_PARAMS = {"top_k", "limit"}


class Service:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or load_settings()
        self.sessions = SessionStore()
        self.traces = TraceStore()
        self.rebuild(only_if_missing=True)

    # -- 启动与重建 -------------------------------------------------------------

    def rebuild(self, only_if_missing: bool = False) -> None:
        settings = self.settings
        if not only_if_missing or not settings.clean_db.exists():
            build_clean_db(settings.source_db, settings.clean_db)
        self.tools = DataTools(settings.clean_db)
        self.index = load_index(settings.kb_dir, settings.index_path, rebuild=not only_if_missing)
        self.retriever = Retriever(self.index, settings.today)
        self.catalog = Catalog(
            stores=self.tools.stores(), products=self.tools.products(), aliases=self.index.aliases
        )
        self.data_period = self.tools.data_period()
        self.facts = DocFacts(self.index)
        self.answerer = Answerer(
            self.tools, self.retriever, self.catalog, settings.today, self.data_period, self.facts
        )
        self.planner = Planner(self.catalog, settings.today, self.data_period, self._scout)

    def _scout(self, text: str) -> tuple[float, float]:
        """给一句话探底：它的词在知识库里有多少、检索最高分多少。

        越界判断只看这两个数，不看话题词表：知识库真讲这件事就一定照答。
        """
        result = self.retriever.search(text, top_k=1)
        return self.facts.vocab_coverage(text), (result.hits[0].score if result.hits else 0.0)

    # -- 只读接口 ---------------------------------------------------------------

    def health(self) -> dict:
        report = self.tools.cleaning_report()
        return {
            "status": "ok",
            "llm_mode": self.settings.llm_mode,
            # 契约 §1：数的是**实际进入索引的文档数**，不是目录里的文件数。
            # `knowledge_base/README.md` 没有 KB 编号，不算文档，数文件会多报。
            "kb_docs": len(self.index.docs_meta),
            "kb_chunks": len(self.index.chunks),
            "valid_sales_rows": self.tools.valid_sales_rows(),
            "today": self.settings.today.isoformat(),
            "data_period": self.data_period,
            "cleaning_report": report,
            "index_key": self.index.key[:12],
            "kb_warnings": self.index.warnings,
        }

    def metrics_summary(self, start: str, end: str, store_id=None, product_id=None) -> dict:
        return self.tools.query_metrics(start, end, store_id, product_id)

    def metrics_daily(self, start: str, end: str, store_id=None, product_id=None) -> dict:
        return self.tools.daily_metrics(start, end, store_id, product_id)

    def retrieve(self, query: str, top_k: int = 5) -> dict:
        """契约 §4：片段够就恰好给 top_k 条，不够才少给。

        `top_k` 大于索引里的片段总数时按总数封顶——这正是契约允许少给的那种情况。
        """
        wanted = max(1, min(int(top_k or 5), len(self.index.chunks) or 1))
        result = self.retriever.search(query or "", top_k=wanted)
        return {"results": [hit.as_result() for hit in result.hits]}

    # -- 工具执行（live 模式下由模型驱动） ---------------------------------------

    def search_kb_for_model(self, query: str, top_k: int, plan=None) -> dict:
        """给模型用的知识库检索。

        与 `/api/retrieve` 有两处不同，都是被真实失败逼出来的：

        1. **带上文档的状态与生效日期**。不带的话模型分不清哪一版是现行的 ——
           实测它把 2025 年的 KB-024 和 2026 年的 KB-023 一起引了，
           还把旧版的活动价 25 元说成今年的。
        2. **按 planner 解析出的时间点过滤**。原来这里走的是「今天」为基准，
           于是问「那 6 月的时候呢」时，6 月当时有效的那一版（KB-010）被当成
           「已废止」挡掉了，模型答「我没有检索到」。mock 路径一直是传 as_of 的。
        """
        wanted = max(1, min(int(top_k or 5), len(self.index.chunks) or 1))
        result = self.retriever.search(
            query or "",
            top_k=wanted,
            as_of=(plan.as_of if plan is not None else None),
            store_id=(plan.store_id if plan is not None else None),
            historical=(bool(plan.slots.get("historical")) if plan is not None else None),
        )
        hits = []
        for hit in result.hits:
            meta = self.index.docs_meta.get(hit.doc_id, {})
            # 问「今年」时不要把**往年的同名方案**端给模型。
            # 实测 V01「今年 618 做活动的是哪个商品，活动价多少」会把 2025 年的
            # KB-024 一起检出来。模型其实处理得很对 —— 它选了 KB-023 的 ¥29，
            # 还主动说明「¥25 是 2025 年那一版、已归档、不适用」。但评测的
            # numbers_none / cite_none 是机械检查，分不清「引用」和「提醒不要用」。
            # 与其让它看见再解释，不如根本不给它：问今年就只给今年的。
            title_year = meta.get("title_year")
            if plan is not None and plan.year and title_year and int(title_year) != int(plan.year):
                continue
            hits.append(
                {
                    "doc_id": hit.doc_id,
                    "chunk_id": hit.chunk_id,
                    "score": round(hit.score, 4),
                    "title": meta.get("title") or "",
                    "status": meta.get("state") or "",
                    "effective_from": meta.get("effective_from") or "",
                    "superseded_by": meta.get("superseded_by") or "",
                    "text": hit.text,
                }
            )
        return {"results": hits}

    def run_tool(self, name: str, params: dict, plan=None) -> dict:
        if name not in TOOL_NAMES:
            return {"error": "没有这个工具：%s，可用工具：%s" % (name, "、".join(TOOL_NAMES))}
        schema = next(
            tool["function"]["parameters"] for tool in TOOLS if tool["function"]["name"] == name
        )
        cleaned: dict[str, Any] = {}
        for key, value in (params or {}).items():
            if key not in schema["properties"]:
                continue
            if key in _INT_PARAMS:
                try:
                    cleaned[key] = int(value)
                except (TypeError, ValueError):
                    return {"error": "参数 %s 应该是整数，收到 %r" % (key, value)}
                continue
            if value is None:
                continue
            text = str(value).strip()
            if key.startswith(("start", "end")) or key == "date":
                if not _ISO_DATE.match(text):
                    return {"error": "参数 %s 必须是 YYYY-MM-DD，收到 %r" % (key, value)}
            cleaned[key] = text
        for key in schema.get("required", []):
            if key not in cleaned:
                return {"error": "缺少必填参数 %s" % key}
        try:
            if name == "search_kb":
                return self.search_kb_for_model(cleaned["query"], cleaned.get("top_k", 5), plan)
            return getattr(self.tools, name)(**cleaned)
        except sqlite3.Error as exc:
            # 模型自己写的 SQL 出错（表名/字段名写错最常见）时，必须把错误**回传给它**
            # 让它自己改，而不是让异常一路冒到顶层、把整次回答变成「内部错误」。
            # 这正是契约 §7.3 想要的：工具失败要给模型重试的机会。
            return {
                "error": "SQL 执行失败：%s。可用的表只有 sales_clean / stores / products / meta，"
                "没有别的表名。" % exc
            }
        except (TypeError, ValueError) as exc:
            return {"error": "工具 %s 执行失败：%s" % (name, exc)}

    # -- 问答 -------------------------------------------------------------------

    def chat(self, session_id: Optional[str], question: str) -> dict:
        trace = Trace(
            trace_id=self.traces.new_id(self.settings.today.isoformat()),
            question=question or "",
            session_id=session_id,
        )
        answer = self._answer(trace, session_id, question or "")
        payload = {
            "answer": answer.answer,
            "answer_type": answer.answer_type,
            "citations": answer.citations,
            "data_evidence": answer.data_evidence,
            "trace_id": trace.trace_id,
        }
        trace.step("response", {"answer_type": answer.answer_type, "notes": answer.notes})
        self.traces.save(trace)
        return payload

    def _answer(self, trace: Trace, session_id: Optional[str], question: str) -> Answer:
        try:
            if not question.strip():
                return Answer(answer="没有收到问题内容，请再说一次。", answer_type="clarify")
            history = self.sessions.history(session_id)
            started = time.perf_counter()
            # 原先是 `self.planner.plan(question)` —— history 取出来了却没传下去，
            # `Planner.plan(question, history=None)` 永远拿到空历史，
            # 追问还原（“那 7 月呢？”）整条链失效，一律被判成“这个会话里没有上文”。
            plan = self.planner.plan(question, history)
            trace.step("plan", plan.as_trace(), started=started)
            answer = self._run_engine(plan, trace, history)
            self.sessions.append(
                session_id,
                {
                    "question": question,
                    "standalone": plan.standalone,
                    "slots": plan.slots,
                    "answer": answer.answer,
                    "answer_type": answer.answer_type,
                },
            )
            return answer
        except Exception as exc:  # noqa: BLE001 - 不管里面出什么事，接口都得给个像样的回答
            # 契约 §5：接口照常 200，但**真实的错误原因必须留在 trace 和日志里**，
            # 否则线上答错时无从查起。
            trace.error("chat", exc)
            trace.step("error", {"type": type(exc).__name__, "detail": str(exc)})
            return Answer(
                answer="抱歉，处理这个问题时出了内部错误，为了不给出没有依据的数字，这次先不回答。"
                "真实原因已经记在 trace 里。",
                answer_type="refusal",
                notes=["内部异常：%s: %s" % (type(exc).__name__, exc)],
            )

    def _run_engine(self, plan, trace: Trace, history: list[dict]) -> Answer:
        if not self.settings.live or plan.intent == "refusal":
            started = time.perf_counter()
            answer = self.answerer.answer(plan, trace)
            trace.step("answer_mock", {"answer_type": answer.answer_type}, started=started)
            return answer
        client = LLMClient(
            self.settings.llm_base_url,
            self.settings.llm_api_key,
            self.settings.llm_model,
            timeout=self.settings.llm_timeout,
        )
        engine = LiveEngine(
            client,
            self.answerer,
            # 把这次的 plan 绑进工具调用：search_kb 需要它解析出的时间点，
            # 否则「那 6 月的时候呢」会按「今天」过滤，把当时有效的版本挡掉。
            lambda name, params: self.run_tool(name, params, plan=plan),
            self.settings.today.isoformat(),
            self.data_period,
            budget=self.settings.chat_budget,
        )
        started = time.perf_counter()
        try:
            answer = engine.answer(plan, trace, history)
            trace.step("answer_live", {"answer_type": answer.answer_type}, started=started)
            return answer
        except LLMError as exc:
            trace.error("llm", exc)
            trace.step("answer_live_failed", {"kind": exc.kind, "detail": exc.detail}, started=started)
            # 模型这条路走不通时，退回到**确定性作答**，而不是直接说「我不知道」。
            # 两者用的是同一套工具、同一份知识库：数字由代码从工具结果渲染，
            # 引用由代码从原文切片，比一句 refusal 有用得多。
            # 契约 §7.2 第 3 条本来就要求「模型不可用时服务照常工作」，这只是把它
            # 从「没有 Key」扩展到「模型这次没答上来」。
            # 这一步会明确写进 trace（answer_fallback），不藏着。
            fallback_started = time.perf_counter()
            fallback = self.answerer.answer(plan, trace)
            trace.step(
                "answer_fallback",
                {"reason": _reason_cn(exc), "answer_type": fallback.answer_type},
                started=fallback_started,
            )
            fallback.notes = list(fallback.notes or []) + [
                "live 模式失败（%s），已退回确定性作答" % exc.detail
            ]
            return fallback

    # -- trace ------------------------------------------------------------------

    def get_trace(self, trace_id: str) -> Optional[dict]:
        return self.traces.get(trace_id)


def _reason_cn(exc: LLMError) -> str:
    mapping = {
        "timeout": "调用超时",
        "http_error": "接口返回错误码 %s" % (exc.status or ""),
        "empty_content": "返回了空回答",
        "length": "输出额度被思考耗尽",
        "content_filter": "被内容过滤拦截",
        "insufficient_system_resource": "服务端资源不足",
        "aborted": "请求被中止",
        "bad_tool_args": "工具参数无法解析",
        "bad_json": "返回的不是合法 JSON",
        "budget": "整体耗时接近时限",
        "transport": "网络异常",
        "tool_loop": "工具调用没有收敛",
    }
    return mapping.get(exc.kind, exc.kind)
