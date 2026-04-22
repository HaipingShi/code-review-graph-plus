# Agent Guide: code-review-graph-plus Fork

> Quick orientation for LLMs working on this codebase.

## What This Is

A personal fork of [code-review-graph](https://code-review-graph.com) v2.3.2 — an MCP server that builds a persistent SQLite knowledge graph from source code and exposes 32+ tools for AI-assisted code review, architecture analysis, and security auditing.

**Key difference from the original:** Test nodes and `TESTED_BY` edges are excluded from all architectural analysis (communities, hubs, bridges, cohesion). Tests remain in the graph for coverage reporting but no longer pollute architecture metrics. Additional features: trend tracking and security data-flow audit.

## Architecture at a Glance

```
CLI (code-review-graph-plus)          MCP Server (stdio)
    |                                    |
    v                                    v
+----------+     +------------+     +------------+
|  build   | --> |  GraphStore | <-- |  @mcp.tool |
|  update  |     |  (SQLite)   |     |  handlers  |
|  watch   |     +------------+     +------------+
+----------+            ^                  |
     |                  |                  v
     v                  |           +------------+
Tree-sitter parser       |           |  analysis  |
+----------+             |           |  security  |
|  nodes   |-------------+           |  trends    |
|  edges   |                          +------------+
+----------+
```

- **GraphStore** (`graph.py`) — SQLite-backed storage for nodes (File/Class/Function/Type/Test) and edges (CALLS/IMPORTS_FROM/INHERITS/IMPLEMENTS/CONTAINS/TESTED_BY/DEPENDS_ON/REFERENCES).
- **Parser** (`parser.py`) — Tree-sitter multi-language AST extraction.
- **Flows** (`flows.py`) — Entry-point detection + forward BFS tracing. Criticality scoring includes security sensitivity.
- **Communities** (`communities.py`) — Leiden algorithm (via igraph) on the production-only subgraph.
- **Analysis** (`analysis.py`) — Hub/bridge/knowledge-gap/surprising-connection detection, all using `get_production_nodes/edges()`.
- **Trends** (`trends.py`) — Snapshots table + threshold/trend alerts.
- **Security Audit** (`security_audit.py`) — Keyword-based classification of sources/sinks/transforms + unprotected path tracing.

## Key Files

| File | Responsibility |
|------|---------------|
| `main.py` | FastMCP app, tool registration, prompts |
| `graph.py` | GraphStore class, schema, read/write ops, BFS/impact radius |
| `migrations.py` | Versioned schema migrations, `_migrate_v2` through `_migrate_v10` |
| `parser.py` | NodeInfo/EdgeInfo dataclasses, tree-sitter parsing orchestration |
| `flows.py` | Entry-point detection, flow tracing, criticality scoring |
| `communities.py` | Community detection (Leiden), incremental update |
| `analysis.py` | Hub/bridge/gap/surprise analysis (production-only) |
| `trends.py` | Snapshot recording, trend queries, alert computation |
| `security_audit.py` | Security node classification, path tracing, risk scoring |
| `tools/__init__.py` | Re-exports all tool functions |
| `tools/build.py` | `build_or_update_graph`, `_run_postprocess`, `_compute_summaries` |
| `tools/query.py` | Graph traversal tools (callers, callees, etc.) |
| `tools/analysis_tools.py` | Wrappers for analysis.py functions |
| `tools/trends_tools.py` | `get_debt_trends`, `compare_snapshots` |
| `tools/security_audit_tools.py` | `audit_security_flows`, `get_security_nodes`, `get_unprotected_paths`, `get_security_critical_flows` |
| `cli.py` | CLI entry point (`code-review-graph-plus build`, `register`, etc.) |
| `setup.py` | Package config. **Important:** uses `package_dir={"code_review_graph": "."}` because the directory is `code-review-graph` (hyphen) but Python package name must be `code_review_graph` (underscore). |

## Database Schema (Key Tables)

```sql
nodes          — id, kind, name, qualified_name, file_path, line_start, line_end,
                 language, parent_name, params, return_type, is_test, community_id, signature
edges          — id, kind, source_qualified, target_qualified, file_path, line, confidence
communities    — id, name, level, cohesion, size, dominant_language
flows          — id, name, entry_point_id, depth, node_count, file_count, criticality, path_json
flow_memberships — flow_id, node_id, position
community_summaries — community_id, name, purpose, key_symbols, size, dominant_language
risk_index     — node_id, qualified_name, risk_score, caller_count, test_coverage, security_relevant
snapshots      — id, snapshot_at, commit_hash, files_count, nodes_count, edges_count,
                 communities_count, avg_cohesion, cross_community_edges, warnings_count,
                 large_functions_count, avg_criticality, metrics_json
```

## Development Conventions

### Adding a New MCP Tool

1. **Implement** in `tools/<module>.py`. Signature: `def my_tool_func(arg, repo_root=None) -> dict`.
2. **Use `_get_store(repo_root)`** and always `store.close()` in a `finally` block.
3. **Export** from `tools/__init__.py`.
4. **Register** in `main.py` with `@mcp.tool()` decorator. Use `asyncio.to_thread` for slow/blocking work.

Pattern:
```python
# tools/my_feature_tools.py
from ._common import _get_store

def my_tool(repo_root: str | None = None) -> dict:
    store, _ = _get_store(repo_root)
    try:
        # ... query store ...
        return {"status": "ok", "data": result}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()

# main.py
from .tools import my_tool

@mcp.tool()
def my_tool_tool(repo_root: Optional[str] = None) -> dict:
    """Docstring shown to the LLM client."""
    return my_tool(repo_root=_resolve_repo_root(repo_root))
```

### Modifying the Database Schema

1. Add a migration function `_migrate_vN(conn)` in `migrations.py`.
2. Register it in the `MIGRATIONS` dict.
3. Add any new table to `_KNOWN_TABLES`.
4. Use `IF NOT EXISTS` and `_has_column` checks to keep migrations idempotent.

### Production-Only Analysis Rule

Any architectural analysis (communities, hubs, bridges, cohesion, surprising connections) **must** use:
```python
nodes = store.get_production_nodes()   # excludes Test + is_test
edges = store.get_production_edges()   # excludes TESTED_BY
```

This prevents test code from appearing as architectural hotspots or inflating coupling metrics.

### Edge Direction Convention

`CALLS` edge: `source_qualified` **calls** `target_qualified`.
- Forward BFS from A → finds functions A calls.
- Reverse BFS from A → finds functions that call A.

## Common Tasks

### "I want to add a new architecture metric"

1. Compute it in `tools/build.py` inside `_compute_summaries()` or a new helper.
2. If it needs persistence, add a column/table via migration.
3. Expose via a tool in `tools/analysis_tools.py` or `tools/query.py`.

### "I want to change community detection"

1. Modify `communities.py` — `detect_communities()` uses igraph + Leiden.
2. Ensure it still uses `store.get_production_edges()` and `store.get_production_nodes()`.
3. `store_communities()` writes to the `communities` table and updates `nodes.community_id`.

### "I want to change how criticality is scored"

Edit `flows.py` — `compute_criticality()`. Current weights: file spread (0.30), external calls (0.20), security sensitivity (0.25), test gap (0.15), depth (0.10).

### "I want to change security keyword classification"

Edit `security_audit.py` — the four frozensets at the top:
- `_SOURCE_PATTERNS` / `_SOURCE_NAME_HINTS`
- `_SINK_PATTERNS` / `_SINK_NAME_HINTS`
- `_TRANSFORM_PATTERNS`
- `_CHECK_PATTERNS`

Nodes are classified by `_name_segments()` (splits on `_` and camelCase boundaries) to avoid substring false positives like `login` matching `log`.

### "Build is failing / graph not found"

- Graph DB lives at `<repo_root>/.code-review-graph/graph.db`.
- Run `code-review-graph-plus build` from the repo root, or call `build_or_update_graph_tool` via MCP.
- If `ModuleNotFoundError: No module named 'code_review_graph'`, reinstall: `pip install -e .` (the `setup.py` maps `code_review_graph` package to the current directory).

## Testing a Change Quickly

```python
# Quick smoke test without a full build
from code_review_graph.graph import GraphStore
from code_review_graph.security_audit import audit_security_flows

store = GraphStore("/path/to/repo/.code-review-graph/graph.db")
result = audit_security_flows(store)
print(result["risk_level"], result["risk_score"])
store.close()
```

For unit-style testing with a mock graph, create a temp DB, upsert `NodeInfo`/`EdgeInfo` objects, and run the function directly.
