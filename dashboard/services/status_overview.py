from dashboard.services.k8s import collect_k8s_metrics_summary
from dashboard.services.synology import collect_synology_summary
from dashboard.services.network import collect_network_summary
from dashboard.services.backup_status import collect_backup_status_summary
from dashboard.services.aws_billing import collect_aws_billing_summary
from claude_usage.services import collect_claude_dashboard_summary
from monitoring.services import collect_host_status

_HIGH_USAGE = 85
_AWS_BUDGET = 2.0
_CLAUDE_WEEKLY_LIMIT = 90


def _check_k8s(issues):
    try:
        pods, nodes, total, cpu, mem = collect_k8s_metrics_summary()
    except Exception as e:
        return {"name": "Kubernetes", "status": "warn", "detail": "Unavailable"}

    status = "ok"
    detail = f"{pods.get('running', 0)}/{total} pods running"

    failed = pods.get("failed", 0)
    pending = pods.get("pending", 0)
    if failed:
        status = "critical"
        issues.append({"severity": "critical", "source": "Kubernetes", "message": f"{failed} pod{'s' if failed != 1 else ''} failed"})
    if pending:
        status = "critical" if status == "critical" else "warn"
        issues.append({"severity": "warn", "source": "Kubernetes", "message": f"{pending} pod{'s' if pending != 1 else ''} pending"})

    for n in nodes or []:
        if not n.get("ready", True):
            status = "critical"
            issues.append({"severity": "critical", "source": "Kubernetes", "message": f"Node {n.get('name')} not ready"})

    if cpu and cpu >= _HIGH_USAGE:
        status = "critical" if status == "critical" else "warn"
        issues.append({"severity": "warn", "source": "Kubernetes", "message": f"Cluster CPU {cpu}%"})
    if mem and mem >= _HIGH_USAGE:
        status = "critical" if status == "critical" else "warn"
        issues.append({"severity": "warn", "source": "Kubernetes", "message": f"Cluster memory {mem}%"})

    return {"name": "Kubernetes", "status": status, "detail": detail}


def _check_synology(issues):
    try:
        m = collect_synology_summary()
    except Exception:
        return {"name": "Synology NAS", "status": "warn", "detail": "Unavailable"}

    if not m or m.get("error"):
        return {"name": "Synology NAS", "status": "warn", "detail": "Unavailable"}

    status = "ok"
    detail = f"Disk {m.get('overall_percent_used', '?')}% used"

    for v in m.get("volumes", []):
        if v.get("status") and v["status"] != "normal":
            status = "critical"
            issues.append({"severity": "critical", "source": "Synology NAS", "message": f"Volume {v.get('name')}: {v['status']}"})
    for d in m.get("disks", []):
        if d.get("smart_status") and d["smart_status"] != "normal":
            status = "critical"
            issues.append({"severity": "critical", "source": "Synology NAS", "message": f"Disk {d.get('name')}: {d['smart_status']}"})

    for key, label in (("cpu_percent", "CPU"), ("memory_percent", "Memory"), ("overall_percent_used", "Disk")):
        val = m.get(key)
        if isinstance(val, (int, float)) and val >= _HIGH_USAGE:
            status = "critical" if status == "critical" else "warn"
            issues.append({"severity": "warn", "source": "Synology NAS", "message": f"{label} {val}%"})

    return {"name": "Synology NAS", "status": status, "detail": detail}


def _check_network(issues):
    try:
        m = collect_network_summary()
    except Exception:
        return {"name": "Network", "status": "warn", "detail": "Unavailable"}

    if not m:
        return {"name": "Network", "status": "warn", "detail": "Unavailable"}

    if not m.get("online", False):
        issues.append({"severity": "critical", "source": "Network", "message": "Internet offline"})
        return {"name": "Network", "status": "critical", "detail": "Offline"}

    return {"name": "Network", "status": "ok", "detail": "Online"}


def _check_hosts(issues):
    try:
        hosts = collect_host_status()
    except Exception:
        return {"name": "Monitored Hosts", "status": "warn", "detail": "Unavailable"}

    total = len(hosts)
    down = [h for h in hosts if h.get("is_up") is False]
    stale = [h for h in hosts if h.get("is_up") is not False and h.get("stale")]

    status = "ok"
    for h in down:
        status = "critical"
        issues.append({"severity": "critical", "source": "Hosts", "message": f"{h.get('name')} is down"})
    if stale and status != "critical":
        status = "warn"
    for h in stale:
        issues.append({"severity": "warn", "source": "Hosts", "message": f"{h.get('name')} stale (no recent ping)"})

    up = total - len(down) - len(stale)
    return {"name": "Monitored Hosts", "status": status, "detail": f"{up}/{total} up"}


def _check_backup(issues):
    try:
        b = collect_backup_status_summary()
    except Exception:
        return {"name": "Backups", "status": "warn", "detail": "Unavailable"}

    if b.get("error"):
        return {"name": "Backups", "status": "warn", "detail": "Unavailable"}

    status = "ok"
    apps = ([b["primary"]] if b.get("primary") else []) + b.get("others", [])
    for a in apps:
        if a.get("status") == "stale":
            status = "critical"
            issues.append({"severity": "critical", "source": "Backups", "message": f"{a.get('app')} overdue ({a.get('age_label')})"})
        elif a.get("status") == "warn":
            status = "critical" if status == "critical" else "warn"
            issues.append({"severity": "warn", "source": "Backups", "message": f"{a.get('app')} aging ({a.get('age_label')})"})

    return {"name": "Backups", "status": status, "detail": f"{len(apps)} app{'s' if len(apps) != 1 else ''} backed up"}


def _check_aws(issues):
    try:
        b = collect_aws_billing_summary()
    except Exception:
        return {"name": "AWS Spending", "status": "warn", "detail": "Unavailable"}

    if b.get("error"):
        return {"name": "AWS Spending", "status": "warn", "detail": "Unavailable"}

    mtd = b.get("mtd_total", 0) or 0
    detail = f"${mtd:.2f} MTD (budget ${_AWS_BUDGET:.0f})"
    if mtd >= _AWS_BUDGET:
        issues.append({"severity": "warn", "source": "AWS Spending", "message": f"${mtd:.2f} this month exceeds ${_AWS_BUDGET:.0f} budget"})
        return {"name": "AWS Spending", "status": "warn", "detail": detail}
    return {"name": "AWS Spending", "status": "ok", "detail": detail}


def _check_claude(issues):
    try:
        c = collect_claude_dashboard_summary()
    except Exception:
        return {"name": "Claude Code", "status": "warn", "detail": "Unavailable"}

    pct = c.get("weekly_pct")
    if pct is None:
        return {"name": "Claude Code", "status": "warn", "detail": "No data"}

    detail = f"{pct}% of weekly limit"
    if pct >= _CLAUDE_WEEKLY_LIMIT:
        issues.append({"severity": "warn", "source": "Claude Code", "message": f"Weekly usage {pct}% (limit {_CLAUDE_WEEKLY_LIMIT}%)"})
        return {"name": "Claude Code", "status": "warn", "detail": detail}
    return {"name": "Claude Code", "status": "ok", "detail": detail}


def collect_status_overview():
    issues = []
    checks = [
        _check_k8s(issues),
        _check_synology(issues),
        _check_network(issues),
        _check_hosts(issues),
        _check_backup(issues),
        _check_aws(issues),
        _check_claude(issues),
    ]

    if any(i["severity"] == "critical" for i in issues):
        overall = "critical"
    elif issues:
        overall = "warn"
    else:
        overall = "ok"

    severity_rank = {"critical": 0, "warn": 1}
    issues.sort(key=lambda i: severity_rank.get(i["severity"], 2))

    return {
        "overall": overall,
        "issues": issues,
        "checks": checks,
    }
