"""Wiki generation from community structure.

Generates markdown pages for each detected community and an index page,
providing a navigable documentation wiki for the codebase architecture.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from .communities import get_communities
from .flows import get_flows
from .graph import GraphStore, _sanitize_name

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a community name to a safe filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or "unnamed"


def _build_qn_to_community_map(
    store: GraphStore,
) -> dict[str, tuple[str, str]]:
    """Build a mapping from qualified_name to (community_name, slug).

    Used for cross-referencing in dependency sections of wiki pages.
    """
    qn_to_cid = store.get_all_community_ids()
    if not qn_to_cid:
        return {}

    # Build community_id -> (name, slug) map
    cid_to_name: dict[int, tuple[str, str]] = {}
    try:
        rows = store._conn.execute(
            "SELECT id, name FROM communities"
        ).fetchall()
        for row in rows:
            cid_to_name[row["id"]] = (
                _sanitize_name(row["name"]),
                _slugify(row["name"]),
            )
    except sqlite3.OperationalError:
        return {}

    result: dict[str, tuple[str, str]] = {}
    for qn, cid in qn_to_cid.items():
        if cid is not None and cid in cid_to_name:
            result[qn] = cid_to_name[cid]
    return result


def _generate_community_page(
    store: GraphStore,
    community: dict[str, Any],
    qn_to_community: dict[str, tuple[str, str]] | None = None,
) -> str:
    """Build markdown content for a single community.

    Includes: heading, overview, grouped members (by kind), key symbols,
    file listing, execution flows, and cross-community dependencies.

    Args:
        store: The graph store.
        community: Community dict from get_communities().
        qn_to_community: Mapping from qualified_name to (name, slug) for
            cross-referencing dependencies.

    Returns:
        Markdown string for the community page.
    """
    name = community["name"]
    size = community["size"]
    cohesion = community.get("cohesion", 0.0)
    lang = community.get("dominant_language", "")
    description = community.get("description", "")

    # Use raw QNs for DB queries (community["members"] are sanitized)
    comm_id = community.get("id")
    raw_qns: list[str] = []
    if comm_id is not None:
        try:
            raw_qns = store.get_community_member_qns(comm_id)
        except sqlite3.OperationalError:
            pass
    member_set = set(raw_qns) if raw_qns else set(community.get("members", []))

    lines: list[str] = []
    lines.append(f"# {name}")
    lines.append("")

    # Overview section
    lines.append("## Overview")
    lines.append("")
    if description:
        lines.append(f"{description}")
        lines.append("")
    lines.append(f"- **Size**: {size} nodes")
    lines.append(f"- **Cohesion**: {cohesion:.4f}")
    if lang:
        lines.append(f"- **Dominant Language**: {lang}")
    lines.append("")

    # Members section -- grouped by Kind
    lines.append("## Members")
    lines.append("")
    if raw_qns:
        classes: list[tuple[str, str, str]] = []
        functions: list[tuple[str, str, str]] = []
        tests: list[tuple[str, str, str]] = []
        other: list[tuple[str, str, str]] = []

        for qn in raw_qns:
            node = store.get_node(qn)
            if node and node.kind != "File":
                entry = (
                    _sanitize_name(node.name),
                    node.file_path,
                    f"{node.line_start}-{node.line_end}",
                )
                if node.kind == "Class":
                    classes.append(entry)
                elif node.kind == "Function":
                    functions.append(entry)
                elif node.kind == "Test":
                    tests.append(entry)
                else:
                    other.append(entry)

        def _render_group(title: str, items: list, limit: int = 20) -> None:
            if not items:
                return
            lines.append(f"### {title} ({len(items)})")
            lines.append("")
            lines.append("| Name | File | Lines |")
            lines.append("|------|------|-------|")
            for item_name, item_file, item_lines in items[:limit]:
                lines.append(f"| {item_name} | {item_file} | {item_lines} |")
            if len(items) > limit:
                lines.append("")
                lines.append(f"*... and {len(items) - limit} more.*")
            lines.append("")

        _render_group("Classes", classes, 20)
        _render_group("Functions", functions, 20)
        _render_group("Tests", tests, 20)
        if other:
            _render_group("Other", other, 10)

        if not classes and not functions and not tests and not other:
            lines.append("No non-file members found.")
    else:
        lines.append("No members found.")
    lines.append("")

    # Key Symbols section (most-connected internal nodes)
    lines.append("## Key Symbols")
    lines.append("")
    if raw_qns:
        edge_counts: Counter[str] = Counter()
        for t in store.get_outgoing_targets(list(member_set)):
            if t in member_set:
                edge_counts[t] += 1
        for s in store.get_incoming_sources(list(member_set)):
            if s in member_set:
                edge_counts[s] += 1

        hubs = edge_counts.most_common(10)
        if hubs:
            lines.append("| Symbol | Internal Connections |")
            lines.append("|--------|---------------------|")
            for qn, count in hubs:
                node = store.get_node(qn)
                sym_name = _sanitize_name(node.name) if node else _sanitize_name(qn)
                lines.append(f"| {sym_name} | {count} |")
            lines.append("")
        else:
            lines.append("No highly-connected symbols identified.")
            lines.append("")
    else:
        lines.append("No members to analyze.")
        lines.append("")

    # Files section
    lines.append("## Files")
    lines.append("")
    if raw_qns:
        file_set: set[str] = set()
        for qn in raw_qns:
            node = store.get_node(qn)
            if node:
                file_set.add(node.file_path)

        if file_set:
            sorted_files = sorted(file_set)[:20]
            for f in sorted_files:
                lines.append(f"- `{f}`")
            if len(file_set) > 20:
                lines.append(f"- *... and {len(file_set) - 20} more files.*")
            lines.append("")
        else:
            lines.append("No files identified.")
            lines.append("")
    else:
        lines.append("No members to list files for.")
        lines.append("")

    # Execution flows through community
    lines.append("## Execution Flows")
    lines.append("")
    try:
        all_flows = get_flows(store, sort_by="criticality", limit=200)
        community_flows: list[dict] = []
        for flow in all_flows:
            flow_qns = store.get_flow_qualified_names(flow["id"])
            if flow_qns & member_set:
                community_flows.append(flow)

        if community_flows:
            for flow in community_flows[:10]:
                flow_name = _sanitize_name(flow.get("name", "unnamed"))
                criticality = flow.get("criticality", 0.0)
                depth = flow.get("depth", 0)
                lines.append(
                    f"- **{flow_name}** (criticality: {criticality:.2f}, depth: {depth})"
                )
            if len(community_flows) > 10:
                lines.append(f"- *... and {len(community_flows) - 10} more flows.*")
        else:
            lines.append("No execution flows pass through this community.")
    except sqlite3.OperationalError as exc:
        logger.debug("wiki: flows table unavailable: %s", exc)
        lines.append("Execution flow data not available.")
    lines.append("")

    # Dependencies (cross-community edges) with community name resolution
    lines.append("## Dependencies")
    lines.append("")
    try:
        outgoing_targets: Counter[str] = Counter()
        incoming_sources: Counter[str] = Counter()
        if raw_qns:
            for t in store.get_outgoing_targets(list(member_set)):
                if t not in member_set:
                    outgoing_targets[t] += 1
            for s in store.get_incoming_sources(list(member_set)):
                if s not in member_set:
                    incoming_sources[s] += 1

        def _format_dep(qn: str, count: int) -> str:
            """Format a dependency with community cross-reference if available."""
            dep_name = _sanitize_name(qn.split("::")[-1])
            if qn_to_community and qn in qn_to_community:
                comm_name, comm_slug = qn_to_community[qn]
                return (
                    f"- `{dep_name}` → [{comm_name}]({comm_slug}.md) ({count} edge(s))"
                )
            return f"- `{dep_name}` ({count} edge(s))"

        if outgoing_targets:
            lines.append("### Outgoing")
            lines.append("")
            for target, count in outgoing_targets.most_common(15):
                lines.append(_format_dep(target, count))
            lines.append("")

        if incoming_sources:
            lines.append("### Incoming")
            lines.append("")
            for source, count in incoming_sources.most_common(15):
                lines.append(_format_dep(source, count))
            lines.append("")

        if not outgoing_targets and not incoming_sources:
            lines.append("No cross-community dependencies detected.")
            lines.append("")
    except sqlite3.OperationalError as exc:
        logger.debug("wiki: dependency edges unavailable: %s", exc)
        lines.append("Dependency data not available.")
        lines.append("")

    return "\n".join(lines)


def generate_wiki(
    store: GraphStore,
    wiki_dir: str | Path,
    force: bool = False,
) -> dict[str, Any]:
    """Generate a markdown wiki from the community structure.

    For each community, generates a markdown page. Also generates an
    index.md with links to all community pages.

    Args:
        store: The graph store.
        wiki_dir: Directory to write wiki pages into.
        force: If True, regenerate all pages even if content unchanged.

    Returns:
        Dict with pages_generated, pages_updated, pages_unchanged counts.
    """
    wiki_path = Path(wiki_dir)
    wiki_path.mkdir(parents=True, exist_ok=True)

    communities = get_communities(store)

    # Build community cross-reference map once for all pages
    qn_to_community = _build_qn_to_community_map(store)

    pages_generated = 0
    pages_updated = 0
    pages_unchanged = 0

    page_entries: list[tuple[str, str, int, str]] = []  # (slug, name, size, desc)

    # Track slugs we've already used in THIS run so two communities that
    # slugify to the same filename don't overwrite each other (#222 follow-up).
    # Previously "Data Processing" and "data processing" both became
    # "data-processing.md", causing silent data loss and inflated "updated"
    # counters (each collision was counted as an update while only one file
    # made it to disk).
    used_slugs: set[str] = set()

    for comm in communities:
        name = comm["name"]
        base_slug = _slugify(name)
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used_slugs.add(slug)

        filename = f"{slug}.md"
        filepath = wiki_path / filename

        content = _generate_community_page(store, comm, qn_to_community)

        if filepath.exists() and not force:
            existing = filepath.read_text(encoding="utf-8")
            if existing == content:
                pages_unchanged += 1
                page_entries.append((slug, name, comm["size"], comm.get("description", "")))
                continue

        already_existed = filepath.exists()
        filepath.write_text(content, encoding="utf-8")
        if already_existed:
            pages_updated += 1
        else:
            pages_generated += 1
        page_entries.append((slug, name, comm["size"], comm.get("description", "")))

    # Generate index.md
    index_lines: list[str] = []
    index_lines.append("# Code Wiki")
    index_lines.append("")
    index_lines.append(
        "Auto-generated documentation from the code knowledge graph community structure."
    )
    index_lines.append("")

    # Graph statistics section
    try:
        stats_row = store._conn.execute(
            "SELECT COUNT(*) as cnt FROM nodes WHERE kind != 'File'"
        ).fetchone()
        edge_row = store._conn.execute(
            "SELECT COUNT(*) as cnt FROM edges"
        ).fetchone()
        lang_rows = store._conn.execute(
            "SELECT DISTINCT language FROM nodes "
            "WHERE language IS NOT NULL AND language != ''"
        ).fetchall()

        total_nodes = stats_row["cnt"] if stats_row else 0
        total_edges = edge_row["cnt"] if edge_row else 0
        languages = ", ".join(sorted(r["language"] for r in lang_rows))

        index_lines.append("## Graph Statistics")
        index_lines.append("")
        index_lines.append(f"- **Total Nodes**: {total_nodes}")
        index_lines.append(f"- **Total Edges**: {total_edges}")
        if languages:
            index_lines.append(f"- **Languages**: {languages}")
        index_lines.append(f"- **Communities**: {len(communities)}")
        index_lines.append("")
    except sqlite3.OperationalError:
        index_lines.append(f"**Total communities**: {len(communities)}")
        index_lines.append("")

    index_lines.append("## Communities")
    index_lines.append("")
    index_lines.append("| Community | Size | Description | Link |")
    index_lines.append("|-----------|------|-------------|------|")
    # Sort by size descending (largest first)
    for slug, name, size, desc in sorted(
        page_entries, key=lambda x: x[2], reverse=True
    ):
        short_desc = desc[:60] + "..." if len(desc) > 60 else desc
        index_lines.append(
            f"| {name} | {size} | {short_desc} | [{slug}.md]({slug}.md) |"
        )
    index_lines.append("")

    index_content = "\n".join(index_lines)
    index_path = wiki_path / "index.md"

    if index_path.exists() and not force:
        existing_index = index_path.read_text(encoding="utf-8")
        if existing_index == index_content:
            pages_unchanged += 1
        else:
            index_path.write_text(index_content, encoding="utf-8")
            pages_updated += 1
    else:
        index_path.write_text(index_content, encoding="utf-8")
        pages_generated += 1

    return {
        "pages_generated": pages_generated,
        "pages_updated": pages_updated,
        "pages_unchanged": pages_unchanged,
    }


def get_wiki_page(wiki_dir: str | Path, page_name: str) -> str | None:
    """Retrieve a specific wiki page by community name.

    Args:
        wiki_dir: Directory containing wiki pages.
        page_name: Community name (will be slugified for filename lookup).

    Returns:
        Page content as a string, or None if the page does not exist.
    """
    wiki_path = Path(wiki_dir)
    slug = _slugify(page_name)
    filepath = wiki_path / f"{slug}.md"

    if filepath.is_file():
        return filepath.read_text(encoding="utf-8")

    # Fallback: try exact filename match — with path traversal protection
    exact_path = (wiki_path / page_name).resolve()
    if exact_path.is_file() and exact_path.is_relative_to(wiki_path.resolve()):
        return exact_path.read_text(encoding="utf-8")

    # Fallback: search for partial match
    if wiki_path.is_dir():
        for p in wiki_path.iterdir():
            if p.suffix == ".md" and slug in p.stem:
                return p.read_text(encoding="utf-8")

    return None
