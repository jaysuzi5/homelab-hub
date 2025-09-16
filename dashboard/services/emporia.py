import requests
from datetime import datetime, timedelta, timezone
from django.core.serializers.json import DjangoJSONEncoder

API_SEARCH_URL = "http://home.dev.com/api/v1/emporia/search"
COST_PER_KWH = 0.182


def _get_metrics():
    # Calculate start date as 7 days ago in UTC
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    payload = {
        "start_date": start_date,
        "name": "Electricity Monitor"
    }
    try:
        response = requests.post(API_SEARCH_URL, json=payload)
        if response.status_code in (200, 201):
            summary_info = response.json()
        else:
            print(f"Failed to post {payload['name']}: {response.status_code}, {response.text}")
            return []
    except requests.RequestException as e:
        print(f"Error posting {payload['name']}: {e}")
        return []
    # Only return {date, usage}
    simplified = [
        {"date": item["instant"].split("T")[0], "usage": item["usage"]}
        for item in summary_info
    ]
    return simplified

def _get_daily_metrics():
    start_date = (datetime.now(timezone.utc)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    payload = {"start_date": start_date}
    try:
        response = requests.post(API_SEARCH_URL, json=payload)
        if response.status_code in (200, 201):
            summary_info = response.json()
        else:
            print(f"Failed to post {payload['name']}: {response.status_code}, {response.text}")
            return []
    except requests.RequestException as e:
        print(f"Error posting {payload['name']}: {e}")
        return []
    # Only return {date, name, usage, percentage}
    simplified = [
        {"date": item["instant"].split("T")[0], "name": item["name"], "usage": item["usage"], "cost": item["usage"]*COST_PER_KWH, "percentage": item["percentage"]}
        for item in summary_info
    ]
    # Sort by usage descending, then move "Balance" to the end
    simplified_sorted = sorted(
        [d for d in simplified if d["name"] != "Balance"],
        key=lambda x: x["usage"],
        reverse=True
    )
    balance_row = [d for d in simplified if d["name"] == "Balance"]
    simplified_sorted.extend(balance_row)

    return simplified_sorted


def collect_emporia_summary():
    return _get_metrics()

def collect_emporia_daily_summary():
    return _get_daily_metrics()