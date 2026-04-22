"""MCP tools for technical debt trend tracking."""

from __future__ import annotations

from typing import Any

from ..trends import compute_alerts, get_snapshot_comparison, get_trend_data
from ._common import _get_store


def get_debt_trends(
    metric: str = "all",
    limit: int = 20,
    include_alerts: bool = True,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Retrieve architecture health trends over time.

    Returns time-series data for tracked metrics and optional alerts.

    Args:
        metric: Metric to query. "all" returns all metrics.
                Options: files_count, nodes_count, edges_count,
                communities_count, avg_cohesion, cross_community_edges,
                warnings_count, large_functions_count, avg_criticality.
        limit: Number of recent snapshots to include (default: 20).
        include_alerts: Whether to compute and return alerts (default: True).
        repo_root: Repository root path. Auto-detected if omitted.

    Returns:
        Dict with trends dict and optional alerts list.
    """
    store, _ = _get_store(repo_root)
    try:
        all_metrics = [
            "files_count", "nodes_count", "edges_count",
            "communities_count", "avg_cohesion", "cross_community_edges",
            "warnings_count", "large_functions_count", "avg_criticality",
        ]

        metrics_to_query = all_metrics if metric == "all" else [metric]

        trends: dict[str, list[dict[str, Any]]] = {}
        for m in metrics_to_query:
            if m in all_metrics:
                trends[m] = get_trend_data(store, m, limit=limit)

        result: dict[str, Any] = {
            "status": "ok",
            "summary": f"Retrieved trends for {len(trends)} metric(s) over {limit} snapshot(s)",
            "trends": trends,
        }

        if include_alerts:
            alerts = compute_alerts(store)
            result["alerts"] = alerts
            result["alert_count"] = len(alerts)
            if alerts:
                result["summary"] += f", {len(alerts)} alert(s)"

        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()


def compare_snapshots(
    snapshot_a_id: int,
    snapshot_b_id: int | None = None,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Compare two architecture snapshots.

    If *snapshot_b_id* is omitted, compares *snapshot_a_id* against
    the most recent snapshot.

    Args:
        snapshot_a_id: ID of the first (earlier) snapshot.
        snapshot_b_id: ID of the second (later) snapshot. Defaults to latest.
        repo_root: Repository root path. Auto-detected if omitted.

    Returns:
        Dict with before/after metadata and per-metric deltas.
    """
    store, _ = _get_store(repo_root)
    try:
        if snapshot_b_id is None:
            row = store._conn.execute(
                "SELECT id FROM snapshots ORDER BY snapshot_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return {
                    "status": "error",
                    "error": "No snapshots found",
                }
            snapshot_b_id = row["id"]

        comparison = get_snapshot_comparison(
            store, snapshot_a_id, snapshot_b_id,
        )

        if "error" in comparison:
            return {"status": "error", "error": comparison["error"]}

        return {
            "status": "ok",
            "summary": (
                f"Comparing snapshot {snapshot_a_id} to {snapshot_b_id}"
            ),
            **comparison,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        store.close()
