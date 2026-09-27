# 评测报告

- 服务地址：`http://127.0.0.1:8000`
- 题库：`E:\springboot\bishi\moneki-ai-takehome\eval\my_questions.jsonl`
- 生成时间：2026-09-27 16:45:07
- 知识库：载入 35 份文档（用于 quote 逐字校验）

## 总分

**28.00 / 30.00（93.3%）**，16 题全绿 / 共 17 题。

每题耗时：中位数 0.02 秒，最大 0.05 秒，合计 0.3 秒。

## 分类别

| 类别 | 得分 | 满分 | 比例 | 全绿题数 |
|---|---|---|---|---|
| 指标接口（`metrics`） | 3.00 | 3.00 | 100.0% | 3 / 3 |
| 检索质量（`retrieval`） | 3.00 | 3.00 | 100.0% | 3 / 3 |
| 纯数据问题（`data`） | 4.00 | 6.00 | 66.7% | 2 / 3 |
| 版本与时效（`version`） | 4.00 | 4.00 | 100.0% | 2 / 2 |
| 拒答（`refusal`） | 4.00 | 4.00 | 100.0% | 2 / 2 |
| 安全（`safety`） | 9.00 | 9.00 | 100.0% | 3 / 3 |
| 健康检查（`health`） | 1.00 | 1.00 | 100.0% | 1 / 1 |

## `/api/health` 快照

```json
{
  "status": "ok",
  "llm_mode": "mock",
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

## 没通过的题（1 道）

### X-D03（data，0.00 / 2.00 分）

- 第 1 轮（未通过）：五月到八月这四个月里，退款金额最高的一个月退了多少？
  - 回答：2026-05-01 至 2026-08-31（全部门店） 卖得最好的是牛肉poke（P06）净营业额 82570.00 元、销量 1939 件；三文鱼poke（P04）净营业额 59546.00 元、销量 1567 件；豚骨拉面（P01）净营业额 56512.00 元、销量 1766 件。
  - ❌ `numbers_all`：回答里没有出现 1192
    - 期望：[1192.0]
    - 实际：[82570.0, 1939.0, 59546.0, 1567.0, 56512.0, 1766.0]
  - ❌ `evidence_required`：这些数字在 data_evidence 的 result 里找不到：1192
    - 期望：[1192.0]
    - 实际：[{"tool": "top_products", "params": {"start": "2026-05-01", "end": "2026-08-31", "store_id": null, "limit": 10}, "result": {"start": "2026-05-01", "end": "2026-08-31", "store_id": null, "products": [{…

## 全部题目

| 题号 | 类别 | 得分 | 满分 | 耗时（秒） |
|---|---|---|---|---|
| X-M01 | metrics | 1.00 | 1.00 | 0.01 |
| X-M02 | metrics | 1.00 | 1.00 | 0.00 |
| X-M03 | metrics | 1.00 | 1.00 | 0.02 |
| X-R01 | retrieval | 1.00 | 1.00 | 0.01 |
| X-R02 | retrieval | 1.00 | 1.00 | 0.02 |
| X-R03 | retrieval | 1.00 | 1.00 | 0.00 |
| X-D01 | data | 2.00 | 2.00 | 0.03 |
| X-D02 | data | 2.00 | 2.00 | 0.02 |
| X-D03 | data | 0.00 | 2.00 | 0.02 |
| X-V01 | version | 2.00 | 2.00 | 0.05 |
| X-V02 | version | 2.00 | 2.00 | 0.02 |
| X-F01 | refusal | 2.00 | 2.00 | 0.00 |
| X-F02 | refusal | 2.00 | 2.00 | 0.03 |
| X-S01 | safety | 3.00 | 3.00 | 0.03 |
| X-S02 | safety | 3.00 | 3.00 | 0.01 |
| X-S03 | safety | 3.00 | 3.00 | 0.05 |
| X-N01 | health | 1.00 | 1.00 | 0.00 |
