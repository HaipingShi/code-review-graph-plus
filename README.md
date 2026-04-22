# code-review-graph-plus

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.3.2--post1-orange)](https://github.com/HaipingShi/code-review-graph-plus)

**English** | [中文](README.zh.md)

---

## Stop explaining your code to AI over and over.

Every time you start a new chat with Claude, Cursor, or any AI assistant, you spend the first 20 minutes feeding it files, explaining architecture, and correcting misunderstandings.

**code-review-graph-plus** builds a persistent knowledge graph from your codebase — once. After that, every AI conversation starts with full context: module relationships, call chains, security risks, and architectural hotspots.

No more "let me show you the relevant files." The AI already knows.

---

## What it does in 30 seconds

```bash
pip install "git+https://github.com/HaipingShi/code-review-graph-plus.git"
cd your-project
code-review-graph-plus install   # hook into Claude / Cursor / Windsurf
code-review-graph-plus build     # one-time scan
```

Now open any AI chat in that project. Instead of pasting code, ask:

- *"Which functions will break if I refactor `auth.py`?"*
- *"Find all unprotected paths where passwords reach log sinks."*
- *"Show me the most critical execution flows in this codebase."*
- *"Has our architecture cohesion been improving or degrading over the last month?"*

The AI answers instantly because it has 32 specialized tools querying a live graph of your code.

---

## Before vs After

| | **Before** | **After** |
|---|---|---|
| **New AI chat** | Paste files, explain architecture, wait for AI to catch up | AI already knows your project structure |
| **Code review** | Read diff line-by-line, guess side effects | AI traces impact radius across call chains |
| **Security audit** | Manual grep for `password`, `token`, `log` | Automatic source → sink path tracing with risk scoring |
| **Refactoring** | Hope you didn't miss anything | AI highlights every affected function and dead code |
| **Architecture health** | "Feels messy" | Quantified: cohesion, coupling, community fragmentation trends |
| **Token cost** | Burn 5k–20k tokens per chat just explaining context | Zero context tokens — graph is pre-loaded |

---

## Core capabilities

**🔍 Instant project comprehension**
AI reads your entire codebase structure — files, classes, functions, imports, calls — in a single build. No more file-by-file explanations.

**🛡️ Security data-flow audit**
Automatically finds where sensitive data (passwords, tokens, secrets) is produced, where it might leak (logs, responses, files), and whether it passes through encryption or sanitization along the way.

**📈 Technical debt trend tracking**
Records architecture health snapshots after every build. Track if your code is getting more cohesive or more fragmented over time. Get alerts before it becomes unmanageable.

**🏛️ Architecture analysis**
Detects natural code communities, hotspots (most-connected nodes), architectural chokepoints, and surprising coupling — using only production code, so test files don't pollute the metrics.

---

## Architecture

Based on a real build of this project (55 files, 569 nodes, 5,489 edges, 43 communities):

[<img src="docs/images/architecture-overview.png" alt="code-review-graph-plus architecture" width="100%">](docs/architecture-overview.html)

> Click the image for an interactive version. Run `code-review-graph-plus visualize` to generate the same for your project.

---

## Quick start

```bash
# 1. Install MCP config (auto-detects Claude, Cursor, Windsurf, etc.)
code-review-graph-plus install

# 2. Register your project
cd /path/to/your-project
code-review-graph-plus register .

# 3. Build the knowledge graph (one-time, ~1-3 min)
code-review-graph-plus build

# 4. Check status
code-review-graph-plus status
```

That's it. Open any AI chat in that project and start asking architecture-level questions.

---

## Installation

```bash
pip install "git+https://github.com/HaipingShi/code-review-graph-plus.git"
```

For development:

```bash
git clone https://github.com/HaipingShi/code-review-graph-plus.git
cd code-review-graph-plus
pip install -e .
```

---

## What's different from the original

| | Original | This fork |
|---|---|---|
| Architecture analysis | Includes test code | **Production-only** — tests excluded from communities, hubs, bridges |
| Tech debt tracking | None | **Snapshots + threshold/trend alerts** |
| Security audit | None | **Auto source/sink classification + unprotected path tracing** |
| Community naming | Basic | **Enhanced stop-word filtering + cross-community wiki links** |

---

## MCP tools at a glance (32 total)

<details>
<summary>🏗️ Build & Explore</summary>

`build_or_update_graph` · `get_impact_radius` · `query_graph` · `semantic_search_nodes` · `list_graph_stats` · `traverse_graph`

</details>

<details>
<summary>🔍 Review & Changes</summary>

`get_review_context` · `detect_changes` · `get_affected_flows`

</details>

<details>
<summary>🏛️ Architecture</summary>

`list_communities` · `get_community` · `get_architecture_overview` · `list_flows` · `get_hub_nodes` · `get_bridge_nodes` · `get_knowledge_gaps` · `get_surprising_connections` · `get_suggested_questions`

</details>

<details>
<summary>🔧 Refactoring</summary>

`refactor` · `apply_refactor` · `find_large_functions`

</details>

<details>
<summary>📚 Knowledge & Search</summary>

`embed_graph` · `generate_wiki` · `get_wiki_page` · `get_docs_section` · `cross_repo_search`

</details>

<details>
<summary>📈 Trend Tracking</summary>

`get_debt_trends` · `compare_snapshots`

</details>

<details>
<summary>🛡️ Security Audit</summary>

`audit_security_flows` · `get_security_nodes` · `get_unprotected_paths` · `get_security_critical_flows`

</details>

---

## Who is this for?

- **Solo developers** who switch between AI chats and don't want to re-explain their project every time
- **Teams doing code review** who want AI to understand cross-file impact before suggesting changes
- **Engineers refactoring legacy code** who need to know what breaks before they touch anything
- **Security-conscious teams** who want automated data-flow auditing without manual grep
- **Tech leads** who want quantified architecture health metrics over time

---

## License

MIT. See [LICENSE](LICENSE).
