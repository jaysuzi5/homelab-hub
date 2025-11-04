import requests
from datetime import datetime, timedelta, timezone
from config.utils import get_config

EMPORIA_API_SEARCH_URL = get_config("EMPORIA_API_SEARCH_URL")
ENPHASE_API_SEARCH_URL = get_config("ENPHASE_API_SEARCH_URL")
COST_PER_KWH = float(get_config("COST_PER_KWH"))


def _get_metrics():
    # Calculate start date as 7 days ago
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    # --- Get Enphase produced metrics ---
    enphase_data = {}
    try:
        params = {"start_date": start_date}
        print(f"[DEBUG] Enphase GET call: {ENPHASE_API_SEARCH_URL}")
        print(f"[DEBUG] Enphase params: {params}")
        response = requests.get(ENPHASE_API_SEARCH_URL, params=params)
        print(f"[DEBUG] Enphase response status: {response.status_code}")
        response.raise_for_status()
        for item in response.json():
            # Convert produced from Wh to kWh
            enphase_data[item["summary_date"]] = item["max_energy_today"] / 1000
    except requests.RequestException as e:
        print(f"Error fetching Enphase summary: {e}")

    # --- Get Emporia usage metrics ---
    emporia_data = {}
    emporia_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    payload = {"start_date": emporia_start,
               "name": "Electricity Monitor"}
    try:
        print(f"[DEBUG] Emporia POST call: {EMPORIA_API_SEARCH_URL}")
        print(f"[DEBUG] Emporia payload: {payload}")
        response = requests.post(EMPORIA_API_SEARCH_URL, json=payload)
        print(f"[DEBUG] Emporia response status: {response.status_code}")
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


def _get_daily_metrics(target_date=None):
    """
    Fetch daily metrics for a specific date (defaults to today).

    Args:
        target_date: Optional date string in format 'YYYY-MM-DD'. Defaults to current date.

    Returns:
        List of daily usage summaries sorted by usage descending with Balance at the end.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    else:
        # Parse the target_date and convert to UTC ISO format
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_date = target_dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    payload = {"start_date": start_date}
    try:
        print(f"[DEBUG] Daily Emporia POST call: {EMPORIA_API_SEARCH_URL}")
        print(f"[DEBUG] Target date: {target_date}")
        print(f"[DEBUG] Daily Emporia payload: {payload}")
        response = requests.post(EMPORIA_API_SEARCH_URL, json=payload)
        print(f"[DEBUG] Daily Emporia response status: {response.status_code}")
        if response.status_code in (200, 201):
            summary_info = response.json()
            print(f"[DEBUG] Daily Emporia raw response count: {len(summary_info)} items")
        else:
            print(f"Failed to post to Emporia API: {response.status_code}, {response.text}")
            return []
    except requests.RequestException as e:
        print(f"Error posting to Emporia API: {e}")
        return []

    # Only return {date, name, usage, cost, percentage} and filter to target_date only
    simplified = [
        {"date": item["instant"].split("T")[0], "name": item["name"], "usage": item["usage"], "cost": item["usage"]*COST_PER_KWH, "percentage": item["percentage"]}
        for item in summary_info
        if item["instant"].split("T")[0] == target_date  # Filter to only the target date
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


def _get_metrics_by_month(year, month):
    """
    Fetch metrics for a specific month (all days in that month).

    Args:
        year: Year (e.g., 2025)
        month: Month number (1-12)

    Returns:
        List of daily metrics for the month, sorted by date.
    """
    # Calculate the first day of the month
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)

    # Calculate the last day of the month
    if month == 12:
        end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    else:
        end_dt = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)

    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    # --- Get Enphase produced metrics ---
    enphase_data = {}
    try:
        params = {"start_date": start_date, "end_date": end_date}
        print(f"[DEBUG] Monthly Enphase GET call: {ENPHASE_API_SEARCH_URL}")
        print(f"[DEBUG] Monthly Enphase params: {params}")
        response = requests.get(ENPHASE_API_SEARCH_URL, params=params)
        print(f"[DEBUG] Monthly Enphase response status: {response.status_code}")
        response.raise_for_status()
        enphase_items = response.json()
        print(f"[DEBUG] Monthly Enphase raw response count: {len(enphase_items)} items")
        for item in enphase_items:
            # Convert produced from Wh to kWh
            enphase_data[item["summary_date"]] = item["max_energy_today"] / 1000
    except requests.RequestException as e:
        print(f"Error fetching Enphase summary for {year}-{month}: {e}")

    # --- Get Emporia usage metrics ---
    emporia_data = {}
    # Set end_date to the first of the next month (API query boundary)
    if month == 12:
        end_dt_next = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_dt_next = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    payload = {
        "start_date": start_dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "end_date": end_dt_next.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "name": "Electricity Monitor"
    }
    try:
        print(f"[DEBUG] Monthly Emporia POST call: {EMPORIA_API_SEARCH_URL}")
        print(f"[DEBUG] Monthly Emporia payload: {payload}")
        response = requests.post(EMPORIA_API_SEARCH_URL, json=payload)
        print(f"[DEBUG] Monthly Emporia response status: {response.status_code}")
        response.raise_for_status()
        emporia_items = response.json()
        print(f"[DEBUG] Monthly Emporia raw response count: {len(emporia_items)} items")
        for item in emporia_items:
            date = item["instant"].split("T")[0]
            emporia_data[date] = item["usage"]
    except requests.RequestException as e:
        print(f"Error fetching Emporia metrics for {year}-{month}: {e}")

    # --- Combine by date and filter to only the selected month ---
    all_dates = set(enphase_data.keys()) | set(emporia_data.keys())
    combined = []
    for date in sorted(all_dates):
        # Only include dates that are within the selected month
        if start_date <= date <= end_date:
            combined.append({
                "date": date,
                "usage": emporia_data.get(date, 0),
                "produced": enphase_data.get(date, 0)
            })

    return combined


def collect_emporia_summary():
    return _get_metrics()

def collect_emporia_daily_summary(target_date=None):
    return _get_daily_metrics(target_date)

def collect_emporia_monthly_summary(year, month):
    return _get_metrics_by_month(year, month)