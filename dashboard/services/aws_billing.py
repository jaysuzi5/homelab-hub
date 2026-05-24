import boto3
import calendar
import json
from datetime import date, timedelta, datetime, timezone
from config.utils import get_config

_CACHE_KEY = "aws_billing_cache"
_CACHE_TS_KEY = "aws_billing_cache_updated"
_CACHE_TTL_DAYS = 7

# S3 standard storage pricing tiers (US, per GB-month)
_S3_TIERS = [
    (51_200,  0.023, "Tier 1"),   # 0 – 50 TB
    (512_000, 0.022, "Tier 2"),   # 50 – 500 TB
    (None,    0.021, "Tier 3"),   # 500 TB+
]


def _s3_tier(gb):
    for threshold, rate, name in _S3_TIERS:
        if threshold is None or gb < threshold:
            next_label = f"{threshold // 1024:,} TB" if threshold else None
            return {"rate": rate, "name": name, "next_tier": next_label}


def _save_cache(data):
    from config.models import HubConfig
    now = datetime.now(timezone.utc).isoformat()
    HubConfig.objects.update_or_create(key=_CACHE_KEY, defaults={"value": json.dumps(data)})
    HubConfig.objects.update_or_create(key=_CACHE_TS_KEY, defaults={"value": now})


def _load_cache():
    """Returns (data, cached_at_datetime) or (None, None)."""
    from config.models import HubConfig
    try:
        data_obj = HubConfig.objects.get(key=_CACHE_KEY)
        ts_obj = HubConfig.objects.get(key=_CACHE_TS_KEY)
        cached_at = datetime.fromisoformat(ts_obj.value)
        return json.loads(data_obj.value), cached_at
    except Exception:
        return None, None


def _fetch_live():
    region = get_config("AWS_DEFAULT_REGION", "us-east-1")
    aws_key = get_config("AWS_ACCESS_KEY_ID", "")
    aws_secret = get_config("AWS_SECRET_ACCESS_KEY", "")

    kwargs = {"region_name": region}
    if aws_key and aws_secret:
        kwargs["aws_access_key_id"] = aws_key
        kwargs["aws_secret_access_key"] = aws_secret

    ce = boto3.client("ce", **kwargs)

    today = date.today()
    month_start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    period_end = today.replace(day=last_day)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    mtd = ce.get_cost_and_usage(
        TimePeriod={"Start": str(month_start), "End": str(today)},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    last_month = ce.get_cost_and_usage(
        TimePeriod={"Start": str(last_month_start), "End": str(month_start)},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )

    services = []
    mtd_total = 0.0
    if mtd["ResultsByTime"]:
        for group in mtd["ResultsByTime"][0]["Groups"]:
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if amount >= 0.001:
                services.append({"name": group["Keys"][0], "cost": round(amount, 4)})
                mtd_total += amount
        services.sort(key=lambda x: x["cost"], reverse=True)

    last_total = 0.0
    if last_month["ResultsByTime"]:
        last_total = float(
            last_month["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
        )

    s3_gb = None
    days_elapsed = (today - month_start).days
    if days_elapsed > 0:
        s3_usage = ce.get_cost_and_usage(
            TimePeriod={"Start": str(month_start), "End": str(today)},
            Granularity="MONTHLY",
            Filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Simple Storage Service"]}},
            Metrics=["UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        )
        total_gb_hours = 0.0
        if s3_usage["ResultsByTime"]:
            for group in s3_usage["ResultsByTime"][0]["Groups"]:
                if "TimedStorage" in group["Keys"][0]:
                    total_gb_hours += float(group["Metrics"]["UsageQuantity"]["Amount"])
        if total_gb_hours > 0:
            s3_gb = round(total_gb_hours / (days_elapsed * 24), 3)

    return {
        "mtd_total": round(mtd_total, 2),
        "last_month_total": round(last_total, 2),
        "services": services[:10],
        "month_start": str(month_start),
        "period_end": str(period_end),
        "as_of": str(today),
        "currency": "USD",
        "s3_gb": s3_gb,
        "s3_tier": _s3_tier(s3_gb) if s3_gb is not None else None,
        "error": None,
    }


def collect_aws_billing_summary(force=False):
    if not force:
        data, cached_at = _load_cache()
        if data and cached_at:
            age = datetime.now(timezone.utc) - cached_at
            if age.days < _CACHE_TTL_DAYS:
                data["cached_at"] = cached_at.strftime("%-m/%-d/%Y %-I:%M %p UTC")
                return data

    try:
        data = _fetch_live()
        _save_cache(data)
        data["cached_at"] = None
        return data
    except Exception as e:
        # Fall back to stale cache rather than showing error if we have one
        cached, cached_at = _load_cache()
        if cached:
            cached["cached_at"] = cached_at.strftime("%-m/%-d/%Y %-I:%M %p UTC") if cached_at else None
            cached["stale"] = True
            return cached
        return {
            "error": str(e),
            "mtd_total": 0, "last_month_total": 0,
            "services": [], "s3_gb": None, "s3_tier": None,
            "cached_at": None,
        }
