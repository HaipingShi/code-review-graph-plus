"""Technical debt trend tracking.

Records architecture health snapshots over time and computes alerts
based on thresholds and trend detection.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections import defaultdict
from typing import Any

from .communities import get_architecture_overview
from .graph import GraphStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds for immediate alerts
# ---------------------------------------------------------------------------

_THRESHOLDS: dict[str, tuple[float, str]] = {
    "avg_cohesion": (0.2, "low"),
    "warnings_count": (10.0, "high"),
    "cross_community_edges": (100.0, "high"),
}

# Metrics where lower is worse (for trend detection)
_LOWER_IS_WORSE = {"avg_cohesion"}

# ---------------------------------------------------------------------------
# Snapshot recording
# ---------------------------------------------------------------------------


def _get_commit_hash(repo_root: str | None = None) -> str | None:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def record_snapshot(
    store: GraphStore,
    commit_hash: str | None = None,
    repo_root: str | None = None,
) -> int:
    """Record a snapshot of current architecture metrics.

    Args:
        store: The GraphStore instance.
        commit_hash: Optional commit hash. Auto-detected from git if omitted.
        repo_root: Repository root for git detection.

    Returns:
        The id of the inserted snapshot row.
    """
    if commit_hash is None:
        commit_hash = _get_commit_hash(repo_root)

    stats = store.get_stats()
    overview = get_architecture_overview(store)

    communities = overview.get("communities", [])
    communities_count = len(communities)
    cross_community_edges = len(overview.get("cross_community_edges", []))
    warnings_count = len(overview.get("warnings", []))

    avg_cohesion = 0.0
    if communities:
        avg_cohesion = sum(c.get("cohesion", 0.0) for c in communities) / len(communities)

    # Large functions (>300 lines)
    large_func_row = store._conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind IN ('Function', 'Class') "
        "AND line_end IS NOT NULL AND line_start IS NOT NULL "
        "AND (line_end - line_start + 1) > 300"
    ).fetchone()
    large_functions_count = large_func_row[0] if large_func_row else 0

    # Average flow criticality
    crit_row = store._conn.execute(
        "SELECT AVG(criticality) FROM flows"
    ).fetchone()
    avg_criticality = crit_row[0] if crit_row and crit_row[0] is not None else 0.0

    metrics_json = json.dumps({
        "nodes_by_kind": stats.nodes_by_kind,
        "edges_by_kind": stats.edges_by_kind,
        "languages": stats.languages,
    })

    cursor = store._conn.execute(
        """INSERT INTO snapshots
           (commit_hash, files_count, nodes_count, edges_count,
            communities_count, avg_cohesion, cross_community_edges,
            warnings_count, large_functions_count, avg_criticality,
            metrics_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            commit_hash,
            stats.files_count,
            stats.total_nodes,
            stats.total_edges,
            communities_count,
            round(avg_cohesion, 4),
            cross_community_edges,
            warnings_count,
            large_functions_count,
            round(avg_criticality, 4),
            metrics_json,
        ),
    )
    snapshot_id = cursor.lastrowid
    logger.info(
        "Recorded snapshot %d: %d files, %d nodes, %d communities, cohesion=%.3f",
        snapshot_id,
        stats.files_count,
        stats.total_nodes,
        communities_count,
        avg_cohesion,
    )
    return snapshot_id


# ---------------------------------------------------------------------------
# Trend queries
# ---------------------------------------------------------------------------


def get_trend_data(
    store: GraphStore,
    metric: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return time-series data for a given metric.

    Args:
        store: The GraphStore instance.
        metric: Column name from snapshots table.
        limit: Max number of recent snapshots.

    Returns:
        List of dicts with keys: snapshot_at, value.
    """
    valid_metrics = {
        "files_count", "nodes_count", "edges_count",
        "communities_count", "avg_cohesion", "cross_community_edges",
        "warnings_count", "large_functions_count", "avg_criticality",
    }
    if metric not in valid_metrics:
        return []

    rows = store._conn.execute(
        f"SELECT snapshot_at, {metric} FROM snapshots "  # noqa: S608
        "ORDER BY snapshot_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    return [
        {"snapshot_at": r["snapshot_at"], "value": r[metric]}
        for r in reversed(rows)
    ]


# ---------------------------------------------------------------------------
# Alert computation
# ---------------------------------------------------------------------------


def compute_alerts(store: GraphStore) -> list[dict[str, Any]]:
    """Compute threshold and trend alerts from recent snapshots.

    Returns:
        List of alert dicts with keys: type, metric, value, threshold,
        severity, message.
    """
    alerts: list[dict[str, Any]] = []

    # --- Latest snapshot for threshold alerts ---
    latest = store._conn.execute(
        "SELECT * FROM snapshots ORDER BY snapshot_at DESC LIMIT 1"
    ).fetchone()
    if latest is None:
        return alerts

    for metric, (threshold, severity) in _THRESHOLDS.items():
        value = latest[metric]
        if value is None:
            continue
        if metric in _LOWER_IS_WORSE:
            if value < threshold:
                alerts.append({
                    "type": "threshold",
                    "metric": metric,
                    "value": round(value, 4),
                    "threshold": threshold,
                    "severity": severity,
                    "message": (
                        f"{metric} is {value:.3f}, below threshold {threshold}"
                    ),
                })
        else:
            if value > threshold:
                alerts.append({
                    "type": "threshold",
                    "metric": metric,
                    "value": round(value, 4),
                    "threshold": threshold,
                    "severity": severity,
                    "message": (
                        f"{metric} is {value:.0f}, above threshold {threshold}"
                    ),
                })

    # --- Trend alerts (3 consecutive worsening snapshots) ---
    recent = store._conn.execute(
        "SELECT * FROM snapshots ORDER BY snapshot_at DESC LIMIT 4"
    ).fetchall()
    if len(recent) < 4:
        return alerts

    for metric in _THRESHOLDS:
        # Check last 3 deltas (need 4 snapshots)
        values = [r[metric] for r in recent[:4]]
        if None in values:
            continue

        worsening = 0
        for i in range(3):
            if metric in _LOWER_IS_WORSE:
                if values[i] < values[i + 1]:
                    worsening += 1
                else:
                    break
            else:
                if values[i] > values[i + 1]:
                    worsening += 1
                else:
                    break

        if worsening >= 3:
            alerts.append({
                "type": "trend",
                "metric": metric,
                "value": round(values[0], 4),
                "severity": "medium",
                "message": (
                    f"{metric} has worsened for 3 consecutive snapshots"
                ),
            })

    return alerts


# ---------------------------------------------------------------------------
# Snapshot comparison
# ---------------------------------------------------------------------------


def get_snapshot_comparison(
    store: GraphStore,
    snapshot_a_id: int,
    snapshot_b_id: int,
) -> dict[str, Any]:
    """Compare two snapshots and return deltas.

    Returns:
        Dict with metrics from both snapshots and computed deltas.
    """
    rows = store._conn.execute(
        "SELECT * FROM snapshots WHERE id IN (?, ?)",
        (snapshot_a_id, snapshot_b_id),
    ).fetchall()

    if len(rows) != 2:
        return {"error": "One or both snapshot IDs not found"}

    row_map = {r["id"]: r for r in rows}
    a = row_map[snapshot_a_id]
    b = row_map[snapshot_b_id]

    numeric_metrics = [
        "files_count", "nodes_count", "edges_count",
        "communities_count", "avg_cohesion", "cross_community_edges",
        "warnings_count", "large_functions_count", "avg_criticality",
    ]

    deltas = {}
    for m in numeric_metrics:
        av = a[m] if a[m] is not None else 0
        bv = b[m] if b[m] is not None else 0
        deltas[m] = {
            "before": round(av, 4) if isinstance(av, float) else av,
            "after": round(bv, 4) if isinstance(bv, float) else bv,
            "delta": round(bv - av, 4) if isinstance(av, float) else bv - av,
        }

    return {
        "snapshot_a": {
            "id": a["id"],
            "snapshot_at": a["snapshot_at"],
            "commit_hash": a["commit_hash"],
        },
        "snapshot_b": {
            "id": b["id"],
            "snapshot_at": b["snapshot_at"],
            "commit_hash": b["commit_hash"],
        },
        "deltas": deltas,
    }
