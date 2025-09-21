import requests
from datetime import datetime, timedelta, timezone
from django.core.serializers.json import DjangoJSONEncoder

API_URL = "http://home.dev.com/api/v1/network?page=1&limit=1"


def _get_metrics():
    results = {}
    try:
        response = requests.get(API_URL)
        response.raise_for_status()  # raise exception if status != 2xx
        results = response.json()[0]
    except requests.RequestException as ex:
        print(f"Error fetching network data: {ex}")
        return None

    return results


def collect_network_summary():
    return _get_metrics()
