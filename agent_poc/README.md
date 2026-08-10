# 最小运营 Agent POC

这是第一版本地切片，按老师意见只验证“用户行为 → 行为分析 → 行为判断”。Nasdaq 是项目预留的目标客户位；当前 8 条行为用于验证最小架构，正式行为数据确认后可直接替换。画像候选、运营建议和审计字段只作为分析结果中的辅助信息，不扩展完整多 Agent 架构。

## 运行

在 `D:\AAAAA` 下执行：

```powershell
$py = "C:\Users\CluckinVV\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py -m unittest discover -s agent_poc/tests -v
& $py agent_poc/run_demo.py
& $py agent_poc/run_consult.py "今天有哪些融资事件" --limit 5
& $py agent_poc/run_live_agent.py --limit 5
& $py agent_poc/run_ingest.py --category news --category investment --category company --category policy --category bidding --limit 20
& $py agent_poc/run_cleanup.py --days 15
```

输出位于 `agent_poc/output/`：

- `news_snapshot_100.json`：从真实 `intelligence_export_100.xlsx` 读取的 100 条新闻快照；
- `data/data_agent_handoff.json`：模拟数据 Agent 的交接结果，包含内容状态和版本；
- `behavior_analysis_run.json`：一次合作伙伴行为分析结果；
- `live_consultation.json`：一次来自 `data.iyiou.com` 官方只读接口的咨询结果；
- `live_operation_answer.json` / `live_operation_answer.md`：模拟客户、官网实时来源和 Qwen 分析的一体化咨询结果；
- `data/iyiou_local.sqlite3`：本地 SQLite 新闻、投资、企业、政策和招投标数据缓存；
- `agent_run_log.jsonl`：运行审计日志。

## 当前边界

- 只有本机配置 `DASHSCOPE_API_KEY` 时才调用 Qwen Flash，Key 不写入文件、日志或 Git；
- 不发送邮件、不发布内容、不写正式画像；
- `partners.json` 同时预留 Nasdaq 目标客户位和程少楷主要服务客户空位；
- 当前 8 条用户行为是明确标注的 POC 行为样例，不替代正式客户行为数据；
- 运营 Agent 已接入 `https://apidata.iyiou.com` 的官网只读入口，已配置资讯、投资事件、企业、政策、招投标、行业和首页汇总；具体接口是否可读取取决于官网权限；
- 全局搜索、部分行业研究/报告和部分招投标接口需要登录，未配置授权时必须返回 `needs_auth`，不能用假数据补齐；
- 新闻只保留真实 `report_id`、时间和来源链接，语义匹配要等上游分类/核验状态进入契约后再放开。
- Demo 现在只使用交接状态合格的内容；翻译待更新、去重重叠、公司匹配不明确或发布状态不合格的内容会被阻断并生成反馈。

## 当前规则

- `article_view=1`、`search=2`、`company_query=3`、`report_download=4`、`material_request=5`、`meeting_request=6`；
- 资料/下载/订阅请求 → “评估”；明确合作或会议请求 → “推进”；重复主动互动 → “了解”；单次浏览 → “关注”；
- 同一主题至少两次主动行为，或出现订阅/资料请求，才生成画像候选；候选状态固定为 `needs_review`。

## 官方数据咨询入口

`agent_poc/iyiou_data_agent.py` 是面向 `data.iyiou.com` 的只读数据适配器，先识别咨询类别，再调用官方接口并统一返回来源、记录 ID、时间、摘要和关键属性。当前支持：

- 资讯/新闻；
- 融资/投资事件；
- 企业；
- 政策；
- 招投标；
- 行业指标/图表入口；
- 需要登录的全局搜索边界提示。

适配器只使用 GET，不执行订阅、关注、导出、提交、发送或修改操作。若后续确认有权限，可通过环境变量 `IYIOU_DATA_AUTH` 提供已授权的 `Auth` 值，不把该值写入代码、文件或日志。

## 新会议要求的本地骨架

- `conversation_memory.py`：按目标、约束、决定、纠错、未解决问题、证据和最近窗口压缩会话；重复闲聊不进入工作记忆。
- `retention_policy.py` / `run_cleanup.py`：默认按 15 天生成清理计划；审计日志、`legal_hold` 和无时间戳记录默认保留。只有明确加 `--apply` 才会改写 JSONL。
- `data_store.py` / `run_ingest.py`：使用 SQLite 保存官网归一化来源记录，按 `(record_type, record_id)` 幂等更新。
- `qwen_client.py` / `run_qwen_smoke.py`：DashScope OpenAI-compatible Qwen 适配器，Key 只从 `DASHSCOPE_API_KEY` 读取；当前对话中暴露的 Key 不使用，必须轮换后再配置。

当前服务目标已经调整为：面向计划在美股上市的海外企业，识别中国与海外市场对同一事件的权重差异，并进一步说明这些真实资讯对业务、融资、合规和上市准备有什么帮助。Qwen 只生成结构化候选判断，来源、证据、不确定性和人工审核状态必须保留。

## 实时咨询最小闭环

`run_live_agent.py` 默认模拟 Nasdaq 客户并执行：

```text
模拟客户行为判断
→ 读取 data.iyiou.com 最新融资记录
→ 为每条记录补齐亿欧官网详情页
→ 将真实记录、record_id 和链接一起交给 Qwen Flash
→ 回答“这些资讯对拟美股上市企业有什么帮助”
→ 独立输出官网来源清单和人工审核提示
```

PowerShell 中先配置 Key，再运行：

```powershell
$env:DASHSCOPE_API_KEY = [System.Net.NetworkCredential]::new("", (Read-Host "请输入 DashScope Key" -AsSecureString)).Password
$env:DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:DASHSCOPE_MODEL = "qwen-flash"
& $py agent_poc/run_live_agent.py --limit 5
```

如果没有 Key，程序仍会展示最新官网记录和链接，但状态为 `sources_ready_model_not_run`，不会伪造模型分析。

## POC 的供给侧差异化

本项目不把“提高新闻整理效率”当作主要卖点。当前最小差异化是：持续读取客户看不全的供给侧事实，用真实来源、证据编号和可打开链接，解释这些变化对融资准备、合规准备、投资者沟通和上市节奏有什么帮助。模型不能替代来源，运营判断必须可追溯并保留人工审核。
