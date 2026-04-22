"""MCP tools for security data-flow audit."""

from __future__ import annotations

from typing import Any

from ..security_audit import (
    audit_security_flows,
    classify_security_nodes,
    find_unprotected_paths,
    get_security_critical_flows,
)
from ._common import _get_store


def audit_security_flows_func(
    max_path_depth: int = 6,
    limit_flows: int = 20,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Run a comprehensive security data-flow audit.

    Identifies sensitive-data sources (e.g. get_password), sinks
    (e.g. log, send_response), and traces paths between them.
    Flags unprotected paths where sensitive data flows to a sink
    without passing through a security transform (encrypt, hash,
    sanitize, etc.).

    Args:
        max_path_depth: Max BFS depth for path tracing. Default: 6.
        limit_flows: Max security-critical flows to return. Default: 20.
        repo_root: Repository root path. Auto-detected if omitted.

    Returns:
        Dict with risk_score, risk_level, summary, classification,
        unprotected_paths, security_critical_flows, and recommendations.
    """
    store, _ = _get_store(repo_root)
    try:
        result = audit_security_flows(
            store,
            max_path_depth=max_path_depth,
            limit_flows=limit_flows,
        )
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()


def get_security_nodes_func(
    repo_root: str | None = None,
) -> dict[str, Any]:
    """List all security-classified nodes in the graph.

    Returns nodes categorized as:
      - sources: functions that produce sensitive data
      - sinks: functions that may leak sensitive data
      - transforms: functions that reduce sensitivity (encrypt, hash, etc.)
      - checks: validation / authentication functions

    Args:
        repo_root: Repository root path. Auto-detected if omitted.
    """
    store, _ = _get_store(repo_root)
    try:
        classification = classify_security_nodes(store)
        total = sum(len(v) for v in classification.values())
        return {
            "status": "ok",
            "summary": (
                f"Found {total} security-classified nodes: "
                f"{len(classification['sources'])} sources, "
                f"{len(classification['sinks'])} sinks, "
                f"{len(classification['transforms'])} transforms, "
                f"{len(classification['checks'])} checks"
            ),
            **classification,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()


def get_unprotected_paths_func(
    max_depth: int = 6,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Find unprotected data paths from sensitive sources to sinks.

    A path is "unprotected" if sensitive data can flow from a source
    (e.g. get_password) to a sink (e.g. log, send_response) without
    passing through a security transform (encrypt, hash, sanitize).

    Args:
        max_depth: Max BFS depth for path tracing. Default: 6.
        repo_root: Repository root path. Auto-detected if omitted.

    Returns:
        Dict with unprotected path list, grouped by risk level.
    """
    store, _ = _get_store(repo_root)
    try:
        paths = find_unprotected_paths(store, max_depth=max_depth)
        critical = [p for p in paths if p["risk_level"] == "critical"]
        high = [p for p in paths if p["risk_level"] == "high"]
        medium = [p for p in paths if p["risk_level"] == "medium"]
        return {
            "status": "ok",
            "summary": (
                f"Found {len(paths)} unprotected path(s): "
                f"{len(critical)} critical, {len(high)} high, {len(medium)} medium"
            ),
            "total": len(paths),
            "critical": critical,
            "high": high,
            "medium": medium,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()


def get_security_critical_flows_func(
    limit: int = 20,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """List execution flows that contain security-sensitive nodes.

    Returns flows (from the flows table) that pass through any node
    classified as a security source, sink, transform, or check.
    Sorted by number of sensitive nodes and criticality.

    Args:
        limit: Maximum flows to return. Default: 20.
        repo_root: Repository root path. Auto-detected if omitted.
    """
    store, _ = _get_store(repo_root)
    try:
        flows = get_security_critical_flows(store, limit=limit)
        return {
            "status": "ok",
            "summary": f"Found {len(flows)} security-critical execution flow(s)",
            "flows": flows,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()
