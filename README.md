# EqualOcean 运营 Agent POC

面向计划在美国资本市场上市的海外企业，验证一条最小、可解释的运营 Agent 链路：

```text
模拟客户行为
→ 行为计分与阶段判断
→ 读取 data.iyiou.com 最新真实资讯
→ 附上官网详情页和来源 ID
→ Qwen Flash 分析“这些资讯对客户有什么帮助”
→ 人工审核
```

当前重点不是复杂多 Agent，而是把“真实官网事实、可追溯证据和客户帮助判断”做扎实。

## 运行

在项目目录执行：

```powershell
$py = "C:\Users\CluckinVV\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

& $py -m unittest discover -s agent_poc/tests -v
& $py agent_poc/run_demo.py
& $py agent_poc/run_consult.py "今天有哪些融资事件" --limit 5
```

需要 Qwen 分析时，在本机 PowerShell 中安全输入 Key：

```powershell
$env:DASHSCOPE_API_KEY = [System.Net.NetworkCredential]::new("", (Read-Host "请输入 DashScope Key" -AsSecureString)).Password
$env:DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:DASHSCOPE_MODEL = "qwen-flash"

& $py agent_poc/run_live_agent.py --limit 5
```

Key、SQLite、本地输出、日志和缓存均被排除在 Git 提交之外。

详细说明见 [agent_poc/README.md](agent_poc/README.md) 和 [operation_agent_workflow.md](operation_agent_workflow.md)。
