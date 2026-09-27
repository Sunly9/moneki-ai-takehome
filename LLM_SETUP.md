# LLM 接入说明

本文档是评审把本服务切到你们自己的模型（DeepSeek `deepseek-flash`）的唯一依据。
按第 3 节改两个环境变量即可，**不需要改任何代码，也不需要重新执行重建命令**。

---

## 1. 用了什么

| 项 | 值 |
|---|---|
| 厂商 | DeepSeek（开发期与评审期同一家） |
| 模型名 | `deepseek-flash`，**只从 `LLM_MODEL` 读**，代码里没有任何模型名常量 |
| 协议 | OpenAI 兼容的 Chat Completions（`POST {LLM_BASE_URL}/chat/completions`） |
| SDK | 不用 SDK，直接用 `httpx` 发 HTTP。少一层版本差异，地址拼接完全可控 |
| `httpx` 版本 | `requirements.txt` 里不锁版本；开发与预检用的是 0.28.1 |
| 思考模式 | **保持开启（默认）**。理由见第 8 节 |

其它依赖只有 `fastapi` / `uvicorn` / `pytest`。检索是纯 Python 的 BM25，
**没有向量模型、没有本地模型文件、不需要下载任何权重**。

## 2. 配置从哪里读

全部从环境变量读，一项配置文件都没有。读取位置：`starter/kbqa/config.py` 的 `load_settings()`。

| 变量 | 默认值 | 含义 |
|---|---|---|
| `LLM_BASE_URL` | 空 | 模型服务地址。**原样使用**：不补 `/v1`、不截路径、不只取域名（契约 §7.1） |
| `LLM_API_KEY` | 空 | 模型 Key，按 `Authorization: Bearer <key>` 发送 |
| `LLM_MODEL` | 空 | 模型名，原样放进请求体的 `model` 字段 |
| `LLM_TIMEOUT` | `120` | 单次模型调用超时（秒） |
| `CHAT_BUDGET` | `150` | `/api/chat` 的整体预算（秒）。契约要求 180 秒内必须返回，这里留 30 秒余量 |

另有三个与数据/知识库有关、和模型无关的变量：`DATA_DIR`、`KB_DIR`、`VAR_DIR`。
以及只给测试用的 `TODAY`（默认就是契约规定的 `2026-09-01`）。

**是否进入 live 模式**只由这三个变量是否都非空决定（`Settings.live`）：
`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 三个都填了才是 `live`，否则是 `mock`。
启动时**不校验 Key 格式**，也**不调用**查余额、列模型之类的接口（契约 §7.2 最后一段）。

## 3. 怎么换成你们的

```bash
export LLM_BASE_URL=https://api.deepseek.com
export LLM_API_KEY=<你们的 Key>
export LLM_MODEL=deepseek-flash
```

Windows PowerShell：

```powershell
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:LLM_API_KEY  = "<你们的 Key>"
$env:LLM_MODEL    = "deepseek-flash"
```

然后**重启服务即可**：

```bash
cd starter
.venv/Scripts/python.exe -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000   # Windows
# .venv/bin/python -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000         # macOS / Linux
```

**不需要重新执行 `make rebuild` / `python -m kbqa.rebuild`**：重建只负责清洗数据与建检索索引，
与模型配置完全无关。

`/api/health` 的 `llm_mode` 会从 `mock` 变成 `live`，可以据此确认切换成功：

```bash
curl -s http://localhost:8000/api/health | python -c "import json,sys; print(json.load(sys.stdin)['llm_mode'])"
```

如果你们的评审环境要让服务经过带路径前缀的代理，把 `LLM_BASE_URL` 设成带前缀的地址即可，
例如 `http://127.0.0.1:<端口>/ds-gw`。代码只做 `base_url.rstrip("/") + "/chat/completions"`，
前缀会原样保留。

## 4. 怎么看到发给模型的请求

三种办法，任选：

**(a) 用作业包里的代理**（推荐，评审时你们用的就是这个）：

```bash
python3 eval/llm_gateway.py proxy --upstream https://api.deepseek.com --log llm_traffic.jsonl
# 用它打印出来的地址作为 LLM_BASE_URL 启动服务
```

每一次往返会往 `llm_traffic.jsonl` 写一行 JSON，`Authorization` 只记长度不记值，可以放心留存。

**(b) 打开服务自己的请求日志**（不经过代理也能看）：

```bash
# macOS / Linux
LLM_TRACE=1 .venv/bin/python -m uvicorn kbqa.server:app --port 8000
```

```powershell
# Windows
$env:LLM_TRACE = "1"
.venv\Scripts\python.exe -m uvicorn kbqa.server:app --port 8000
```

完整请求（提示词、工具定义、每一轮消息）与原始响应会以一行 JSON 写进 stderr。
`starter/kbqa/llm.py` 里每次调用都会产出一条 record，字段如下（脱敏样例，结构与真实一致）：

```json
{"endpoint": "https://api.deepseek.com/chat/completions", "model": "deepseek-flash",
 "messages": 3, "tools": 4,
 "prompt": "[{\"role\": \"system\", \"content\": \"<系统提示词，约 1.2KB>\"}, {\"role\": \"user\", \"content\": \"618 当天 S02 的牛肉poke 卖了多少份，达到目标了吗？\"}]",
 "status": 200, "finish_reason": "tool_calls", "content_chars": 0,
 "tool_calls": ["query_metrics"], "has_reasoning": true,
 "usage": {"prompt_tokens": 1180, "completion_tokens": 412},
 "raw_content": "", "raw_reasoning": "<约 900 字思考过程，略>",
 "took_ms": 8421.3}
```

要点：

- `prompt` 是**完整的 messages 数组**（含系统提示词、全部历史轮次、工具定义数量），
  超过 4000 字会截断并标注总长度。
- `raw_content` 是模型的正文输出，`raw_reasoning` 是思考过程。**思考过程只在这里和 trace
  里出现，不进 `answer` / `citations` / `data_evidence`**（预检 P10 验的就是这一条）。
- 出错时 record 里会有 `error` 字段（`timeout` / `transport` / `http_401` / `bad_json` /
  `length` / `content_filter` / `no_choice` 等）与 `detail`，可以据此定位。
- `Authorization` 头**不写进日志**，Key 不会泄漏到 stderr。

`LLM_TRACE` 的值在进程启动时读一次；改它要重启服务。默认关闭（不输出），
预检与公开评测都是在关闭状态下跑的，不影响结果。

**(c) 逐题看 trace**：`GET /api/trace/{trace_id}` 里的 `llm_calls` 数组就是每一次调用的
请求与原始响应，看板页面的「调试」标签把它可视化。

## 5. 没有 Key 时会怎样

服务**照常启动**，四个接口都正常，`/api/chat` 进入降级（mock）模式，**不会 500**。

| 接口 | 没有 Key 时的行为 |
|---|---|
| `GET /api/health` | 正常，`llm_mode` 为 `"mock"` |
| `GET /api/metrics/summary`、`/api/metrics/daily` | 正常，数字与有没有 Key 无关 |
| `POST /api/retrieve` | 正常，检索是本地 BM25 |
| `POST /api/chat` | 走本地模板作答：确定性规则规划 + KB-001 口径取数 + 抽取式引用。`answer_type`、`citations`、`data_evidence`、`trace_id` 字段齐全，形状与 live 模式完全一致 |
| `GET /api/trace/{trace_id}` | 正常 |

降级模式**不是**返回空壳或拒答：公开题库 55 题里 52 题在这种模式下就是靠本地模板答对的
（见 `EVAL_REPORT.md`）。差别在于它不能做开放式归纳，只能抽取与复述。

## 6. 依赖与安装

额外依赖：无。`requirements.txt` 只有 `fastapi`、`uvicorn`、`httpx`、`pytest`。
没有向量模型，没有模型文件下载，首次启动耗时约 1 秒（含读取 `.cache/index.json`）。
重建（`python -m kbqa.rebuild`）在当前机器上约 0.3 秒。

## 7. 自测结果

走的是 OpenAI 兼容路线，已跑 `eval/llm_gateway.py preflight`。
**14 项检查全部通过，没有失败项，也没有「未检查」项。**

复现命令（仓库根目录）：

```bash
python tools/run_preflight.py --out eval_reports
```

`tools/run_preflight.py` 是为此写的一层薄封装：预检本身是交互式的（起假服务 → 打印三个
环境变量 → 等回车），手工做容易出错。这个脚本挑一个空闲端口、用 `--port` 让假服务地址变成
可预测的 `http://127.0.0.1:<port>/ds-gw`，把服务用这三个变量起起来、确认 `llm_mode` 变成
`live`，再跑 `preflight --no-wait`。

原始报告：[`eval_reports/preflight_report.md`](eval_reports/preflight_report.md) 与
[`eval_reports/preflight_report.json`](eval_reports/preflight_report.json)。
摘要如下：

```
预检假模型已启动：http://127.0.0.1:49344/ds-gw
  LLM_BASE_URL=http://127.0.0.1:49344/ds-gw
  LLM_API_KEY=preflight-key-3b9c1f
  LLM_MODEL=preflight-model-7f3a

编号  检查项                                                            结果
P1    服务确实把请求发到了注入的 LLM_BASE_URL（含路径前缀）             通过  共观察到 60 次 POST /ds-gw/chat/completions
P2    请求里的 model 等于注入的 LLM_MODEL                               通过  全部请求都用了 preflight-model-7f3a
P3    注入的 Key 以 Authorization: Bearer 发送                          通过  全部请求都带了正确的 Bearer Key
P4    只用了 DeepSeek 文档列出的顶层参数                                通过  只出现了文档列出的顶层参数
P5    max_tokens 不设，或不小于 2048                                    通过  max_tokens 都不小于 2048
P6    没有访问 {prefix}/chat/completions 之外的任何路径                 通过  只访问了 POST /ds-gw/chat/completions
P7    工具定义规范，且每一个工具调用都以 role=tool + tool_call_id 回传  通过  44 个工具调用的结果都正确回传
P8    每个场景下 /api/chat 都返回 HTTP 200 与字段完整的合法 JSON        通过  32 次问答全部 200 且字段完整
P9    模型不可用时给出结构化 refusal，answer 从不是空串                 通过  失败场景都给了结构化 refusal，没有把半截输出当回答
P10   思考内容没有漏进 answer / citations / data_evidence               通过  32 次回答里思考标记都没有出现在任何对外字段里
P11   /api/chat 在时限内返回（含长时间无响应的场景）                    通过  最慢一次 120.05 秒，在 180 秒以内
P12   注入环境变量后 /api/health 报告 llm_mode = live                   通过  llm_mode = live
P13   多轮工具调用之间 reasoning_content 原样回传（没有触发 400）       通过  18 次多轮请求都原样回传了 reasoning_content
P14   保持连接的空行与 SSE 注释没有把服务弄坏                           通过  空行与 `: keep-alive` 都被正确跳过

预检通过：在 OpenAI 兼容这条路线上，我们能原样接上你的服务。
```

预检覆盖的场景包括：`normal`（多轮 + 一条消息多个工具调用）、`thinking_starved`、
`empty_content`、`json_empty`、`bad_tool_args`、`content_filter`、`insufficient_resource`、
`aborted`、`http_401/402/422/429/500/503`、`slow`（保持连接）、`hang`（长时间不响应）。

## 8. 已知限制

1. **保持思考模式开启**。理由：这道作业的题目里混合问题（「618 当天 S02 的牛肉poke 卖了
   多少份，达到目标了吗？」）需要先规划再取数再检索文档，思考模式下规划更稳。
   代价是慢（预检里最慢一次 120 秒）与贵。如果你们更看重速度，可以在
   `live.py` 的请求体里加 `thinking: {"type": "disabled"}`——这是**唯一**一处需要改代码
   才能切的开关，我没有把它做成环境变量，因为契约 §7.3 说这个选择由实现者定并在 README
   写明理由即可。关闭后预检的 P10 与 P13 会显示「未检查」（规范允许，不扣分）。
2. **`live` 模式从不产出 `data_evidence[].sql`**。契约 §5 允许「工具调用」与「SQL」二选一，
   本实现统一用 `tool` + `params` + `result`。后果是：模型如果自己写了一段 SQL（走 `run_sql`
   工具），它在证据里也是以 `tool: "run_sql"` 的形式出现，而不是顶层 `sql` 字段。SQL 的只读
   约束由工具层强制执行（语句白名单 `SELECT`/`WITH` + 必须有 `FROM` + 连接开
   `PRAGMA query_only`），不依赖评测侧再校验一遍。
3. **`/api/trace` 存在内存里**，只保留最近 200 条，服务重启即清空。契约没有要求持久化，
   但跨重启追查历史问题会取不到 trace。
4. **单一上游**。没有做多厂商自动降级：`LLM_BASE_URL` 指向谁就用谁，对方挂了就返回结构化
   refusal，不会悄悄换一家。
5. **`response_format` 没有使用**。契约 §7.3 提到 JSON 模式偶尔返回空内容；本实现的
   结构化输出一律靠工具调用（`tools` + `tool_choice`），不依赖 JSON 模式。
6. **预检的假服务行为是按文档实现的，未与真实接口对照过**。真实 DeepSeek 接口上如果
   出现与预检不同的行为，最可能出现在错误码响应体结构与 `insufficient_system_resource`
   的重试上——这两处我按「宁可重试一次、也不要把半截输出当回答」处理，
   重试仍失败就返回结构化 refusal 并把真实原因写进 trace。
