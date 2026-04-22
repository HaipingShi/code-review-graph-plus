# code-review-graph-plus

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.3.2--post1-orange)](https://github.com/HaipingShi/code-review-graph-plus)

**中文** | [English](README.md)

---

## 别再一遍遍给 AI 解释你的代码了

每次新开一个 Claude、Cursor 或其他 AI 助手的对话，你都要先花 20 分钟给它贴文件、讲架构、纠正误解。

**code-review-graph-plus** 给你的代码库建一个**永久记忆图谱**——只需构建一次。之后每次 AI 对话都自带完整上下文：模块关系、调用链、安全风险、架构热点。

不用再发"我给你看一下相关文件"。AI 已经知道了。

---

## 30 秒看懂它能做什么

```bash
pip install "git+https://github.com/HaipingShi/code-review-graph-plus.git"
cd your-project
code-review-graph-plus install   # 接入 Claude / Cursor / Windsurf
code-review-graph-plus build     # 一次性扫描
```

现在在这个项目里打开任意 AI 对话。不用贴代码，直接问：

- *"如果重构 `auth.py`，哪些函数会受影响？"*
- *"找出所有密码未加密就写入日志的路径。"*
- *"这个代码库里最关键的执行流是什么？"*
- *"过去一个月我们的架构健康度是在变好还是变差？"*

AI 能秒答，因为它有 32 个专业工具在实时查询你的代码图谱。

---

## 用了它之后有什么不一样

| | **以前** | **现在** |
|---|---|---|
| **新开 AI 对话** | 贴文件、讲架构、等 AI 慢慢理解 | AI 已经知道你的项目结构 |
| **代码审查** | 一行行看 diff，猜副作用 | AI 自动追踪跨文件的调用影响链 |
| **安全审计** | 手动 grep `password`、`token`、`log` | 自动追踪敏感数据从哪来、到哪去、有没有加密 |
| **重构代码** | 祈祷没漏掉什么 | AI 标出所有受影响函数和死代码 |
| **架构健康** | "感觉越来越乱了" | 量化指标：内聚度、耦合度、社区碎片化趋势 |

---

## 核心能力

**🔍 让 AI 瞬间读懂项目**
一次构建，AI 就掌握了整个代码库的结构——文件、类、函数、导入、调用关系。再也不用逐文件解释。

**🛡️ 安全数据流审计**
自动发现敏感数据（密码、Token、密钥）在哪里产生、在哪里可能泄露（日志、响应、文件）、路上有没有经过加密或脱敏。

**📈 技术债务趋势追踪**
每次构建后自动记录架构健康快照。追踪代码是在越来越凝聚还是越来越碎片化。在失控之前收到预警。

**🏛️ 架构分析**
自动识别代码社区、热点（连接最多的节点）、架构瓶颈和意外耦合——只分析生产代码，测试结果不会污染指标。

---

## 架构一览

基于本项目真实构建结果（55 文件 / 569 节点 / 5,489 边 / 43 社区）：

[<img src="docs/images/architecture-overview.png" alt="code-review-graph-plus 架构" width="100%">](docs/architecture-overview.html)

> 点击上方图片查看可交互版本。运行 `code-review-graph-plus visualize` 即可为你的项目生成同类图表。

---

## 快速开始

```bash
# 1. 安装 MCP 配置（自动识别 Claude、Cursor、Windsurf 等）
code-review-graph-plus install

# 2. 注册你的项目
cd /path/to/your-project
code-review-graph-plus register .

# 3. 构建知识图谱（一次性，约 1-3 分钟）
code-review-graph-plus build

# 4. 查看状态
code-review-graph-plus status
```

完成。在这个项目里打开任意 AI 对话，直接问架构级别的问题。

---

## 安装

```bash
pip install "git+https://github.com/HaipingShi/code-review-graph-plus.git"
```

开发模式：

```bash
git clone https://github.com/HaipingShi/code-review-graph-plus.git
cd code-review-graph-plus
pip install -e .
```

---

## 与原版的区别

| | 原版 | 本 fork |
|---|---|---|
| 架构分析 | 包含测试代码 | **仅分析生产代码**——测试不污染社区、热点等指标 |
| 技术债务追踪 | 无 | **快照 + 阈值/趋势预警** |
| 安全审计 | 无 | **自动源/汇聚点分类 + 未保护路径追踪** |
| 社区命名 | 基础 | **增强停用词过滤 + 跨社区 Wiki 引用** |

---

## MCP 工具一览（共 32 个）

<details>
<summary>🏗️ 构建与探索</summary>

`build_or_update_graph` · `get_impact_radius` · `query_graph` · `semantic_search_nodes` · `list_graph_stats` · `traverse_graph`

</details>

<details>
<summary>🔍 审查与变更</summary>

`get_review_context` · `detect_changes` · `get_affected_flows`

</details>

<details>
<summary>🏛️ 架构分析</summary>

`list_communities` · `get_community` · `get_architecture_overview` · `list_flows` · `get_hub_nodes` · `get_bridge_nodes` · `get_knowledge_gaps` · `get_surprising_connections` · `get_suggested_questions`

</details>

<details>
<summary>🔧 重构辅助</summary>

`refactor` · `apply_refactor` · `find_large_functions`

</details>

<details>
<summary>📚 知识与搜索</summary>

`embed_graph` · `generate_wiki` · `get_wiki_page` · `get_docs_section` · `cross_repo_search`

</details>

<details>
<summary>📈 趋势追踪</summary>

`get_debt_trends` · `compare_snapshots`

</details>

<details>
<summary>🛡️ 安全审计</summary>

`audit_security_flows` · `get_security_nodes` · `get_unprotected_paths` · `get_security_critical_flows`

</details>

---

## 适合谁用

- **独立开发者**：在不同 AI 对话间切换，不想每次都重新介绍项目
- **做代码审查的团队**：希望 AI 在提建议前先理解跨文件影响
- **重构遗留代码的工程师**：在动手之前就知道会牵一发而动全身
- **注重安全的团队**：想要自动化的数据流审计，不用手动 grep
- **技术负责人**：想要可量化的架构健康度指标和趋势

---

## 许可证

MIT。详见 [LICENSE](LICENSE)。
