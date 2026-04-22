# Production-Only Graph Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude Test nodes and TESTED_BY edges from architectural analysis (communities, hubs, bridges, gaps, surprises) while keeping them in the graph for coverage reporting.

**Architecture:** Add `GraphStore.get_production_nodes()` and `get_production_edges()` helpers, then switch community detection and analysis modules to use the production-only subgraph.

**Tech Stack:** Python 3.11+, SQLite, NetworkX, igraph (optional)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `graph.py` | Add `get_production_nodes()` and `get_production_edges()` to `GraphStore` |
| `communities.py` | `detect_communities()` uses production-only nodes/edges |
| `analysis.py` | All analysis functions use production-only subgraph |
| `tools/build.py` | `_compute_summaries()` risk_index excludes Test nodes |

---

## Task 1: Add production-only helpers to GraphStore

**Files:**
- Modify: `graph.py` (in `GraphStore` class, near `get_all_nodes`/`get_all_edges`)

- [ ] **Step 1: Add `get_production_nodes()`**

Insert after `get_all_nodes()` in `GraphStore`:

```python
    def get_production_nodes(self) -> list[GraphNode]:
        """Return non-File, non-Test nodes for architectural analysis."""
        return [
            n for n in self.get_all_nodes(exclude_files=True)
            if n.kind != "Test" and not n.is_test
        ]
```

- [ ] **Step 2: Add `get_production_edges()`**

Insert after `get_all_edges()` in `GraphStore`:

```python
    def get_production_edges(self) -> list[GraphEdge]:
        """Return all edges excluding TESTED_BY for architectural analysis."""
        return [e for e in self.get_all_edges() if e.kind != "TESTED_BY"]
```

- [ ] **Step 3: Commit**

```bash
git add graph.py
git commit -m "feat(graph): add get_production_nodes and get_production_edges helpers"
```

---

## Task 2: Community detection on production subgraph

**Files:**
- Modify: `communities.py` (in `detect_communities()`)

- [ ] **Step 1: Update `detect_communities()` to use production subgraph**

Replace the current node/edge gathering:

```python
    # Old:
    all_edges = store.get_all_edges()
    unique_nodes = store.get_all_nodes(exclude_files=True)
```

With:

```python
    all_edges = store.get_production_edges()
    unique_nodes = store.get_production_nodes()
```

- [ ] **Step 2: Commit**

```bash
git add communities.py
git commit -m "feat(communities): detect communities on production-only subgraph"
```

---

## Task 3: Analysis on production subgraph

**Files:**
- Modify: `analysis.py`

- [ ] **Step 1: Add `_production_nodes_and_edges()` helper**

Insert at the top of `analysis.py` after imports:

```python
def _production_nodes_and_edges(store: GraphStore) -> tuple[list, list]:
    """Return production-only nodes and edges for analysis."""
    return store.get_production_nodes(), store.get_production_edges()
```

- [ ] **Step 2: Update `find_hub_nodes()`**

Replace:
```python
    edges = store.get_all_edges()
    nodes = store.get_all_nodes(exclude_files=True)
```

With:
```python
    nodes, edges = _production_nodes_and_edges(store)
```

- [ ] **Step 3: Update `find_bridge_nodes()`**

Replace the `nxg = store._build_networkx_graph()` call. The NetworkX graph must be built from production edges only.

Add a helper or modify the call. Since `_build_networkx_graph()` uses `get_all_edges()`, we need a production-only variant or inline build.

Replace the bridge function body with:

```python
    import networkx as nx

    nodes, edges = _production_nodes_and_edges(store)
    nxg = nx.Graph()
    for n in nodes:
        nxg.add_node(n.qualified_name)
    for e in edges:
        nxg.add_edge(e.source_qualified, e.target_qualified)
```

- [ ] **Step 4: Update `find_knowledge_gaps()`**

Replace:
```python
    edges = store.get_all_edges()
    nodes = store.get_all_nodes(exclude_files=True)
```

With:
```python
    nodes, edges = _production_nodes_and_edges(store)
```

- [ ] **Step 5: Update `find_surprising_connections()`**

Replace:
```python
    edges = store.get_all_edges()
    nodes = store.get_all_nodes(exclude_files=True)
```

With:
```python
    nodes, edges = _production_nodes_and_edges(store)
```

Also remove the cross-test-boundary scoring block:

```python
        # Cross-file-type: test <-> non-test (+0.15)
        if src.is_test != tgt.is_test and e.kind == "CALLS":
            score += 0.15
            reasons.append("cross-test-boundary")
```

Since src and tgt are already production nodes, `is_test` is always False, so this block is dead code.

- [ ] **Step 6: Commit**

```bash
git add analysis.py
git commit -m "feat(analysis): run all analysis on production-only subgraph"
```

---

## Task 4: Risk index excludes Test nodes

**Files:**
- Modify: `tools/build.py` (in `_compute_summaries()`)

- [ ] **Step 1: Update risk_index query**

Find this SQL in the `risk_index` block:

```python
        risk_nodes = conn.execute(
            "SELECT id, qualified_name, name FROM nodes "
            "WHERE kind IN ('Function', 'Class', 'Test')"
        ).fetchall()
```

Change to:

```python
        risk_nodes = conn.execute(
            "SELECT id, qualified_name, name FROM nodes "
            "WHERE kind IN ('Function', 'Class')"
        ).fetchall()
```

- [ ] **Step 2: Update community_summaries edge_counts**

The `edge_counts` in `community_summaries` should exclude TESTED_BY edges. Find:

```python
        edge_counts: dict[str, int] = defaultdict(int)
        for row in conn.execute(
            "SELECT source_qualified, COUNT(*) FROM edges "
            "GROUP BY source_qualified"
        ):
            edge_counts[row[0]] += row[1]
        for row in conn.execute(
            "SELECT target_qualified, COUNT(*) FROM edges "
            "GROUP BY target_qualified"
        ):
            edge_counts[row[0]] += row[1]
```

Change to exclude TESTED_BY:

```python
        edge_counts: dict[str, int] = defaultdict(int)
        for row in conn.execute(
            "SELECT source_qualified, COUNT(*) FROM edges "
            "WHERE kind != 'TESTED_BY' GROUP BY source_qualified"
        ):
            edge_counts[row[0]] += row[1]
        for row in conn.execute(
            "SELECT target_qualified, COUNT(*) FROM edges "
            "WHERE kind != 'TESTED_BY' GROUP BY target_qualified"
        ):
            edge_counts[row[0]] += row[1]
```

- [ ] **Step 3: Commit**

```bash
git add tools/build.py
git commit -m "feat(build): exclude tests from risk_index and community_summaries"
```

---

## Task 5: Verification

- [ ] **Step 1: Run basic import check**

```bash
cd /Users/geesh/AI/skills/code-review-graph
python -c "from code_review_graph.graph import GraphStore; from code_review_graph.communities import detect_communities; from code_review_graph.analysis import find_hub_nodes, find_knowledge_gaps"
```

Expected: No import errors.

- [ ] **Step 2: Test on a repo (WriterOS)**

Build or re-postprocess the graph:

```bash
cd /path/to/writeros
python -m code_review_graph.cli run_postprocess
```

Then check:
- Community count should be lower (no giant test communities)
- Cross-community edges should be fewer
- Cohesion scores should be higher

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-04-22-production-only-analysis.md
git commit -m "docs: add implementation plan for production-only analysis"
```

---

## Spec Coverage Check

| Spec Section | Task |
|-------------|------|
| graph.py helpers | Task 1 |
| communities.py filtering | Task 2 |
| analysis.py all functions | Task 3 |
| tools/build.py risk_index | Task 4 |
| tools/build.py community_summaries | Task 4 |
| Verification | Task 5 |

All covered.
