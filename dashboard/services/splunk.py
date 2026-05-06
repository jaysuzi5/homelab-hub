from datetime import datetime, timedelta
import time
import pytz
import requests
import urllib3
from jTookkit.jDateTime import DateUtility
from config.utils import get_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SPLUNK_HOST = get_config("SPLUNK_HOST")
SPLUNK_WEB_PORT = int(get_config("SPLUNK_WEB_PORT", 8000))
SPLUNK_USER = get_config("SPLUNK_USER", "admin")
SPLUNK_PASSWORD = get_config("SPLUNK_PASSWORD", "")

def _splunk_session():
    web_base = f"http://{SPLUNK_HOST}:{SPLUNK_WEB_PORT}"
    login_url = f"{web_base}/en-US/account/login"
    session = requests.Session()

    session.get(login_url, timeout=10)
    cval = session.cookies.get("cval", "")

    session.post(login_url, data={
        "username": SPLUNK_USER,
        "password": SPLUNK_PASSWORD,
        "cval": cval,
    }, timeout=10)

    return session, web_base

def _splunk_search(query: str, earliest: str = "-24h", latest: str = "now") -> dict:
    try:
        session, web_base = _splunk_session()
        jobs_url = f"{web_base}/en-US/splunkd/__raw/services/search/jobs"
        csrf_token = session.cookies.get(f"splunkweb_csrf_token_{SPLUNK_WEB_PORT}", "")

        r = session.post(jobs_url, data={
            "search": query,
            "output_mode": "json",
            "earliest_time": earliest,
            "latest_time": latest,
        }, headers={"X-Splunk-Form-Key": csrf_token, "X-Requested-With": "XMLHttpRequest"}, timeout=10)

        if r.status_code != 201:
            return {"success": False, "data": [], "message": f"Job create failed: {r.status_code} {r.text[:300]}"}
        sid = r.json()["sid"]

        status_url = f"{jobs_url}/{sid}"
        for _ in range(60):
            sr = session.get(status_url, params={"output_mode": "json"}, timeout=10)
            state = sr.json().get("entry", [{}])[0].get("content", {}).get("dispatchState", "")
            if state == "DONE":
                break
            time.sleep(0.5)
        else:
            return {"success": False, "data": [], "message": "Search job timed out"}

        rr = session.get(f"{status_url}/results", params={"output_mode": "json", "count": 1000}, timeout=15)
        results = rr.json().get("results", [])
        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}

def _transform_splunk_collector_summary(results: list):
    ten_minutes_ago = datetime.now(tz=pytz.UTC) - timedelta(minutes=10)
    four_hours_ago = datetime.now(tz=pytz.UTC) - timedelta(hours=4)

    transformed = []
    for item in results:
        last_run_utc = DateUtility.date_time_to_utc(item["last_run"])
        last_run_est_dt = DateUtility.date_time_to_est(item["last_run"])
        last_run_est_str = last_run_est_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        is_stale = last_run_utc < ten_minutes_ago
        if item["component"] == "enphase-collector":
            is_stale = last_run_utc < four_hours_ago
        is_bad_return_code = int(item["return_code"]) >= 400

        transformed.append({
            "component": item["component"],
            "return_code": item["return_code"],
            "count": item["count"],
            "duration": item["duration"],
            "last_run_est": last_run_est_str,
            "_last_run_est_dt": last_run_est_dt,
            "is_stale": is_stale,
            "is_bad_return_code": is_bad_return_code
        })

    transformed.sort(key=lambda x: x["_last_run_est_dt"], reverse=True)
    for item in transformed:
        del item["_last_run_est_dt"]
    return transformed

def otel_response_summary(earliest: str = "-1h") -> dict:
    query = r"""
        search index="otel_logging" event="Response"
        | rename service.name as service_name
        | eval endpoint = coalesce(endpoint, "none")
        | eval service = coalesce(service, service_name, "none")
        | eval status = coalesce(status, "")
        | eval method = coalesce(method, "")
        | eval path = coalesce(path, "")
        | stats dc(transaction_id) as transactions by service, endpoint, method, status
        | sort service, endpoint, method, status
    """
    result = _splunk_search(query, earliest=earliest)
    if not result["success"]:
        return {"success": False, "data": [], "message": result.get("message", "Query failed")}
    return {"success": True, "data": result["data"]}


def splunk_collector_summary():
    query = r"""
        search index="otel_logging"
        | rex field=_raw "['\"]event_type['\"]\s*:\s*['\"](?<_event_type>[^'\"]+)['\"]"
        | rex field=_raw "['\"]component['\"]\s*:\s*['\"](?<_component>[^'\"]+)['\"]"
        | rex field=_raw "['\"]return_code['\"]\s*:\s*(?<_return_code>[0-9]+)"
        | rex field=_raw "['\"]duration['\"]\s*:\s*(?<_duration>[0-9.]+)"
        | rex field=_raw "['\"]timestamp['\"]\s*:\s*['\"](?<_timestamp>[^'\"]+)['\"]"
        | eval event_type=coalesce(event_type, _event_type)
        | eval component=coalesce(component, _component)
        | eval return_code=coalesce(return_code, _return_code)
        | eval duration=coalesce(duration, _duration)
        | eval timestamp=coalesce(timestamp, _timestamp)
        | where event_type="transaction_end" AND match(component, ".*-collector.*")
        | stats count, avg(duration) as duration, max(duration) as max_duration, max(timestamp) as last_run, max(_time) as last_run_2 by component, return_code
        | eval duration = round(duration, 1)
        | eval max_duration = round(max_duration, 1)
        | sort component
    """
    result = _splunk_search(query)
    if not result["success"]:
        print(f"❌ Splunk query failed: {result['message']}")

    return _transform_splunk_collector_summary(result["data"])
