# EqualOcean — Auditable AI Operations Agent POC

面向海外企业订阅与运营分析场景的 AI 工作流原型。项目重点不是让模型直接替代业务决策，而是把来源、状态、判断依据和人工复核连接成可追踪流程。

## What it explores

- 多来源记录的字段标准化与幂等入库
- 基于 SQLite 的状态、客户上下文与记忆管理
- 来源校验、质量门禁与异常路径处理
- 模型建议与人工决策之间的明确权限边界
- 可复现的本地运行、测试与交接文档

## Workflow

```text
source records
  -> normalize and validate
  -> idempotent SQLite ingestion
  -> customer question/context
  -> candidate analysis
  -> quality gate
  -> human review
```

## Repository status

This public repository is a portfolio baseline. The local working version may be ahead of the public code and has been verified with 62 unit tests. No production availability, autonomous business decision or unrestricted internal-data access is claimed.

## Why this matters

The project treats traceability, reversibility and reviewability as product requirements. Important outputs retain source evidence, and low-confidence or high-risk cases are routed to people.

## Author

[Cluckin-VV](https://github.com/Cluckin-VV)
