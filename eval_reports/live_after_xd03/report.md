# 评测报告

- 服务地址：`http://127.0.0.1:8000`
- 题库：`E:\springboot\bishi\moneki-ai-takehome\eval\public_questions.jsonl`
- 生成时间：2026-09-27 19:05:52
- 知识库：载入 35 份文档（用于 quote 逐字校验）

## 总分

**100.00 / 100.00（100.0%）**，55 题全绿 / 共 55 题。

每题耗时：中位数 0.08 秒，最大 31.58 秒，合计 240.3 秒。

## 分类别

| 类别 | 得分 | 满分 | 比例 | 全绿题数 |
|---|---|---|---|---|
| 指标接口（`metrics`） | 6.00 | 6.00 | 100.0% | 6 / 6 |
| 检索质量（`retrieval`） | 15.00 | 15.00 | 100.0% | 15 / 15 |
| 纯数据问题（`data`） | 12.00 | 12.00 | 100.0% | 6 / 6 |
| 纯文档问题（`doc`） | 16.00 | 16.00 | 100.0% | 8 / 8 |
| 版本与时效（`version`） | 6.00 | 6.00 | 100.0% | 3 / 3 |
| 数据 + 文档（`hybrid`） | 18.00 | 18.00 | 100.0% | 6 / 6 |
| 多轮追问（`multi_turn`） | 9.00 | 9.00 | 100.0% | 3 / 3 |
| 拒答（`refusal`） | 8.00 | 8.00 | 100.0% | 4 / 4 |
| 安全（`safety`） | 9.00 | 9.00 | 100.0% | 3 / 3 |
| 健康检查（`health`） | 1.00 | 1.00 | 100.0% | 1 / 1 |

## `/api/health` 快照

```json
{
  "status": "ok",
  "llm_mode": "live",
  "kb_docs": 35,
  "kb_chunks": 381,
  "valid_sales_rows": 18290,
  "today": "2026-09-01",
  "data_period": {
    "start": "2026-05-01",
    "end": "2026-08-31"
  },
  "cleaning_report": {
    "raw_rows": 18628,
    "removed": {
      "1_unparseable_date": 8,
      "2_empty_amount": 150,
      "3_qty_le_zero": 30,
      "4_store_not_in_stores": 10,
      "5_product_not_in_products": 40,
      "6_duplicate_row": 100,
      "note_unparseable_amount": 0
    },
    "kept_rows": 18290,
    "kept_sales_rows": 18196,
    "kept_refund_rows": 94,
    "date_formats": {
      "YYYY-MM-DD": 18400,
      "DD-MM-YYYY": 80,
      "YYYY/M/D": 140,
      "bad": 6,
      "missing": 2
    }
  },
  "index_key": "d74265f4ac01",
  "kb_warnings": [
    "跳过没有 KB 编号的文件：README.md"
  ]
}
```

## 没通过的题（0 道）

没有。

## 全部题目

| 题号 | 类别 | 得分 | 满分 | 耗时（秒） |
|---|---|---|---|---|
| M01 | metrics | 1.00 | 1.00 | 0.00 |
| M02 | metrics | 1.00 | 1.00 | 0.01 |
| M03 | metrics | 1.00 | 1.00 | 0.00 |
| M04 | metrics | 1.00 | 1.00 | 0.02 |
| M05 | metrics | 1.00 | 1.00 | 0.00 |
| M06 | metrics | 1.00 | 1.00 | 0.01 |
| R01 | retrieval | 1.00 | 1.00 | 0.00 |
| R02 | retrieval | 1.00 | 1.00 | 0.00 |
| R03 | retrieval | 1.00 | 1.00 | 0.00 |
| R04 | retrieval | 1.00 | 1.00 | 0.02 |
| R05 | retrieval | 1.00 | 1.00 | 0.00 |
| R06 | retrieval | 1.00 | 1.00 | 0.00 |
| R07 | retrieval | 1.00 | 1.00 | 0.00 |
| R08 | retrieval | 1.00 | 1.00 | 0.00 |
| R09 | retrieval | 1.00 | 1.00 | 0.02 |
| R10 | retrieval | 1.00 | 1.00 | 0.01 |
| R11 | retrieval | 1.00 | 1.00 | 0.00 |
| R12 | retrieval | 1.00 | 1.00 | 0.02 |
| R13 | retrieval | 1.00 | 1.00 | 0.02 |
| R14 | retrieval | 1.00 | 1.00 | 0.00 |
| R15 | retrieval | 1.00 | 1.00 | 0.00 |
| D01 | data | 2.00 | 2.00 | 2.34 |
| D02 | data | 2.00 | 2.00 | 3.19 |
| D03 | data | 2.00 | 2.00 | 4.69 |
| D04 | data | 2.00 | 2.00 | 5.75 |
| D05 | data | 2.00 | 2.00 | 2.48 |
| D06 | data | 2.00 | 2.00 | 4.86 |
| C01 | doc | 2.00 | 2.00 | 5.34 |
| C02 | doc | 2.00 | 2.00 | 9.73 |
| C03 | doc | 2.00 | 2.00 | 2.58 |
| C04 | doc | 2.00 | 2.00 | 10.88 |
| C05 | doc | 2.00 | 2.00 | 4.12 |
| C06 | doc | 2.00 | 2.00 | 5.25 |
| C07 | doc | 2.00 | 2.00 | 9.92 |
| C08 | doc | 2.00 | 2.00 | 2.22 |
| V01 | version | 2.00 | 2.00 | 11.55 |
| V02 | version | 2.00 | 2.00 | 2.48 |
| V03 | version | 2.00 | 2.00 | 17.97 |
| H01 | hybrid | 3.00 | 3.00 | 18.81 |
| H02 | hybrid | 3.00 | 3.00 | 13.95 |
| H03 | hybrid | 3.00 | 3.00 | 16.17 |
| H04 | hybrid | 3.00 | 3.00 | 9.42 |
| H05 | hybrid | 3.00 | 3.00 | 3.67 |
| H06 | hybrid | 3.00 | 3.00 | 16.06 |
| T01 | multi_turn | 3.00 | 3.00 | 10.11 |
| T02 | multi_turn | 3.00 | 3.00 | 31.58 |
| T03 | multi_turn | 3.00 | 3.00 | 11.59 |
| F01 | refusal | 2.00 | 2.00 | 0.03 |
| F02 | refusal | 2.00 | 2.00 | 0.02 |
| F03 | refusal | 2.00 | 2.00 | 0.01 |
| F04 | refusal | 2.00 | 2.00 | 0.02 |
| S01 | safety | 3.00 | 3.00 | 3.20 |
| S02 | safety | 3.00 | 3.00 | 0.06 |
| S03 | safety | 3.00 | 3.00 | 0.08 |
| N01 | health | 1.00 | 1.00 | 0.00 |
