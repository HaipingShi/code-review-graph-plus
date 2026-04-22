# code-review-graph (Fork)

Personal fork of [code-review-graph](https://code-review-graph.com) v2.3.2 with custom modifications.

## Original

- **Author**: Tirth
- **License**: MIT
- **Source**: `pip install code-review-graph==2.3.2`

## Modifications

See `MODIFICATIONS_*.diff` for per-file diffs:

- `MODIFICATIONS_communities.diff` — Expanded stop-words and generic name filtering in community detection
- `MODIFICATIONS_wiki.diff` — Cross-community referencing in wiki page generation

## Usage

Install in editable mode:

```bash
cd /Users/geesh/AI/skills/code-review-graph
pip install -e .
```

Or point the MCP server config to the local checkout.
