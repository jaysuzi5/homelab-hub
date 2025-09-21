from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import pytz
from jTookkit.jSplunk import SplunkClient
from jTookkit.jDateTime import DateUtility


load_dotenv()
SPLUNK_HOST = "splunk.home"
SPLUNK_PORT = 8089
SPLUNK_USER = "admin"
SPLUNK_PASSWORD = os.getenv("SPLUNK_PASSWORD")


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
            "_last_run_est_dt": last_run_est_dt,  # helper for sorting
            "is_stale": is_stale,
            "is_bad_return_code": is_bad_return_code
        })

    # Sort descending by last_run_est datetime
    transformed.sort(key=lambda x: x["_last_run_est_dt"], reverse=True)

    # Remove the helper datetime before returning
    for item in transformed:
        del item["_last_run_est_dt"]
    return transformed

def splunk_collector_summary():
    splunk = SplunkClient(
        host = SPLUNK_HOST,
        port = SPLUNK_PORT,
        username = SPLUNK_USER,
        password = SPLUNK_PASSWORD
    )

    query = """
        search index="otel_logging" component="*-collector" event_type="transaction_end"
        | stats count, avg(duration) as duration, max(duration) as max_duration, max(timestamp) as last_run, max(_time) as last_run_2 by component, return_code
        | eval duration = round(duration, 1)
        | eval max_duration = round(max_duration, 1)
        | sort component    
    """
    result = splunk.query(query)
    if not result["success"]:
        print(f"❌ Query failed: {result['message']}")    

    return _transform_splunk_collector_summary(result["data"])
