import boto3
from datetime import date, timedelta
from config.utils import get_config


def collect_aws_billing_summary():
    try:
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
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        # MTD cost by service
        mtd = ce.get_cost_and_usage(
            TimePeriod={"Start": str(month_start), "End": str(today)},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Last month total
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

        return {
            "mtd_total": round(mtd_total, 2),
            "last_month_total": round(last_total, 2),
            "services": services[:10],
            "month_start": str(month_start),
            "as_of": str(today),
            "currency": "USD",
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "mtd_total": 0, "last_month_total": 0, "services": []}
