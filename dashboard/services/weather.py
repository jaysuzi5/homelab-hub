import requests
from config.utils import get_config

WEATHER_URL = get_config("WEATHER_URL")
FORECAST_URL = get_config("FORECAST_URL")
 

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
