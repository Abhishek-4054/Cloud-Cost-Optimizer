"""
Oracle Cloud Infrastructure Pricing — OCI Public Pricing API.
"""
import httpx
import logging

logger  = logging.getLogger(__name__)
HOURS   = 730
OCI_URL = "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/"


def _oci_price(filter_str: str = "") -> list:
    params = {"productFilter": filter_str} if filter_str else {}
    r = httpx.get(OCI_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])


def _extract(items: list, keyword: str = "") -> float:
    for p in items:
        name = p.get("displayName","").lower()
        if keyword and keyword.lower() not in name:
            continue
        for loc in p.get("currencyCodeLocalizations",[]):
            if loc.get("currencyCode") == "USD":
                for price in loc.get("prices",[]):
                    if price.get("model") == "PAY_AS_YOU_GO":
                        v = float(price.get("value",0))
                        if v > 0: return v
    return 0.0


def get_compute_price() -> dict:
    hourly = _extract(_oci_price("Compute"), "e4") or 0.025 * 2  # 2 OCPUs
    return {"service":"OCI VM.Standard.E4.Flex (2 OCPU)","hourly_usd":round(hourly,6),"monthly_usd":round(hourly*HOURS,2),"source":"OCI Public Pricing API"}


def get_db_price() -> dict:
    hourly = _extract(_oci_price("Database"), "mysql") or 0.0416
    return {"service":"OCI MySQL HeatWave","hourly_usd":round(hourly,6),"monthly_usd":round(hourly*HOURS,2),"source":"OCI Public Pricing API"}


def get_storage_price(storage_gb: int) -> dict:
    pgb = 0.0255
    return {"service":"OCI Object Storage","storage_gb":storage_gb,"per_gb_usd":pgb,"monthly_usd":round(pgb*max(0,storage_gb-20),2),"source":"OCI Published Pricing"}


def get_cdn_price() -> dict:
    return {"service":"OCI CDN","transfer_gb":50,"monthly_usd":round(50*0.0085,2),"source":"OCI Published Pricing"}


def get_oci_total(compute_tier: str, storage_gb: int,
                  selected: list = None, extra: dict = None) -> dict:
    if selected is None: selected = ["compute","database","storage","cdn"]
    if extra is None:    extra    = {}

    result   = {"provider":"Oracle Cloud","region":"ap-mumbai-1"}
    total    = 0.0
    fetchers = {
        "compute":  lambda: get_compute_price(),
        "database": lambda: get_db_price(),
        "storage":  lambda: get_storage_price(storage_gb),
        "cdn":      lambda: get_cdn_price(),
    }

    for svc in selected:
        if svc in fetchers:
            try:
                data = fetchers[svc]()
                result[svc] = data
                total += data.get("monthly_usd", 0)
            except Exception as e:
                logger.error(f"OCI {svc} error: {e}")

    result["total_monthly_usd"] = round(total, 2)
    return result
