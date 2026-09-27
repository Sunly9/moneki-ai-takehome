# 评测报告

## 结论

| | 总分 | 全绿题数 | 报告目录 |
|---|---|---|---|
| **起点**（前同事留下的 starter，一个字没改） | **17.00 / 100** | 11 / 55 | `eval_reports/baseline/` |
| **最终** | **100.00 / 100** | **55 / 55** | `eval_reports/layer11/` |

跑的都是**公开题库** `eval/public_questions.jsonl`，用的是题目自带的评测脚本。

> **关于「commit」这一栏**：开发过程中建过 12 个分阶段 commit，整理阶段按要求重置过一次，
> 哈希已不再有效，所以下面用**阶段名**指代（对照表见 `DEBUG_LOG.md` 顶部）。
> 分阶段的提交历史会随最终仓库一并给出。

---

## 运行命令

每一次得分都是下面这条命令产生的（在仓库根目录执行）：

```bash
python tools/run_eval.py --out eval_reports/<目录名>
```

`tools/run_eval.py` 是一层薄封装：起服务 → 轮询 `/api/health` 直到就绪 →
调用作业包自带的 `eval/run_eval.py` → 收服务 → 打印分类别得分与未通过题号。
等价的手工两步是：

```bash
# 终端 A
cd starter && .venv/bin/python -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000
# 终端 B（仓库根目录）
python3 eval/run_eval.py --base-url http://localhost:8000 --questions eval/public_questions.jsonl
```

---

## 分数阶梯

| 阶段 | 总分 | 未通过 | 关键改动 |
|---|---|---|---|
| `0-基线` | 17.00 | 44 题 | 冻结未修改的 starter |
| `1-数据与索引` | 48.00 | — | KB-001 口径清洗、中文二元组分词、`.txt`/`.html` 与 GBK 加载、缓存键改成内容哈希、切块不再丢尾巴 |
| `2-指标口径` | 67.50 | — | 从 KB-002 旧口径改回 KB-001 v3（退款计入、订单数去重、客单价分母）、闭区间、`kb_docs` 数入索引文档、`run_sql` 只读 |
| `3-检索与安全` | 69.50 | — | 先过滤再取 top_k、删掉改写 `doc_id` 的赋值、版本过滤键名 `state`、删掉规划器末尾的一票否决路由、接上安全闸门、作答不再贴整篇文档 |
| `4-作答排序` | 89.50 | — | 文档候选排序改成检索名次优先 |
| `5-多轮追问` | 95.00 | R04 C02 C04 | 把 `history` 传给 planner |
| `6-前端与测试` | 95.00 | R04 C02 C04 | 看板前端、接口契约收口、真实链路回归测试 |
| `7-接入与文档` | 95.00 | R04 C02 C04 | `LLM_TRACE` 开关、`LLM_SETUP.md`、`DEBUG_LOG.md` |
| `8-表格与排序` | 99.00 | V03 | 表格切块并保留表头、表格行实体加成、候选排序改句子分优先 |
| `9-单字降权` | 100.00 | **无** | 单字中文词不参与句子打分 |
| `10-补测试` | 100.00 | **无** | 4 条回归测试锁住最后 5 分的来源 |
| `11-自补题修复` | 100.00 | **无** | 自补题库发现的四处（见下） |

原始输出在 `eval_reports/` 下逐目录可查，每个目录都有 `report.json`（机器可读）与 `report.md`（人读）。

---

## 分类别得分（最终）

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

起点对照（`eval_reports/baseline/report.json`）：
metrics 1/6、retrieval 6/15、data 0/12、doc 0/16、version 0/6、hybrid 0/18、
multi_turn 1/9、refusal 6/8、safety 3/9、health 0/1。

---

## 用的模型与配置

| 项 | 值 |
|---|---|
| 是否配置了 Key | **否**。上表全部是**没有配置任何 `LLM_*` 环境变量**时的结果，`/api/health` 报 `llm_mode: "mock"` |
| 作答方式 | 本地模板作答：确定性规则规划 + KB-001 口径取数 + 抽取式逐字引用 |
| 检索 | 本地纯 Python BM25 + 中文二元组分词，**没有向量模型**，不联网 |
| 模型配置 | `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 均未设置 |
| 其它环境变量 | `DATA_DIR` / `KB_DIR` / `VAR_DIR` 均用默认值；`TODAY` 用契约默认的 `2026-09-01` |
| Python | 3.12.14（Windows） |
| 依赖 | `fastapi` / `uvicorn` / `httpx` / `pytest`，无额外依赖 |

**为什么最终分是 mock 模式的分数**：题目要求「最终得分请用你自己的大模型跑；实在没有 Key，
就跑无 Key 的降级模式，并在报告里写明」。我没有自备 DeepSeek Key，所以按后半句执行，
在这里写明。降级模式不是空壳 —— 55 题在这种模式下全部答对。

**切换后的可用性另有独立证据**：接入预检 `eval/llm_gateway.py preflight` 已经跑过，
在**配置了假模型（`llm_mode: "live"`）**的状态下驱动 `/api/chat` 走完 16 个场景、
14 项检查全部通过，没有失败项也没有「未检查」项：

```bash
python tools/run_preflight.py --out eval_reports
```

原始报告：`eval_reports/preflight_report.md` 与 `preflight_report.json`。
输出摘要与逐项说明见 [`LLM_SETUP.md`](LLM_SETUP.md) 第 7 节。

---

## 自补题库（公开题库之外）

公开题库全绿之后，我又写了一份自己的题库 `eval/my_questions.jsonl`（19 题），
专挑公开题库**没有覆盖**的角度：`DD-MM-YYYY` 脏日期、小写/带空格的门店编号、
空区间、另一类注入手法、以及「以前那一版」的问法。

```bash
python tools/run_eval.py --out eval_reports/my_questions --questions eval/my_questions.jsonl
```

第一次跑出来是 **17.00 / 30.00**，抓到 6 个公开题库测不出来的缺陷；修完后是 **28.00 / 30.00**。
逐条根因见 `DEBUG_LOG.md` 的「自补题库」一节，摘要：

| 编号 | 问题 | 结论 |
|---|---|---|
| X-D02 | 「s05 5 月的净营业额是多少？」答成了 5–8 月合计 | `S02 7 月` 去掉空格变成 `s027月`，月份正则匹配到 `27` 导致时间窗口被丢弃。公开题库恰好没有这种问法，**隐藏题库的「换门店、换月份」改写几乎一定会踩到** |
| X-D01 | 「25-07-2026 那天全店一共卖了多少？」被判成文档题 | 规划器缺少「卖了多少」这类没有指标名词、但明显在问经营数字的说法 |
| X-F02 | 「S03 店长家里养了几只猫？」答了一段门店档案 | 拒答闸门 `VOCAB_HARD_GATE=0.25` 是中文按空白切词时标定的，那时覆盖率恒为 0、闸门从没开过门。重新标定到 0.35 |
| X-V01 | 「储值充值以前那一版的赠送规则是什么？」挑错了句子 | 「以**前**那一版」的「前」匹配上「5 日**前**完成对账」。修法推广成「所有单字中文词都不参与句子打分」 |
| X-S01 | 我自己的题写错了 | 系统正确拒答，只是文案里含「系统提示词」被我的 `text_none` 判红。改成只禁止真泄漏特征 |
| X-D03 | 「四个月里退款金额最高的一个月退了多少？」 | **未实现**，见下 |

### 未通过的一道

**X-D03** 期望 1192.00（5 月的退款金额），实际答成了商品排行。
它需要「按自然月拆分区间、对某个指标取极值」的能力，而现有规划器只有
`top_products`（按商品排名）与 `compare_periods`（比两个区间），没有跨月取极值。
改动面比前面几条大，而公开题库已满分，我选择不在收尾阶段动主干链路。
这一条如实留作已知缺口。

---

## 回归测试

```bash
cd starter && .venv/bin/python -m pytest tests -q     # 48 passed
```

`starter/tests/test_regressions.py` 里的用例全部走**真实链路**（真清洗、真索引、真检索、
真作答），不 mock 检索层。同一份测试文件在**未修改的起点**上的结果是：

```
19 failed, 4 passed        → eval_reports/baseline_regression_red.txt
48 passed                  → eval_reports/head_regression_green.txt
```

红绿证据的取法：

```bash
git worktree add ../baseline_wt <原始 commit>
cp starter/tests/test_regressions.py starter/tests/conftest.py ../baseline_wt/starter/tests/
cd ../baseline_wt/starter && pytest tests/test_regressions.py -q
```

（顺带说明：starter 自带的 `tests/conftest.py` 原本会把 `Retriever.search` 整个换成
固定返回的假命中而且不还原，所以那份「17 passed 全绿」掩盖了全部检索问题 —— 这也是
前同事交接文档里「测试全部通过」这句话的真实含义。）

---

## CI

`.github/workflows/ci.yml`：每次 push / PR 在 **Ubuntu 与 Windows 双平台**上
安装依赖 → `rebuild` → `pytest` → 跑公开题库 → 用
`python tools/check_score.py eval_reports/ci --min-score 99` 断言分数下限 → 跑自补题库，
并把全部报告作为 artifact 上传。分数掉一道题就会红，不用等人肉发现。
