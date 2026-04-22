"""Security data-flow audit for the code knowledge graph.

Identifies sensitive-data sources/sinks, traces potential unprotected
paths, and surfaces security-relevant execution flows.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Optional

from .graph import GraphNode, GraphStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword-based node classification
# ---------------------------------------------------------------------------

# Nodes that PRODUCE sensitive data (passwords, tokens, secrets, etc.)
_SOURCE_PATTERNS: frozenset[str] = frozenset({
    "password", "token", "secret", "credential", "api_key", "apikey",
    "private_key", "privkey", "secret_key", "access_key", "auth_code",
    "refresh_token", "bearer", "jwt", "cookie", "session_id",
    "pin", "ssn", "credit_card", "creditcard", "iban", "pii",
})

# Name prefixes/suffixes that indicate data production
_SOURCE_NAME_HINTS: frozenset[str] = frozenset({
    "get_", "fetch_", "retrieve_", "read_", "parse_", "decode_",
    "decrypt_", "decrypt", "deserialize_", "load_", "extract_",
    "generate_", "create_", "issue_", "renew_", "refresh_",
})

# Nodes that CONSUME / may LEAK sensitive data
_SINK_PATTERNS: frozenset[str] = frozenset({
    "log", "logger", "logging", "print", "printf", "console",
    "debug", "trace", "syslog", "sentry", "rollbar",
    "send", "respond", "response", "jsonify", "render",
    "write", "save", "store", "persist", "upload",
    "execute", "query", "raw_query", "exec_", "callproc",
    "subprocess", "popen", "system", "eval", "exec",
    "http", "request",
    "email", "mail", "notify", "message", "sms",
    "cache", "redis", "memcached", "kafka", "queue",
})

# Name prefixes/suffixes that indicate sink behavior
_SINK_NAME_HINTS: frozenset[str] = frozenset({
    "log_", "debug_", "print_", "write_", "save_", "send_",
    "respond_", "render_", "output_", "export_", "upload_",
    "execute_", "query_", "fetch_", "request_", "call_",
})

# Security TRANSFORMS — mitigate risk when present on a path
_TRANSFORM_PATTERNS: frozenset[str] = frozenset({
    "encrypt", "encrypt_", "aes", "rsa", "gcm", "cbc",
    "hash", "sha", "sha256", "sha512", "md5", "bcrypt",
    "scrypt", "argon", "pbkdf2", "hmac", "digest",
    "sanitize", "escape", "quote", "htmlspecialchars",
    "strip_tags", "clean", "scrub", "parametrize",
    "mask", "redact", "truncate", "obfuscate", "anonymize",
    "bind", "prepare", "parameterize", "validate",
})

# Security CHECKS / gates
_CHECK_PATTERNS: frozenset[str] = frozenset({
    "authenticate", "auth", "authorize", "permission", "acl",
    "validate", "verify", "check", "assert", "require",
    "is_authenticated", "is_authorized", "has_permission",
    "csrf", "cors", "rate_limit", "throttle", "whitelist",
    "blacklist", "denylist", "allowlist", "waf",
})


def _name_segments(name: str) -> list[str]:
    """Split a snake_case or camelCase name into word segments."""
    # Split on underscore first
    parts = [p for p in name.lower().split("_") if p]
    # Also handle camelCase by splitting when lowercase meets uppercase
    import re
    result: list[str] = []
    for part in parts:
        # Insert space before capitals, then split
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", part)
        result.extend([s.lower() for s in split.split() if s])
    return result


def _classify_node(node: GraphNode) -> list[str]:
    """Classify a node into security roles based on its name.

    Returns a list of zero or more labels:
      - "source": produces sensitive data
      - "sink": may leak sensitive data
      - "transform": transforms/reduces sensitivity
      - "check": validates/authenticates
    """
    labels: list[str] = []
    name_lower = node.name.lower()
    qn_lower = node.qualified_name.lower()
    segments = _name_segments(node.name)
    qn_segments = _name_segments(node.qualified_name.rsplit("::", 1)[-1])

    # Source detection:
    # 1. Prefix is a source hint AND name contains a sensitive word
    # 2. OR name is exactly a sensitive word
    is_source = False
    has_sensitive_word = any(
        pat in segments or pat in qn_segments for pat in _SOURCE_PATTERNS
    )
    if has_sensitive_word:
        # Must also have a source-producing prefix, OR be exactly the sensitive word
        if any(name_lower.startswith(hint) for hint in _SOURCE_NAME_HINTS):
            is_source = True
        elif any(name_lower == pat for pat in _SOURCE_PATTERNS):
            is_source = True
    if is_source:
        labels.append("source")

    # Sink detection:
    # Match sink patterns as whole segments (avoids "login" matching "log")
    is_sink = False
    for pat in _SINK_PATTERNS:
        if pat in segments or pat in qn_segments:
            is_sink = True
            break
    if not is_sink:
        for hint in _SINK_NAME_HINTS:
            if name_lower.startswith(hint):
                is_sink = True
                break
    if is_sink:
        labels.append("sink")

    # Transform detection:
    # Match as whole segments OR prefix hints
    is_transform = False
    for pat in _TRANSFORM_PATTERNS:
        if pat in segments or pat in qn_segments:
            is_transform = True
            break
    if not is_transform:
        for hint in ("hash_", "encrypt_", "decrypt_", "sanitize_", "escape_",
                     "mask_", "redact_", "obfuscate_", "anonymize_"):
            if name_lower.startswith(hint):
                is_transform = True
                break
    if is_transform:
        labels.append("transform")

    # Check detection:
    is_check = False
    for pat in _CHECK_PATTERNS:
        if pat in segments or pat in qn_segments:
            is_check = True
            break
    if is_check:
        labels.append("check")

    return labels


def classify_security_nodes(
    store: GraphStore,
) -> dict[str, list[dict]]:
    """Classify all Function/Class nodes by security role.

    Returns dict with keys: sources, sinks, transforms, checks.
    Each value is a list of node dicts.
    """
    nodes = store.get_production_nodes()
    result: dict[str, list[dict]] = {
        "sources": [],
        "sinks": [],
        "transforms": [],
        "checks": [],
    }
    for n in nodes:
        if n.kind not in ("Function", "Class"):
            continue
        labels = _classify_node(n)
        node_dict = {
            "name": n.name,
            "qualified_name": n.qualified_name,
            "kind": n.kind,
            "file": n.file_path,
        }
        if "source" in labels:
            result["sources"].append(node_dict)
        if "sink" in labels:
            result["sinks"].append(node_dict)
        if "transform" in labels:
            result["transforms"].append(node_dict)
        if "check" in labels:
            result["checks"].append(node_dict)
    return result


# ---------------------------------------------------------------------------
# Path tracing
# ---------------------------------------------------------------------------


def _reverse_bfs(
    store: GraphStore,
    start_qnames: set[str],
    max_depth: int = 6,
) -> dict[str, tuple[int, list[str]]]:
    """Reverse BFS from *start_qnames* following CALLS edges backward.

    Returns dict: qname -> (depth, path_from_start)
    where path is a list of qnames from start to this node (inclusive).
    """
    visited: dict[str, tuple[int, list[str]]] = {}
    queue: deque[tuple[str, int, list[str]]] = deque()

    for qn in start_qnames:
        visited[qn] = (0, [qn])
        queue.append((qn, 0, [qn]))

    while queue:
        current, depth, path = queue.popleft()
        if depth >= max_depth:
            continue

        # Find all nodes that CALL current (reverse of CALLS edge)
        edges = store.get_edges_by_target(current)
        for e in edges:
            if e.kind != "CALLS":
                continue
            caller = e.source_qualified
            if caller in visited:
                continue
            new_path = path + [caller]
            visited[caller] = (depth + 1, new_path)
            queue.append((caller, depth + 1, new_path))

    return visited


def _forward_bfs(
    store: GraphStore,
    start_qnames: set[str],
    max_depth: int = 6,
) -> dict[str, tuple[int, list[str]]]:
    """Forward BFS from *start_qnames* following CALLS edges.

    Returns dict: qname -> (depth, path_from_start)
    """
    visited: dict[str, tuple[int, list[str]]] = {}
    queue: deque[tuple[str, int, list[str]]] = deque()

    for qn in start_qnames:
        visited[qn] = (0, [qn])
        queue.append((qn, 0, [qn]))

    while queue:
        current, depth, path = queue.popleft()
        if depth >= max_depth:
            continue

        edges = store.get_edges_by_source(current)
        for e in edges:
            if e.kind != "CALLS":
                continue
            callee = e.target_qualified
            if callee in visited:
                continue
            new_path = path + [callee]
            visited[callee] = (depth + 1, new_path)
            queue.append((callee, depth + 1, new_path))

    return visited


def find_unprotected_paths(
    store: GraphStore,
    max_depth: int = 6,
) -> list[dict]:
    """Find paths from sensitive sources to sinks without security transforms.

    Algorithm:
      1. Classify all nodes.
      2. From each source, reverse-BFS to find all callers (data consumers).
      3. For each caller in the reverse-BFS tree, check if it forward-calls
         any sink.
      4. If yes, reconstruct the path: source ← ... ← caller → sink.
      5. Check if any transform node lies on the path. If not → unprotected.

    Returns a list of path dicts with:
      - source, sink, path_nodes, has_transform, risk_level
    """
    classification = classify_security_nodes(store)
    sources = {s["qualified_name"] for s in classification["sources"]}
    sinks = {s["qualified_name"] for s in classification["sinks"]}
    transforms = {t["qualified_name"] for t in classification["transforms"]}

    if not sources or not sinks:
        return []

    # Pre-compute: for every node, does it forward-call a sink?
    node_to_sinks: dict[str, list[str]] = defaultdict(list)
    nodes = store.get_production_nodes()
    for n in nodes:
        edges = store.get_edges_by_source(n.qualified_name)
        for e in edges:
            if e.kind == "CALLS" and e.target_qualified in sinks:
                node_to_sinks[n.qualified_name].append(e.target_qualified)

    results: list[dict] = []
    seen_paths: set[tuple[str, str]] = set()

    for src in sources:
        # Reverse BFS from source: who receives data from this source?
        rev = _reverse_bfs(store, {src}, max_depth=max_depth)

        for node_qn, (_depth, rev_path) in rev.items():
            # Skip if this node doesn't call any sink
            called_sinks = node_to_sinks.get(node_qn, [])
            if not called_sinks:
                continue

            for sink in called_sinks:
                path_key = (src, sink)
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)

                # Full path: source -> ... -> node -> sink
                # rev_path is [src, ..., node] (source to node via reverse edges)
                full_path = rev_path + [sink]

                # Check for transforms on the path
                path_qnames = set(full_path)
                has_transform = bool(path_qnames & transforms)

                # Risk scoring
                risk_level = "high"
                if has_transform:
                    risk_level = "medium"

                # Check if sink is a logging function (especially bad)
                sink_node = store.get_node(sink)
                is_log_sink = False
                if sink_node:
                    sn_lower = sink_node.name.lower()
                    is_log_sink = any(
                        kw in sn_lower for kw in ("log", "print", "debug", "trace")
                    )

                if is_log_sink and not has_transform:
                    risk_level = "critical"

                results.append({
                    "source": src,
                    "sink": sink,
                    "path_nodes": full_path,
                    "path_length": len(full_path),
                    "has_transform": has_transform,
                    "is_log_sink": is_log_sink,
                    "risk_level": risk_level,
                })

    # Sort by risk: critical first, then high, then medium
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    results.sort(key=lambda x: risk_order.get(x["risk_level"], 4))
    return results


def get_security_critical_flows(
    store: GraphStore,
    limit: int = 20,
) -> list[dict]:
    """Return stored execution flows that contain security-sensitive nodes.

    A flow is security-critical if any node on its path is classified as
    source, sink, transform, or check.
    """
    classification = classify_security_nodes(store)
    sensitive_qnames: set[str] = set()
    for cat in classification.values():
        for node in cat:
            sensitive_qnames.add(node["qualified_name"])

    if not sensitive_qnames:
        return []

    conn = store._conn
    rows = conn.execute(
        "SELECT id, name, entry_point_id, criticality, node_count, "
        "file_count, path_json FROM flows ORDER BY criticality DESC"
    ).fetchall()

    results: list[dict] = []
    for r in rows:
        path_ids = []
        try:
            import json as _json
            path_ids = _json.loads(r["path_json"]) if r["path_json"] else []
        except Exception:
            continue

        # Check if any node in this flow is security-sensitive
        sensitive_nodes_in_flow: list[dict] = []
        for nid in path_ids:
            node = store.get_node_by_id(nid)
            if node and node.qualified_name in sensitive_qnames:
                labels = _classify_node(node)
                sensitive_nodes_in_flow.append({
                    "name": node.name,
                    "qualified_name": node.qualified_name,
                    "kind": node.kind,
                    "labels": labels,
                })

        if sensitive_nodes_in_flow:
            results.append({
                "flow_id": r["id"],
                "name": r["name"],
                "criticality": r["criticality"],
                "node_count": r["node_count"],
                "file_count": r["file_count"],
                "sensitive_nodes": sensitive_nodes_in_flow,
                "sensitive_count": len(sensitive_nodes_in_flow),
            })

    # Sort by number of sensitive nodes descending, then criticality
    results.sort(key=lambda x: (-x["sensitive_count"], -x["criticality"]))
    return results[:limit]


def audit_security_flows(
    store: GraphStore,
    max_path_depth: int = 6,
    limit_flows: int = 20,
) -> dict:
    """Run a full security data-flow audit on the graph.

    Returns a comprehensive report with:
      - classified nodes (sources, sinks, transforms, checks)
      - unprotected paths from source to sink
      - security-critical execution flows
      - summary statistics and risk score
    """
    classification = classify_security_nodes(store)
    unprotected = find_unprotected_paths(store, max_depth=max_path_depth)
    critical_flows = get_security_critical_flows(store, limit=limit_flows)

    # Summary stats
    total_sources = len(classification["sources"])
    total_sinks = len(classification["sinks"])
    total_transforms = len(classification["transforms"])
    total_checks = len(classification["checks"])

    critical_paths = [p for p in unprotected if p["risk_level"] == "critical"]
    high_paths = [p for p in unprotected if p["risk_level"] == "high"]

    # Overall risk score (0.0 - 1.0)
    # Based on: unprotected paths / (sources * sinks) ratio, weighted by criticality
    risk_score = 0.0
    if total_sources > 0 and total_sinks > 0:
        max_possible_paths = total_sources * total_sinks
        actual_unprotected = len([p for p in unprotected if not p["has_transform"]])
        path_ratio = min(actual_unprotected / max(max_possible_paths * 0.1, 1), 1.0)
        critical_weight = len(critical_paths) * 0.15
        risk_score = min(path_ratio + critical_weight, 1.0)
        risk_score = round(risk_score, 4)

    # Recommendations
    recommendations: list[str] = []
    if critical_paths:
        recommendations.append(
            f"Found {len(critical_paths)} critical unprotected path(s) where "
            "sensitive data may be logged or exposed without transformation. "
            "Review immediately."
        )
    if high_paths:
        recommendations.append(
            f"Found {len(high_paths)} high-risk unprotected path(s) from "
            "sensitive sources to sinks. Consider adding encryption, hashing, "
            "or sanitization."
        )
    if total_sources > 0 and total_transforms == 0:
        recommendations.append(
            "Sensitive data sources detected but no security transforms found. "
            "Consider adding encryption/hashing functions."
        )
    if total_sources > 0 and total_checks == 0:
        recommendations.append(
            "Sensitive data sources detected but no validation/check functions found. "
            "Consider adding input validation and authentication checks."
        )
    if not critical_paths and not high_paths:
        recommendations.append(
            "No high-risk unprotected paths detected. Security posture looks good."
        )

    return {
        "status": "ok",
        "risk_score": risk_score,
        "risk_level": (
            "critical" if risk_score >= 0.7 else
            "high" if risk_score >= 0.4 else
            "medium" if risk_score >= 0.2 else
            "low"
        ),
        "summary": {
            "sources_count": total_sources,
            "sinks_count": total_sinks,
            "transforms_count": total_transforms,
            "checks_count": total_checks,
            "unprotected_paths_count": len(unprotected),
            "critical_paths_count": len(critical_paths),
            "high_paths_count": len(high_paths),
            "security_critical_flows_count": len(critical_flows),
        },
        "classification": classification,
        "unprotected_paths": unprotected[:50],  # Cap output size
        "security_critical_flows": critical_flows,
        "recommendations": recommendations,
    }
