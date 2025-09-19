import requests
from datetime import datetime, timedelta, timezone
from django.core.serializers.json import DjangoJSONEncoder

EMPORIA_API_SEARCH_URL = "http://home.dev.com/api/v1/emporia/search"
ENPHASE_API_SEARCH_URL = "http://home.dev.com/api/v1/enphase/summary"
COST_PER_KWH = 0.182


def _get_enphase_metrics():
    # Calculate start date as 7 days ago in UTC (YYYY-MM-DD)
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    
    params = {"start_date": start_date}
    
    try:
        response = requests.get(ENPHASE_API_SEARCH_URL, params=params)
        response.raise_for_status()  # raise exception if status != 2xx
        summary_info = response.json()
    except requests.RequestException as e:
        print(f"Error fetching summary: {e}")
        return []

    # Only return {date, produced} equivalent
    simplified = [
        {"date": item["summary_date"], "produced": item["max_energy_today"]}
        for item in summary_info
    ]
    return simplified

def _get_emporia_metrics():
    # Calculate start date as 7 days ago in UTC
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    payload = {
        "start_date": start_date,
        "name": "Electricity Monitor"
    }
    try:
        response = requests.post(EMPORIA_API_SEARCH_URL, json=payload)
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


from datetime import datetime, timedelta, timezone
import requests

def _get_metrics():
    # Calculate start date as 7 days ago
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    # --- Get Enphase produced metrics ---
    enphase_data = {}
    try:
        response = requests.get(ENPHASE_API_SEARCH_URL, params={"start_date": start_date})
        response.raise_for_status()
        for item in response.json():
            # Convert produced from Wh to kWh
            enphase_data[item["summary_date"]] = item["max_energy_today"] / 1000
    except requests.RequestException as e:
        print(f"Error fetching Enphase summary: {e}")

    # --- Get Emporia usage metrics ---
    emporia_data = {}
    payload = {"start_date": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
               "name": "Electricity Monitor"}
    try:
        response = requests.post(EMPORIA_API_SEARCH_URL, json=payload)
        response.raise_for_status()
        for item in response.json():
            date = item["instant"].split("T")[0]
            emporia_data[date] = item["usage"]
    except requests.RequestException as e:
        print(f"Error fetching Emporia metrics: {e}")

    # --- Combine by date ---
    all_dates = set(enphase_data.keys()) | set(emporia_data.keys())
    combined = []
    for date in sorted(all_dates):
        combined.append({
            "date": date,
            "usage": emporia_data.get(date, 0),
            "produced": enphase_data.get(date, 0)
        })

    return combined


def _get_daily_metrics():
    start_date = (datetime.now(timezone.utc)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    payload = {"start_date": start_date}
    try:
        response = requests.post(EMPORIA_API_SEARCH_URL, json=payload)
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