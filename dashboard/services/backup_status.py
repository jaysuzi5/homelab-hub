import boto3
import json
from datetime import datetime, timezone
from config.utils import get_config

_CACHE_KEY = "backup_status_cache"
_CACHE_TS_KEY = "backup_status_cache_updated"
_CACHE_TTL_HOURS = 2

_PRIMARY_APP = "homelab-hub"

# Thresholds (hours) for freshness classification
_OK_HOURS = 36
_WARN_HOURS = 24 * 8


def _bucket():
    return get_config("BACKUP_S3_BUCKET", "jay-curtis-backup")


def _client():
    region = get_config("AWS_DEFAULT_REGION", "us-east-1")
    key = get_config("backup_access_key_id", "")
    secret = get_config("backup_secret_access_key", "")

    kwargs = {"region_name": region}
    if key and secret:
        kwargs["aws_access_key_id"] = key
        kwargs["aws_secret_access_key"] = secret
    return boto3.client("s3", **kwargs)


def _age_label(hours):
    if hours < 1:
        mins = int(hours * 60)
        return f"{mins}m ago" if mins else "just now"
    if hours < 24:
        return f"{int(hours)}h ago"
    days = hours / 24
    return f"{int(days)}d ago"


def _status(hours):
    if hours <= _OK_HOURS:
        return "ok"
    if hours <= _WARN_HOURS:
        return "warn"
    return "stale"


def _save_cache(data):
    from config.models import HubConfig
    now = datetime.now(timezone.utc).isoformat()
    HubConfig.objects.update_or_create(key=_CACHE_KEY, defaults={"value": json.dumps(data)})
    HubConfig.objects.update_or_create(key=_CACHE_TS_KEY, defaults={"value": now})


def _load_cache():
    from config.models import HubConfig
    try:
        data_obj = HubConfig.objects.get(key=_CACHE_KEY)
        ts_obj = HubConfig.objects.get(key=_CACHE_TS_KEY)
        cached_at = datetime.fromisoformat(ts_obj.value)
        return json.loads(data_obj.value), cached_at
    except Exception:
        return None, None


def _fetch_live():
    s3 = _client()
    bucket = _bucket()
    now = datetime.now(timezone.utc)

    top = s3.list_objects_v2(Bucket=bucket, Delimiter="/")
    prefixes = [cp["Prefix"].rstrip("/") for cp in top.get("CommonPrefixes", [])]

    paginator = s3.get_paginator("list_objects_v2")
    apps = []
    for app in prefixes:
        latest = None
        total_size = 0
        count = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{app}/"):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue
                count += 1
                total_size += obj["Size"]
                if latest is None or obj["LastModified"] > latest["LastModified"]:
                    latest = obj

        if latest is None:
            continue

        age_hours = (now - latest["LastModified"]).total_seconds() / 3600
        apps.append({
            "app": app,
            "is_primary": app == _PRIMARY_APP,
            "latest_key": latest["Key"].split("/")[-1],
            "last_modified": latest["LastModified"].astimezone(timezone.utc).strftime("%-m/%-d/%Y %-I:%M %p UTC"),
            "age_label": _age_label(age_hours),
            "age_hours": round(age_hours, 1),
            "status": _status(age_hours),
            "size_mb": round(total_size / (1024 * 1024), 1),
            "count": count,
        })

    apps.sort(key=lambda a: (not a["is_primary"], a["app"]))

    primary = next((a for a in apps if a["is_primary"]), None)
    others = [a for a in apps if not a["is_primary"]]

    return {
        "primary": primary,
        "others": others,
        "bucket": bucket,
        "error": None,
    }


def collect_backup_status_summary(force=False):
    if not force:
        data, cached_at = _load_cache()
        if data and cached_at:
            age = datetime.now(timezone.utc) - cached_at
            if age.total_seconds() / 3600 < _CACHE_TTL_HOURS:
                data["cached_at"] = cached_at.strftime("%-m/%-d/%Y %-I:%M %p UTC")
                return data

    try:
        data = _fetch_live()
        _save_cache(data)
        data["cached_at"] = None
        return data
    except Exception as e:
        cached, cached_at = _load_cache()
        if cached:
            cached["cached_at"] = cached_at.strftime("%-m/%-d/%Y %-I:%M %p UTC") if cached_at else None
            cached["stale"] = True
            return cached
        return {
            "primary": None,
            "others": [],
            "bucket": _bucket(),
            "error": str(e),
            "cached_at": None,
        }
