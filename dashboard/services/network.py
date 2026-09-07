import requests
import concurrent.futures
import psycopg2
from datetime import datetime, timezone
from django.core.cache import cache
from config.utils import get_config
from urllib.parse import urlparse, urlunparse

NETWORK_URL = get_config("NETWORK_URL")

# The network collector (a separate service) writes to its own Postgres database.
# Reading it directly lets Postgres do the daily rollup instead of us paging through
# the collector's REST API and averaging tens of thousands of raw rows in Python.
_NETWORK_DB_HOST = get_config("NETWORK_DB_HOST")
_NETWORK_DB_PORT = get_config("NETWORK_DB_PORT", "5432")
_NETWORK_DB_NAME = get_config("NETWORK_DB_NAME")
_NETWORK_DB_USER = get_config("NETWORK_DB_USER")
_NETWORK_DB_PASSWORD = get_config("NETWORK_DB_PASSWORD")

# Collector writes a large sentinel (~1,800,000 ms = 30 min) when a ping/speedtest
# times out. Any value at or above this threshold is a timeout, not a real latency.
_TIMEOUT_MS = 10000

_REQUEST_TIMEOUT = 10  # seconds, per HTTP call to the network collector API
_PAGE_WORKERS = 10  # parallel page fetches per batch


def _fetch_page(base_url, page, limit=100):
    try:
        response = requests.get(base_url, params={'page': page, 'limit': limit}, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        return page, response.json()
    except requests.RequestException as e:
        print(f"[DEBUG] Error fetching network page {page}: {e}")
        return page, None


def _get_metrics():
    """
    Fetch the most recent network metrics.
    Looks back up to 1 hour to find the latest non-null value for each metric.
    """
    try:
        # Parse the URL to get base URL without query parameters
        parsed_url = urlparse(NETWORK_URL)
        base_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            '',
            '',
            ''
        ))

        # Fetch recent records (last hour, approximately 12 records if testing every 5 min)
        # Using limit of 50 to be safe
        params = {'page': 1, 'limit': 50}
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        records = response.json()

        if not records:
            return None

        # Initialize result with values from the most recent record
        result = {
            'tcp_latency': None,
            'internet_ping': None,
            'internet_download': None,
            'internet_upload': None,
            'online': records[0].get('online', False),
            'id': records[0].get('id'),
            'create_date': records[0].get('create_date'),
            'update_date': records[0].get('update_date')
        }

        # Find the most recent non-null value for each metric
        for record in records:
            # Stop looking if we already have all metrics
            if all([result['tcp_latency'] is not None,
                    result['internet_ping'] is not None,
                    result['internet_download'] is not None,
                    result['internet_upload'] is not None]):
                break

            # Check record age (only use records from last hour)
            record_date = record.get('create_date', '')
            if record_date:
                record_time = datetime.fromisoformat(record_date.replace('Z', '+00:00'))
                age = datetime.now(timezone.utc) - record_time
                if age.total_seconds() > 3600:  # More than 1 hour old
                    break

            # Fill in missing metrics with most recent non-null values
            if result['tcp_latency'] is None and record.get('tcp_latency') is not None:
                result['tcp_latency'] = record.get('tcp_latency')

            if result['internet_ping'] is None and record.get('internet_ping') is not None:
                result['internet_ping'] = record.get('internet_ping')

            if result['internet_download'] is None and record.get('internet_download') is not None:
                result['internet_download'] = record.get('internet_download')

            if result['internet_upload'] is None and record.get('internet_upload') is not None:
                result['internet_upload'] = record.get('internet_upload')

        # Flag timeout sentinels and blank the value so the UI shows "Timeout"
        result['tcp_latency_timeout'] = (
            result['tcp_latency'] is not None and result['tcp_latency'] >= _TIMEOUT_MS
        )
        result['internet_ping_timeout'] = (
            result['internet_ping'] is not None and result['internet_ping'] >= _TIMEOUT_MS
        )
        if result['tcp_latency_timeout']:
            result['tcp_latency'] = None
        if result['internet_ping_timeout']:
            result['internet_ping'] = None

        # Set defaults for any metrics still null (but keep None for timeouts)
        if result['tcp_latency'] is None and not result['tcp_latency_timeout']:
            result['tcp_latency'] = 0
        if result['internet_ping'] is None and not result['internet_ping_timeout']:
            result['internet_ping'] = 0
        if result['internet_download'] is None:
            result['internet_download'] = 0
        if result['internet_upload'] is None:
            result['internet_upload'] = 0

        return result

    except requests.RequestException as ex:
        print(f"Error fetching network data: {ex}")
        return None


def _get_daily_rollup_from_db(start_dt, end_dt):
    """
    Roll up daily network averages directly from the collector's Postgres database,
    so the aggregation runs in Postgres instead of over the REST API in Python.

    Returns None (rather than []) on any connection/query failure, so callers can
    fall back to the REST API path instead of reporting "no data".
    """
    if not (_NETWORK_DB_HOST and _NETWORK_DB_NAME and _NETWORK_DB_USER):
        return None

    query = """
        SELECT
            (create_date AT TIME ZONE 'UTC')::date AS day,
            AVG(internet_download) AS download,
            AVG(internet_upload) AS upload,
            AVG(internet_ping) FILTER (WHERE internet_ping < %(timeout)s) AS ping,
            AVG(tcp_latency) FILTER (WHERE tcp_latency < %(timeout)s) AS tcp_latency
        FROM network
        WHERE create_date >= %(start)s AND create_date < %(end)s
        GROUP BY day
        ORDER BY day;
    """
    try:
        with psycopg2.connect(
            host=_NETWORK_DB_HOST,
            port=_NETWORK_DB_PORT,
            dbname=_NETWORK_DB_NAME,
            user=_NETWORK_DB_USER,
            password=_NETWORK_DB_PASSWORD,
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"start": start_dt, "end": end_dt, "timeout": _TIMEOUT_MS})
                rows = cur.fetchall()
    except psycopg2.Error as e:
        print(f"[DEBUG] Network DB rollup failed, falling back to REST API: {e}")
        return None

    return [
        {
            "date": day.strftime("%Y-%m-%d"),
            "download": float(download) if download is not None else 0,
            "upload": float(upload) if upload is not None else 0,
            "ping": float(ping) if ping is not None else 0,
            "tcp_latency": float(tcp_latency) if tcp_latency is not None else 0,
        }
        for day, download, upload, ping, tcp_latency in rows
    ]


def _get_metrics_by_month_via_api(year, month, start_date, end_date):
    """
    Fallback for when the collector's database isn't reachable: fetch raw records
    via its REST API (paginated, no server-side date filter) and average in Python.

    Args:
        year: Year (e.g., 2025)
        month: Month number (1-12)
        start_date / end_date: "YYYY-MM-DD" bounds of the selected month.

    Returns:
        List of daily network metrics for the month, sorted by date.
    """
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)

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

        # Fetch historical data using pagination (API max limit is 100, no server-side
        # date filtering available). Records are newest-first, so we page forward in
        # parallel batches (doubling batch size) until we pass the start of the month,
        # instead of issuing hundreds of pages one request at a time.
        network_items = []
        page = 0
        next_page = 1
        batch_size = _PAGE_WORKERS
        reached_start = False

        with concurrent.futures.ThreadPoolExecutor(max_workers=_PAGE_WORKERS) as executor:
            while next_page <= max_pages and not reached_start:
                batch_pages = list(range(next_page, min(next_page + batch_size, max_pages + 1)))
                futures = {executor.submit(_fetch_page, base_url, p): p for p in batch_pages}
                pages_data = {}
                for fut, p in futures.items():
                    pages_data[p] = fut.result()[1]

                for p in batch_pages:
                    page = p
                    page_data = pages_data.get(p)
                    if not page_data:
                        print(f"[DEBUG] No more data (or fetch error) at page {p}")
                        reached_start = True
                        break

                    network_items.extend(page_data)

                    # Check the oldest date in this page
                    oldest_date = page_data[-1].get('create_date', '').split('T')[0]
                    if oldest_date and oldest_date < start_date:
                        print(f"[DEBUG] Reached data before month start ({oldest_date}) at page {p}, stopping")
                        reached_start = True
                        break

                next_page = batch_pages[-1] + 1
                batch_size = min(batch_size * 2, 50)

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
                if ping is not None and ping < _TIMEOUT_MS:
                    daily_data[date_only]["ping"].append(ping)
                if tcp_latency is not None and tcp_latency < _TIMEOUT_MS:
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


def _get_metrics_by_month(year, month):
    """
    Fetch daily-averaged network metrics for a specific month.

    Args:
        year: Year (e.g., 2025)
        month: Month number (1-12)

    Returns:
        List of daily network metrics for the month, sorted by date.
    """
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_dt = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    rollup = _get_daily_rollup_from_db(start_dt, end_dt)
    if rollup is not None:
        return rollup

    return _get_metrics_by_month_via_api(
        year, month, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
    )


def collect_network_summary():
    return _get_metrics()


def collect_network_monthly_summary(year, month):
    now = datetime.now(timezone.utc)
    is_current_month = (year == now.year and month == now.month)

    cache_key = f"network_monthly_summary:{year}:{month:02d}"
    if not is_current_month:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    result = _get_metrics_by_month(year, month)

    if is_current_month:
        # In-progress month: short TTL so today's data keeps updating.
        cache.set(cache_key, result, timeout=300)
    elif result:
        # Completed month: history never changes, cache indefinitely.
        cache.set(cache_key, result, timeout=None)

    return result
