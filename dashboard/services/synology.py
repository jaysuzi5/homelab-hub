import requests
from config.utils import get_config

SYNOLOGY_URL = get_config("SYNOLOGY_URL")


def _get_metrics():
    results = {}
    try:
        response = requests.get(SYNOLOGY_URL)
        response.raise_for_status()  # raise exception if status != 2xx
        results = response.json()[0]
    except requests.RequestException as ex:
        print(f"Error fetching synology data: {ex}")
        return None
    return results


def collect_synology_summary():
    return _get_metrics()
