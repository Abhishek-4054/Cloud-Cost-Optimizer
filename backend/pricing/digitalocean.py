"""
DigitalOcean Pricing — Live from DO public API + published rates.
"""
import httpx
import logging
from config.settings import DOConfig

logger  = logging.getLogger(__name__)
REGION  = DOConfig.REGION


def get_droplet_price(compute_tier: str) -> dict:
    r      = httpx.get("https://api.digitalocean.com/v2/sizes", timeout=15)
    r.raise_for_status()
    sizes  = r.json().get("sizes", [])
    avail  = [s for s in sizes if s.get("available") and REGION in s.get("regions",[])]
    targets = {"small":{"vcpus":1,"memory":2048},"medium":{"vcpus":2,"memory":4096},"large":{"vcpus":4,"memory":8192},"xlarge":{"vcpus":8,"memory":16384}}
    t       = targets.get(compute_tier, targets["medium"])
    matches = sorted([s for s in avail if s["vcpus"]>=t["vcpus"] and s["memory"]>=t["memory"]], key=lambda x: x["price_monthly"])
    best    = (matches or sorted(avail, key=lambda x: x["price_monthly"]))[0]
    return {"service":f"DO Droplet {best['slug']}","slug":best["slug"],"vcpus":best["vcpus"],"hourly_usd":round(best["price_hourly"],6),"monthly_usd":round(best["price_monthly"],2),"source":"DigitalOcean API (live)"}


def get_managed_db_price(compute_tier: str) -> dict:
    plans = {"small":{"plan":"db-s-1vcpu-2gb","monthly_usd":30.0},"medium":{"plan":"db-s-2vcpu-4gb","monthly_usd":60.0},"large":{"plan":"db-s-4vcpu-8gb","monthly_usd":120.0},"xlarge":{"plan":"db-s-6vcpu-16gb","monthly_usd":240.0}}
    p = plans.get(compute_tier, plans["medium"])
    return {"service":f"DO Managed PostgreSQL ({p['plan']})","plan":p["plan"],"monthly_usd":p["monthly_usd"],"source":"DigitalOcean Published Pricing"}


def get_spaces_price(storage_gb: int) -> dict:
    extra = max(0, storage_gb - 250)
    return {"service":"DigitalOcean Spaces","storage_gb":storage_gb,"monthly_usd":round(25.0 + extra*0.02,2),"source":"DigitalOcean Published Pricing"}


def get_cdn_price() -> dict:
    return {"service":"DO CDN (included with Spaces)","monthly_usd":0.0,"source":"DigitalOcean Published Pricing"}


def get_functions_price(invocations: int = 1000000) -> dict:
    # DO Functions: $0.0000185/GB-second, first 90K GB-seconds free
    gb_sec   = (128/1024) * 0.2 * invocations
    billable = max(0, gb_sec - 90000)
    cost     = billable * 0.0000185
    return {"service":"DigitalOcean Functions","invocations":invocations,"monthly_usd":round(cost,2),"source":"DigitalOcean Published Pricing"}


def get_k8s_price(nodes: int = 3) -> dict:
    # DOKS: free control plane, $12/node (s-1vcpu-2gb)
    return {"service":f"DOKS ({nodes}x s-1vcpu-2gb)","nodes":nodes,"monthly_usd":round(12.0*nodes,2),"source":"DigitalOcean Published Pricing"}


def get_do_total(compute_tier: str, storage_gb: int,
                 selected: list = None, extra: dict = None) -> dict:
    if selected is None: selected = ["compute","database","storage","cdn"]
    if extra is None:    extra    = {}

    result = {"provider":"DigitalOcean","region":REGION}
    total  = 0.0

    fetchers = {
        "compute":    lambda: get_droplet_price(compute_tier),
        "database":   lambda: get_managed_db_price(compute_tier),
        "storage":    lambda: get_spaces_price(storage_gb),
        "cdn":        lambda: get_cdn_price(),
        "serverless": lambda: get_functions_price(extra.get("lambda_invocations",1000000)),
        "kubernetes": lambda: get_k8s_price(extra.get("k8s_nodes",3)),
    }

    for svc in selected:
        if svc in fetchers:
            try:
                data = fetchers[svc]()
                result[svc] = data
                total += data.get("monthly_usd", 0)
            except Exception as e:
                logger.error(f"DO {svc} error: {e}")

    result["total_monthly_usd"] = round(total, 2)
    return result
