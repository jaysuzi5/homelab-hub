import requests
from datetime import datetime, timedelta
import pytz
from config.utils import get_config

PROMETHEUS_URL = get_config("PROMETHEUS_URL", "http://prometheus-operator-kube-p-prometheus.monitoring.svc.cluster.local:9090")


def _parse_earliest(earliest: str):
    end = datetime.now(tz=pytz.UTC)
    units = {"h": 3600, "d": 86400, "m": 60}
    try:
        val = int(earliest[1:-1])
        unit = earliest[-1]
        start = end - timedelta(seconds=val * units.get(unit, 3600))
    except Exception:
        start = end - timedelta(hours=1)
    return start, end


def prom_instant_query(query: str) -> dict:
    try:
        r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            return {"success": False, "data": [], "message": data.get("error", "Query failed")}
        return {"success": True, "data": data["data"]["result"], "result_type": data["data"]["resultType"]}
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}


def prom_range_query(query: str, earliest: str = "-1h", step: str = "60s") -> dict:
    try:
        start, end = _parse_earliest(earliest)
        r = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            return {"success": False, "data": [], "message": data.get("error", "Query failed")}
        return {"success": True, "data": data["data"]["result"], "result_type": data["data"]["resultType"]}
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}
