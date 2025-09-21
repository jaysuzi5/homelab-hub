import requests
from config.utils import get_config

NETWORK_URL = get_config("NETWORK_URL")


def _get_metrics():
    results = {}
    try:
        response = requests.get(NETWORK_URL)
        response.raise_for_status()  # raise exception if status != 2xx
        results = response.json()[0]
    except requests.RequestException as ex:
        print(f"Error fetching network data: {ex}")
        return None

    return results


def collect_network_summary():
    return _get_metrics()
