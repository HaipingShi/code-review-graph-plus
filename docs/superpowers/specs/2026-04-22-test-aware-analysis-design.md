# Design: Production-Only Graph Analysis

## Problem

Test nodes and TESTED_BY edges pollute architectural analysis, producing false positives:

- Giant test communities (e.g. writeos-tests 1,385 nodes) mask real architecture
- Cross-community edge count is inflated by TESTED_BY edges
- Cohesion scores are artificially low because test edges span communities
- Hub/Bridge nodes, surprising connections, and large-function hotspots include test code

## Principle

Test nodes and TESTED_BY edges remain in the graph for coverage reporting, but all architecture analysis (communities, hubs, bridges, gaps, surprises) operates on a **production-only subgraph**.

## Changes

### 1. graph.py — Production-only helpers

Add `get_production_nodes()` and `get_production_edges()` to `GraphStore`.

- `get_production_nodes()`: non-File nodes where `kind != "Test"` and `not is_test`
- `get_production_edges()`: all edges where `kind != "TESTED_BY"`

### 2. communities.py — Community detection on production subgraph

- `detect_communities()`: feed production-only nodes and edges into Leiden/file-based detection
- `_generate_community_name()`: heuristic 1 (test-dominated) remains but rarely triggered
- `_compute_cohesion_batch()`: unchanged; benefits from filtered input
- `get_architecture_overview()`: already skips TESTED_BY in cross-edge count; keeps test-community filtering for safety

### 3. analysis.py — All analysis on production subgraph

Add `_production_nodes_and_edges(store)` helper.

| Function | Change |
|----------|--------|
| `find_hub_nodes()` | Use production nodes + edges |
| `find_bridge_nodes()` | Build NetworkX graph from production subgraph |
| `find_knowledge_gaps()` | Exclude Test nodes from isolated/untested checks |
| `find_surprising_connections()` | Exclude Test nodes; drop cross-test-boundary scoring |
| `generate_suggested_questions()` | Benefits from upstream filtering |

### 4. tools/build.py — _compute_summaries

- `risk_index`: SQL query changes from `kind IN ('Function', 'Class', 'Test')` to `kind IN ('Function', 'Class')`
- `community_summaries`: edge_counts exclude TESTED_BY edges

### 5. Unchanged modules

| Module | Reason |
|--------|--------|
| flows.py | `detect_entry_points()` defaults to `include_tests=False` |
| changes.py | TESTED_BY used correctly for coverage gap detection |
| tools/review.py | Test gap reporting is correct behavior |
| search.py | Should find test code too |

## Rollout

After code changes, users must re-run `build_or_update_graph` (or `run_postprocess`) to regenerate communities and flows with the new logic.
