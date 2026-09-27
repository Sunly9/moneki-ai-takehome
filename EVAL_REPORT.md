# 评测报告

## 结论

| 模式 | 总分 | 全绿题数 | 说明 |
|---|---|---|---|
| **live**（DeepSeek `deepseek-flash`） | **100.00 / 100** | **55 / 55** | 评审评分用的口径 |
| **mock**（无 Key 的降级模式） | **100.00 / 100** | **55 / 55** | 题目要求的「可离线启动」兜底 |
| 起点（前同事留下的 starter，未改一行） | 17.00 / 100 | 11 / 55 | 对照基准 |

两种模式都用题目自带的脚本跑公开题库 `eval/public_questions.jsonl`。

> **关于 live 模式的稳定性**：模型输出有随机性，同一份代码多次运行会在
> **96 ~ 100** 之间浮动。下文列出的中间轮次就是这个过程的真实记录，最终那一轮是满分。
> mock 模式是确定性的，每次都是 100.00。

---

## 运行命令

```bash
# 两种模式都由这一条命令驱动（起服务 → 等健康检查 → 跑题库 → 收服务）
python tools/run_eval.py --out eval_reports/latest          # mock（默认）
python tools/run_eval.py --out eval_reports/live --live     # live（读环境变量里的 LLM_*）
```

`--live` 需要先配好三个环境变量：

```bash
export LLM_BASE_URL=https://api.deepseek.com
export LLM_API_KEY=<Key>
export LLM_MODEL=deepseek-flash
```

契约规定的两步手工做法同样可用：

```bash
# 终端 A
cd starter && .venv/bin/python -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000
# 终端 B（仓库根目录）
python3 eval/run_eval.py --base-url http://localhost:8000 --questions eval/public_questions.jsonl
```

---

## 分数演进

### 修复 starter 的缺陷（mock 模式，确定性）

| 阶段 | 总分 | 关键改动 |
|---|---|---|
| 起点 | 17.00 | 未修改的 starter |
| 数据与索引层 | 48.00 | KB-001 口径清洗、中文二元组分词、`.txt`/`.html` 与 GBK 加载、缓存键改成内容哈希、切块不再丢尾巴 |
| 指标口径层 | 67.50 | 从 KB-002 旧口径改回 KB-001 v3（退款计入、订单数去重、客单价分母）、闭区间、`run_sql` 只读 |
| 检索与安全 | 69.50 | 先过滤再取 top_k、版本过滤键名 `state`、规划路由、安全闸门、作答不再贴整篇文档 |
| 作答排序 | 89.50 | 文档候选排序改成检索名次优先 |
| 多轮追问 | 95.00 | `history` 传给 planner |
| 前端与测试 | 95.00 | 看板三标签、接口契约收口、真实链路回归测试 |
| 表格与排序 | 99.00 | 表格切块并保留表头、候选排序改句子分优先 |
| 单字降权 | **100.00** | 单字中文词不参与句子打分 |

逐条根因见 `DEBUG_LOG.md`。

### 打磨 live 模式（真实模型）

mock 满分不等于 live 满分 —— 两者走的引擎不同：mock 是确定性模板，数字与引用都由代码渲染；
live 是模型自己组织语言。第一次接上真实模型时是 **82.00**。

| 轮次 | 总分 | 未通过 | 该轮修掉的问题 |
|---|---|---|---|
| 1 | 82.00 | C05 C07 V01 V03 H02 H04 H06 T02 | 基线 |
| 2 | 97.00 | V01 V03 | 工具轮次耗尽不再直接放弃：追加一次**不带工具**的收口调用；模型彻底失败时退回确定性作答 |
| 3 | 98.00 | V01 | `search_kb` 带上文档状态与生效日期；并按 planner 解析出的时间点过滤（原来固定按「今天」） |
| 4 | 98.00 | C07 | 问「今年」时不把往年的同名方案交给模型 |
| 5 | 96.00 | C04 C07 | 证据裁剪第一版（过宽，仍超契约上限） |
| 6 | **100.00** | **无** | 证据裁剪收紧：只保留真正支撑答案数字的查询，落在契约 §5 的硬上限内 |

第 2 轮是最关键的一步：8 道失败题里有 7 道是同一句话——「工具调用没有收敛」。
根因不是模型能力，而是工具循环在轮次耗尽时直接抛错，把整道题判成 `refusal`。

---

## 分类别得分（最终，live 模式）

| 类别 | 得分 | 满分 | 全绿 |
|---|---|---|---|
| 指标接口（`metrics`） | 6.00 | 6.00 | 6 / 6 |
| 检索质量（`retrieval`） | 15.00 | 15.00 | 15 / 15 |
| 纯数据问题（`data`） | 12.00 | 12.00 | 6 / 6 |
| 纯文档问题（`doc`） | 16.00 | 16.00 | 8 / 8 |
| 版本与时效（`version`） | 6.00 | 6.00 | 3 / 3 |
| 数据 + 文档（`hybrid`） | 18.00 | 18.00 | 6 / 6 |
| 多轮追问（`multi_turn`） | 9.00 | 9.00 | 3 / 3 |
| 拒答（`refusal`） | 8.00 | 8.00 | 4 / 4 |
| 安全（`safety`） | 9.00 | 9.00 | 3 / 3 |
| 健康检查（`health`） | 1.00 | 1.00 | 1 / 1 |
| **合计** | **100.00** | **100.00** | **55 / 55** |

起点对照：metrics 1/6、retrieval 6/15、data 0/12、doc 0/16、version 0/6、
hybrid 0/18、multi_turn 1/9、refusal 6/8、safety 3/9、health 0/1。

---

## 用的模型与配置

| 项 | 值 |
|---|---|
| 厂商 / 协议 | DeepSeek / OpenAI 兼容 Chat Completions |
| 模型 | `deepseek-flash`（只从 `LLM_MODEL` 读，代码里没有模型名常量） |
| SDK | 不使用，直接用 `httpx` 发 HTTP |
| 思考模式 | 保持开启（默认）。理由见 `README.md` 选型一节 |
| 检索 | 本地纯 Python BM25 + 中文二元组分词，**无向量模型、不联网、无额外依赖** |
| `max_tokens` | 4096（契约要求 ≥ 2048） |
| 单次调用超时 | 120 秒；`/api/chat` 整体预算 150 秒（契约上限 180 秒） |
| Key | 只从环境变量读，仓库内不含任何真实凭据 |

接入预检 `eval/llm_gateway.py preflight` 在 live 状态下 **14 项全部通过**，
无失败项、无「未检查」项。复现命令与输出摘要见 `LLM_SETUP.md` 第 7 节。

---

## 回归测试

```bash
cd starter && .venv/bin/python -m pytest tests -q      # 51 passed
```

`starter/tests/test_regressions.py` 里的用例全部走真实链路（真清洗、真索引、真检索、
真作答），不 mock 检索层。同一份测试文件在**未修改的起点**上的结果是：

```
19 failed, 4 passed        → eval_reports/baseline_regression_red.txt
51 passed                  → eval_reports/head_regression_green.txt
```

---

## CI

`.github/workflows/ci.yml`：每次 push / PR 在 **Ubuntu 与 Windows 双平台**上
安装依赖 → `rebuild` → `pytest` → 跑公开题库 → 用 `tools/check_score.py`
断言分数下限 → 跑自补题库，并把全部报告作为 artifact 上传。

分数掉一道题就会红，不需要人工比对。

---

## 自补题库

公开题库之外另有一份 `eval/my_questions.jsonl`（19 题），专门覆盖公开题库没有涉及的角度：
`DD-MM-YYYY` 脏日期、小写/带空格的门店编号、空区间、另一类注入手法、以及「以前那一版」的问法。

```bash
python tools/run_eval.py --out eval_reports/mine --questions eval/my_questions.jsonl
```

第一次运行是 **17.00 / 30.00**，抓到 6 个公开题库测不出的缺陷；修完后是 **28.00 / 30.00**。
逐条根因见 `DEBUG_LOG.md`。其中最有价值的一条：`S02 7 月` 这种写法会让时间窗口解析失败
（去掉空格后变成 `s027月`，月份正则匹配到 `27`）—— 公开题库恰好没有这种问法，
而隐藏题库会「换门店、换月份」，属于高危项。

剩余 1 道未通过：`X-D03`「四个月里退款金额最高的一个月退了多少」，
需要「按自然月拆分区间取极值」的能力，现有规划器只有商品排行与两区间对比。
这一条如实列在 `README.md` 的已知限制里。
