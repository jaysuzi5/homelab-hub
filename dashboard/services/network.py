import requests
from datetime import datetime, timezone
from config.utils import get_config
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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


def _get_metrics_by_month(year, month):
    """
    Fetch network metrics for a specific month.

    Args:
        year: Year (e.g., 2025)
        month: Month number (1-12)

    Returns:
        List of daily network metrics for the month, sorted by date.
    """
    # Calculate the first day of the month
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)

    # Calculate the last day of the month
    if month == 12:
        end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_dt = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    try:
        # Parse the URL to get base URL without query parameters
        parsed_url = urlparse(NETWORK_URL)

        # Build base URL without query parameters
        base_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            '',
            '',
            ''
        ))

        # Calculate how many pages we need based on how far back the month is
        # Assume ~144 records per day, 100 records per page
        now = datetime.now(timezone.utc)
        days_back = (now - start_dt).days
        estimated_pages = int((days_back * 144) / 100) + 10  # Add 10 page buffer
        max_pages = min(estimated_pages, 200)  # Cap at 200 pages for safety

        print(f"[DEBUG] Selected month is ~{days_back} days back, fetching ~{max_pages} pages")

        # Fetch historical data using pagination (API max limit is 100)
        # Keep fetching until we have data covering the entire selected month
        network_items = []
        page = 0

        for page in range(1, max_pages + 1):
            params = {'page': page, 'limit': 100}
            response = requests.get(base_url, params=params)

            if response.status_code != 200:
                print(f"[DEBUG] Stopped pagination at page {page}: status {response.status_code}")
                break

            page_data = response.json()
            if not page_data:
                print(f"[DEBUG] No more data at page {page}")
                break

            network_items.extend(page_data)

            # Check dates in this page to see if we've reached the start of the month
            for item in page_data:
                item_date = item.get('create_date', '').split('T')[0]
                if item_date and item_date >= start_date and item_date < end_date:
                    # We found data within our target month
                    if item_date[:7] == start_date[:7]:  # Check if it's from the start of the month
                        has_start_of_month = True

            # Check the oldest date in this page
            if page_data:
                oldest_date = page_data[-1].get('create_date', '').split('T')[0]
                # If we've gone past the start of the month, we can stop
                if oldest_date and oldest_date < start_date:
                    print(f"[DEBUG] Reached data before month start ({oldest_date}) at page {page}, stopping")
                    break

        print(f"[DEBUG] Monthly Network total records fetched: {len(network_items)} items after {page} pages")

        # Group by date and calculate daily averages
        daily_data = {}
        for item in network_items:
            create_date = item.get("create_date", "")
            if not create_date:
                continue

            # Extract just the date part
            date_only = create_date.split("T")[0]

            # Filter to only include dates in the selected month
            if start_date <= date_only < end_date:
                if date_only not in daily_data:
                    daily_data[date_only] = {
                        "download": [],
                        "upload": [],
                        "ping": [],
                        "tcp_latency": []
                    }

                # Append values if they exist (some records might have None)
                download = item.get("internet_download")
                upload = item.get("internet_upload")
                ping = item.get("internet_ping")
                tcp_latency = item.get("tcp_latency")

                if download is not None:
                    daily_data[date_only]["download"].append(download)
                if upload is not None:
                    daily_data[date_only]["upload"].append(upload)
                if ping is not None:
                    daily_data[date_only]["ping"].append(ping)
                if tcp_latency is not None:
                    daily_data[date_only]["tcp_latency"].append(tcp_latency)

        # Calculate averages for each day
        metrics = []
        for date, values in daily_data.items():
            avg_download = sum(values["download"]) / len(values["download"]) if values["download"] else 0
            avg_upload = sum(values["upload"]) / len(values["upload"]) if values["upload"] else 0
            avg_ping = sum(values["ping"]) / len(values["ping"]) if values["ping"] else 0
            avg_tcp_latency = sum(values["tcp_latency"]) / len(values["tcp_latency"]) if values["tcp_latency"] else 0

            metrics.append({
                "date": date,
                "download": avg_download,
                "upload": avg_upload,
                "ping": avg_ping,
                "tcp_latency": avg_tcp_latency
            })

        print(f"[DEBUG] Requested month: {year}-{month:02d} ({start_date} to {end_date})")
        print(f"[DEBUG] Aggregated daily data for {len(daily_data)} unique dates")
        if daily_data:
            print(f"[DEBUG] Date range in results: {min(daily_data.keys())} to {max(daily_data.keys())}")
        else:
            print(f"[DEBUG] No data found for the selected month")

        return sorted(metrics, key=lambda x: x["date"])

    except requests.RequestException as e:
        print(f"Error fetching network metrics for {year}-{month}: {e}")
        return []


def collect_network_summary():
    return _get_metrics()


def collect_network_monthly_summary(year, month):
    return _get_metrics_by_month(year, month)
