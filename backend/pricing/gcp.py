"""
GCP Pricing — via GCP public pricing JSON (no auth needed).
Services: Compute, DB, Storage, CDN, AI/ML (Vertex AI),
          Serverless (Cloud Functions), Kubernetes (GKE),
          Analytics (BigQuery), Messaging (Pub/Sub), Cache (Memorystore)
"""
import httpx
import logging
from config.settings import GCPConfig

logger  = logging.getLogger(__name__)
HOURS   = 730
REGION  = GCPConfig.REGION
GCP_PRICELIST_URL = "https://cloudpricingcalculator.appspot.com/static/data/pricelist.json"

_pricelist_cache = None

def _get_pricelist() -> dict:
    global _pricelist_cache
    if _pricelist_cache is None:
        r = httpx.get(GCP_PRICELIST_URL, timeout=20)
        r.raise_for_status()
        _pricelist_cache = r.json().get("gcp_price_list", {})
    return _pricelist_cache


def _price(key: str, region_key: str = "asia") -> float:
    pl  = _get_pricelist()
    sku = pl.get(key, {})
    return float(
        sku.get(region_key, {}).get("price", 0) or
        sku.get("us", {}).get("price", 0) or
        sku.get("price", 0) or 0
    )


def get_compute_price(machine_type: str = "e2-medium") -> dict:
    key_map = {
        "e2-small":      "CP-COMPUTEENGINE-VMIMAGE-E2-SMALL",
        "e2-medium":     "CP-COMPUTEENGINE-VMIMAGE-E2-MEDIUM",
        "e2-standard-2": "CP-COMPUTEENGINE-VMIMAGE-E2-STANDARD-2",
        "e2-standard-4": "CP-COMPUTEENGINE-VMIMAGE-E2-STANDARD-4",
    }
    key    = key_map.get(machine_type, "CP-COMPUTEENGINE-VMIMAGE-E2-MEDIUM")
    hourly = _price(key)
    if not hourly:
        raise ValueError(f"No GCP compute price for {machine_type}")
    return {"service":f"GCP Compute Engine {machine_type}","machine":machine_type,"hourly_usd":round(hourly,6),"monthly_usd":round(hourly*HOURS,2),"source":"GCP Public Pricelist (live)"}


def get_cloudsql_price() -> dict:
    keys   = ["CP-CLOUDSQL-POSTGRESQL-ZONAL-CORE","CP-CLOUDSQL-CORE"]
    hourly = 0.0
    for key in keys:
        hourly = _price(key)
        if hourly: break
    if not hourly:
        raise ValueError("No GCP Cloud SQL price")
    return {"service":"Cloud SQL PostgreSQL (1 vCPU)","hourly_usd":round(hourly,6),"monthly_usd":round(hourly*HOURS,2),"source":"GCP Public Pricelist (live)"}


def get_gcs_price(storage_gb: int) -> dict:
    pgb = _price("CP-BIGSTORE-STORAGE")
    if not pgb: raise ValueError("No GCS price")
    return {"service":"Google Cloud Storage Standard","storage_gb":storage_gb,"per_gb_usd":round(pgb,6),"monthly_usd":round(pgb*storage_gb,2),"source":"GCP Public Pricelist (live)"}


def get_cdn_price() -> dict:
    pgb = _price("CP-INTERNETEGRESS-APAC") or 0.12
    return {"service":"Cloud CDN","transfer_gb":50,"monthly_usd":round(pgb*50,2),"source":"GCP Public Pricelist (live)"}


# ── AI/ML ─────────────────────────────────────────────────────────────────────
def get_vertex_ai_price(requests: int = 100000) -> dict:
    # Vertex AI Gemini 1.0 Pro: $0.00025/1K input tokens, $0.0005/1K output
    # Avg 500 input + 200 output per request
    input_cost  = (requests * 500 / 1000) * 0.00025
    output_cost = (requests * 200 / 1000) * 0.0005
    total       = input_cost + output_cost
    return {"service":"GCP Vertex AI (Gemini 1.0 Pro)","requests":requests,"monthly_usd":round(total,2),"source":"GCP Published Pricing"}


# ── Serverless ────────────────────────────────────────────────────────────────
def get_cloud_functions_price(invocations: int = 1000000) -> dict:
    # First 2M free, $0.40/million after
    billable = max(0, invocations - 2000000)
    cost     = (billable / 1000000) * 0.40
    return {"service":"GCP Cloud Functions","invocations":invocations,"monthly_usd":round(cost,2),"source":"GCP Published Pricing"}


# ── Kubernetes ────────────────────────────────────────────────────────────────
def get_gke_price(nodes: int = 3) -> dict:
    # GKE Autopilot: $0.10/vCPU/hr + $0.01/GB RAM/hr
    # Or Standard: $0.10/cluster/hr + node costs
    cluster_cost = 0.10 * HOURS
    # e2-medium nodes: ~$0.034/hr each
    node_cost    = 0.034 * HOURS * nodes
    total        = cluster_cost + node_cost
    return {"service":f"GKE Standard ({nodes}x e2-medium)","nodes":nodes,"monthly_usd":round(total,2),"source":"GCP Published Pricing"}


# ── Analytics ─────────────────────────────────────────────────────────────────
def get_bigquery_price(tb: float = 1.0) -> dict:
    # BigQuery on-demand: $5/TB queried. Storage: $0.02/GB
    query_cost   = tb * 5.0
    storage_cost = tb * 1024 * 0.02  # TB → GB
    return {"service":"Google BigQuery","tb_processed":tb,"monthly_usd":round(query_cost,2),"source":"GCP Published Pricing"}


# ── Messaging ─────────────────────────────────────────────────────────────────
def get_pubsub_price(messages: int = 1000000) -> dict:
    # First 10GB/month free (~10M messages), $0.04/GB after
    # Avg message 1KB
    gb        = (messages * 1024) / (1024**3)
    billable  = max(0, gb - 10)
    cost      = billable * 0.04
    return {"service":"GCP Pub/Sub","messages":messages,"monthly_usd":round(cost,2),"source":"GCP Published Pricing"}


# ── Cache ─────────────────────────────────────────────────────────────────────
def get_memorystore_price(cache_gb: int = 10) -> dict:
    # Redis Basic M1: $0.049/GB/hr
    hourly = 0.049 * cache_gb
    return {"service":f"Cloud Memorystore Redis ({cache_gb}GB)","cache_gb":cache_gb,"hourly_usd":round(hourly,6),"monthly_usd":round(hourly*HOURS,2),"source":"GCP Published Pricing"}


# ── Aggregator ────────────────────────────────────────────────────────────────
def get_gcp_total(compute_tier: str, storage_gb: int,
                  selected: list = None, extra: dict = None) -> dict:
    if selected is None: selected = ["compute","database","storage","cdn"]
    if extra is None:    extra    = {}

    machine_map = {"small":"e2-small","medium":"e2-medium","large":"e2-standard-2","xlarge":"e2-standard-4"}
    machine     = machine_map.get(compute_tier, "e2-medium")
    result      = {"provider":"GCP","region":REGION}
    total       = 0.0

    fetchers = {
        "compute":    lambda: get_compute_price(machine),
        "database":   lambda: get_cloudsql_price(),
        "storage":    lambda: get_gcs_price(storage_gb),
        "cdn":        lambda: get_cdn_price(),
        "ai_ml":      lambda: get_vertex_ai_price(extra.get("ai_ml_requests", 100000)),
        "serverless": lambda: get_cloud_functions_price(extra.get("lambda_invocations", 1000000)),
        "kubernetes": lambda: get_gke_price(extra.get("k8s_nodes", 3)),
        "analytics":  lambda: get_bigquery_price(extra.get("analytics_tb", 1.0)),
        "messaging":  lambda: get_pubsub_price(extra.get("messages", 1000000)),
        "cache":      lambda: get_memorystore_price(extra.get("cache_gb", 10)),
    }

    for svc in selected:
        if svc in fetchers:
            try:
                data = fetchers[svc]()
                result[svc] = data
                total += data.get("monthly_usd", 0)
            except Exception as e:
                logger.error(f"GCP {svc} error: {e}")

    result["total_monthly_usd"] = round(total, 2)
    return result
