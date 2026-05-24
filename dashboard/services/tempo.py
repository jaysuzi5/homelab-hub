import requests
from datetime import datetime, timedelta
import pytz
from config.utils import get_config

TEMPO_URL = get_config("TEMPO_URL", "http://tempo.monitoring.svc.cluster.local:3100")


def _parse_earliest(earliest: str):
    end = datetime.now(tz=pytz.UTC)
    units = {"h": 3600, "d": 86400, "m": 60}
    try:
        val = int(earliest[1:-1])
        unit = earliest[-1]
        start = end - timedelta(seconds=val * units.get(unit, 3600))
    except Exception:
        start = end - timedelta(hours=1)
    return int(start.timestamp()), int(end.timestamp())


def tempo_services() -> dict:
    try:
        r = requests.get(f"{TEMPO_URL}/api/search/tag/service.name/values", timeout=10)
        r.raise_for_status()
        return {"success": True, "data": sorted(r.json().get("tagValues", []))}
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}


def tempo_recent_traces(service: str = "", earliest: str = "-1h", limit: int = 50, root_span: str = "") -> dict:
    try:
        start_ts, end_ts = _parse_earliest(earliest)
        params = {"limit": limit, "start": start_ts, "end": end_ts}
        tags_parts = []
        if service:
            tags_parts.append(f"service.name={service}")
        if root_span:
            tags_parts.append(f"name={root_span}")
        if tags_parts:
            params["tags"] = " ".join(tags_parts)
        r = requests.get(f"{TEMPO_URL}/api/search", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return {"success": True, "data": data.get("traces", []), "metrics": data.get("metrics", {})}
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}


def tempo_trace_detail(trace_id: str) -> dict:
    try:
        r = requests.get(f"{TEMPO_URL}/api/traces/{trace_id}", timeout=10)
        r.raise_for_status()
        return {"success": True, "data": r.json()}
    except Exception as e:
        return {"success": False, "data": {}, "message": str(e)}
