import requests
from datetime import datetime, timedelta, timezone
from django.core.serializers.json import DjangoJSONEncoder

WEATHER_URL = "http://home.dev.com/api/v1/weather?page=1&limit=1"
FORECAST_URL = "http://home.dev.com/api/v1/forecast/latest"


def _get_metrics():
    results = {}
    try:
        # Get the weather
        response = requests.get(WEATHER_URL)
        response.raise_for_status()  # raise exception if status != 2xx
        results["weather"] = response.json()[0]
    except requests.RequestException as e:
        print(f"Error fetching weather: {e}")
        return None

    try:
        # Get the forecast
        response = requests.get(FORECAST_URL)
        response.raise_for_status()  # raise exception if status != 2xx
        results["forecast"] = response.json()
    except requests.RequestException as e:
        print(f"Error fetching forecast: {e}")
        return None

    return results


def collect_weather_summary():
    return _get_metrics()
