import requests
from datetime import datetime, timedelta, timezone
from config.utils import get_config

ENPHASE_API_SEARCH_URL = get_config("ENPHASE_API_SEARCH_URL")


def _get_metrics():
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


def collect_enhase_summary():
    return _get_metrics()
