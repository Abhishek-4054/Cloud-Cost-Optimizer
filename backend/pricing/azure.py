"""
Azure Pricing — Live from Azure Retail Pricing API (no auth needed).
Services: Compute, DB, Storage, CDN, AI/ML (Azure OpenAI),
          Serverless (Functions), Kubernetes (AKS), Analytics (Synapse),
          Messaging (Service Bus), Cache (Azure Cache for Redis)
"""
import httpx
import logging
from config.settings import AzureConfig

logger  = logging.getLogger(__name__)
HOURS   = 730
BASE    = AzureConfig.PRICING_URL
REGION  = AzureConfig.REGION
VER     = AzureConfig.API_VERSION


def _fetch(filter_str: str) -> list:
    r = httpx.get(BASE, params={"$filter": filter_str, "api-version": VER}, timeout=15)
    r.raise_for_status()
    return r.json().get("Items", [])


def get_vm_price(sku: str) -> dict:
    items = _fetch(f"armRegionName eq '{REGION}' and skuName eq '{sku}' and priceType eq 'Consumption' and serviceName eq 'Virtual Machines'")
    linux = [i for i in items if "Windows" not in i.get("productName","")]
    item  = (linux or items)[0] if (linux or items) else None
    if not item:
        raise ValueError(f"No Azure VM price for {sku}")
    h = item["retailPrice"]
    return {"service":f"Azure VM {sku}","sku":sku,"hourly_usd":round(h,6),"monthly_usd":round(h*HOURS,2),"source":"Azure Retail API (live)"}


def get_db_price() -> dict:
    items = _fetch(f"armRegionName eq '{REGION}' and serviceName eq 'Azure Database for PostgreSQL' and priceType eq 'Consumption'")
    if not items:
        raise ValueError("No Azure DB price")
    h = items[0]["retailPrice"]
    return {"service":f"Azure DB for PostgreSQL ({items[0].get('skuName','')})","hourly_usd":round(h,6),"monthly_usd":round(h*HOURS,2),"source":"Azure Retail API (live)"}


def get_blob_price(storage_gb: int) -> dict:
    items = _fetch(f"armRegionName eq '{REGION}' and serviceName eq 'Storage' and skuName eq 'LRS' and priceType eq 'Consumption' and meterName eq 'LRS Data Stored'")
    if not items:
        raise ValueError("No Azure Blob price")
    pgb = items[0]["retailPrice"]
    return {"service":"Azure Blob Storage LRS","storage_gb":storage_gb,"per_gb_usd":round(pgb,6),"monthly_usd":round(pgb*storage_gb,2),"source":"Azure Retail API (live)"}


def get_cdn_price() -> dict:
    items = _fetch(f"armRegionName eq '{REGION}' and serviceName eq 'Content Delivery Network' and priceType eq 'Consumption'")
    if items:
        pgb = items[0]["retailPrice"]
        return {"service":"Azure CDN","transfer_gb":50,"monthly_usd":round(pgb*50,2),"source":"Azure Retail API (live)"}
    raise ValueError("No Azure CDN price")


# ── AI/ML ─────────────────────────────────────────────────────────────────────
def get_openai_price(requests: int = 100000) -> dict:
    # Azure OpenAI GPT-3.5-Turbo: $0.002/1K tokens
    # Avg 700 tokens/request
    tokens_k = (requests * 700) / 1000
    cost     = tokens_k * 0.002
    return {"service":"Azure OpenAI (GPT-3.5-Turbo)","requests":requests,"monthly_usd":round(cost,2),"source":"Azure Published Pricing"}


def get_ml_studio_price() -> dict:
    # Azure ML compute: Standard_DS2_v2 $0.201/hr
    return {"service":"Azure Machine Learning Studio (DS2_v2)","hourly_usd":0.201,"monthly_usd":round(0.201*HOURS,2),"source":"Azure Published Pricing"}


# ── Serverless ────────────────────────────────────────────────────────────────
def get_functions_price(invocations: int = 1000000) -> dict:
    # First 1M free, $0.20/million after
    billable  = max(0, invocations - 1000000)
    req_cost  = (billable / 1000000) * 0.20
    gb_secs   = (128/1024) * 0.2 * invocations
    dur_cost  = max(0, gb_secs - 400000) * 0.000016
    total     = req_cost + dur_cost
    return {"service":"Azure Functions","invocations":invocations,"monthly_usd":round(total,2),"source":"Azure Published Pricing"}


# ── Kubernetes ────────────────────────────────────────────────────────────────
def get_aks_price(nodes: int = 3) -> dict:
    # AKS control plane is FREE, pay only for worker nodes
    # Standard_D2s_v3: $0.096/hr
    node_cost = 0.096 * HOURS * nodes
    return {"service":f"Azure AKS ({nodes}x Standard_D2s_v3)","nodes":nodes,"monthly_usd":round(node_cost,2),"source":"Azure Published Pricing"}


# ── Analytics ─────────────────────────────────────────────────────────────────
def get_synapse_price(tb: float = 1.0) -> dict:
    # Synapse Analytics: $5/TB scanned
    return {"service":"Azure Synapse Analytics","tb_processed":tb,"monthly_usd":round(tb*5.0,2),"source":"Azure Published Pricing"}


# ── Messaging ─────────────────────────────────────────────────────────────────
def get_servicebus_price(messages: int = 1000000) -> dict:
    # Basic tier: $0.05 per million operations
    cost = (messages / 1000000) * 0.05
    return {"service":"Azure Service Bus (Basic)","messages":messages,"monthly_usd":round(cost,2),"source":"Azure Published Pricing"}


# ── Cache ─────────────────────────────────────────────────────────────────────
def get_redis_cache_price() -> dict:
    # C1 Basic (1GB): $0.055/hr
    return {"service":"Azure Cache for Redis (C1 Basic)","hourly_usd":0.055,"monthly_usd":round(0.055*HOURS,2),"source":"Azure Published Pricing"}


# ── Aggregator ────────────────────────────────────────────────────────────────
def get_azure_total(compute_tier: str, storage_gb: int,
                    selected: list = None, extra: dict = None) -> dict:
    if selected is None: selected = ["compute","database","storage","cdn"]
    if extra is None:    extra    = {}

    sku_map = {"small":"B2s","medium":"D2s v3","large":"D4s v3","xlarge":"D8s v3"}
    sku     = sku_map.get(compute_tier, "D2s v3")
    result  = {"provider":"Azure","region":REGION}
    total   = 0.0

    fetchers = {
        "compute":    lambda: get_vm_price(sku),
        "database":   lambda: get_db_price(),
        "storage":    lambda: get_blob_price(storage_gb),
        "cdn":        lambda: get_cdn_price(),
        "ai_ml":      lambda: get_openai_price(extra.get("ai_ml_requests", 100000)),
        "serverless": lambda: get_functions_price(extra.get("lambda_invocations", 1000000)),
        "kubernetes": lambda: get_aks_price(extra.get("k8s_nodes", 3)),
        "analytics":  lambda: get_synapse_price(extra.get("analytics_tb", 1.0)),
        "messaging":  lambda: get_servicebus_price(extra.get("messages", 1000000)),
        "cache":      lambda: get_redis_cache_price(),
    }

    for svc in selected:
        if svc in fetchers:
            try:
                data = fetchers[svc]()
                result[svc] = data
                total += data.get("monthly_usd", 0)
            except Exception as e:
                logger.error(f"Azure {svc} error: {e}")

    result["total_monthly_usd"] = round(total, 2)
    return result
