"""
Cloud Cost Optimizer v2 — FastAPI Backend
All service categories: Compute, DB, Storage, CDN, AI/ML,
Serverless, Kubernetes, Analytics, Messaging, Cache.
Live pricing from all providers. AI recommendations via Bedrock Claude.
"""
import logging
import concurrent.futures
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

from config.settings import AppConfig
from pricing.aws import get_aws_total
from pricing.azure import get_azure_total
from pricing.gcp import get_gcp_total
from pricing.digitalocean import get_do_total
from pricing.oracle import get_oci_total
from agents.bedrock_agent import get_ai_recommendation, get_service_recommendation

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cloud Cost Optimizer API v2",
    description="Multi-cloud, multi-service cost comparison with live pricing and AI recommendations",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALL_SERVICES = [
    "compute", "database", "storage", "cdn",
    "ai_ml", "serverless", "kubernetes",
    "analytics", "messaging", "cache"
]


class AppRequirements(BaseModel):
    app_type:          str          = Field(..., example="web app")
    users:             int          = Field(..., example=500, ge=1)
    storage_gb:        int          = Field(..., example=100, ge=1)
    database:          str          = Field(..., example="PostgreSQL")
    region:            str          = Field(..., example="ap-south-1")
    budget_usd:        float        = Field(..., example=500.0, gt=0)
    priorities:        list[str]    = Field(..., example=["cost", "performance"])
    selected_services: list[str]    = Field(
        default=["compute", "database", "storage", "cdn"],
        example=["compute", "database", "storage", "cdn", "ai_ml"]
    )
    # Optional per-service config
    ai_ml_requests_per_month: Optional[int]   = Field(default=100000)
    lambda_invocations:       Optional[int]   = Field(default=1000000)
    k8s_nodes:                Optional[int]   = Field(default=3)
    analytics_tb:             Optional[float] = Field(default=1.0)
    messages_per_month:       Optional[int]   = Field(default=1000000)
    cache_gb:                 Optional[int]   = Field(default=10)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/services")
def list_services():
    """List all supported service categories."""
    return {
        "services": [
            {"id": "compute",    "name": "Compute",              "icon": "💻", "description": "VMs, EC2, Droplets"},
            {"id": "database",   "name": "Database",             "icon": "🗄️", "description": "RDS, Cloud SQL, Cosmos DB"},
            {"id": "storage",    "name": "Object Storage",       "icon": "📦", "description": "S3, Blob, GCS"},
            {"id": "cdn",        "name": "CDN & Networking",     "icon": "🌐", "description": "CloudFront, Azure CDN, Cloud CDN"},
            {"id": "ai_ml",      "name": "AI / ML",              "icon": "🤖", "description": "Bedrock, SageMaker, Vertex AI, Azure OpenAI"},
            {"id": "serverless", "name": "Serverless Functions", "icon": "⚡", "description": "Lambda, Cloud Functions, Azure Functions"},
            {"id": "kubernetes", "name": "Kubernetes",           "icon": "☸️", "description": "EKS, GKE, AKS"},
            {"id": "analytics",  "name": "Analytics & Data",     "icon": "📊", "description": "Redshift, BigQuery, Synapse"},
            {"id": "messaging",  "name": "Messaging & Queues",   "icon": "📨", "description": "SQS/SNS, Pub/Sub, Service Bus"},
            {"id": "cache",      "name": "Cache",                "icon": "⚡", "description": "ElastiCache, Memorystore, Azure Cache"},
        ]
    }


@app.get("/providers")
def list_providers():
    return {
        "providers": [
            {"name": "AWS",          "auth_required": True,  "services": ["compute","database","storage","cdn","ai_ml","serverless","kubernetes","analytics","messaging","cache"]},
            {"name": "Azure",        "auth_required": False, "services": ["compute","database","storage","cdn","ai_ml","serverless","kubernetes","analytics","messaging","cache"]},
            {"name": "GCP",          "auth_required": False, "services": ["compute","database","storage","cdn","ai_ml","serverless","kubernetes","analytics","messaging","cache"]},
            {"name": "DigitalOcean", "auth_required": False, "services": ["compute","database","storage","cdn","serverless","kubernetes"]},
            {"name": "Oracle Cloud", "auth_required": False, "services": ["compute","database","storage","cdn"]},
        ]
    }


@app.post("/compare-costs")
def compare_costs(req: AppRequirements):
    """
    Main endpoint — fetches live pricing for ALL selected service categories
    from all providers in parallel, then calls Bedrock Claude for:
    1. Single-cloud well-architected recommendation
    2. Multi-cloud best-of-breed solution
    """
    tier = _compute_tier(req.users)
    logger.info(f"v2 compare: tier={tier}, services={req.selected_services}")

    extra = {
        "ai_ml_requests":    req.ai_ml_requests_per_month,
        "lambda_invocations": req.lambda_invocations,
        "k8s_nodes":         req.k8s_nodes,
        "analytics_tb":      req.analytics_tb,
        "messages":          req.messages_per_month,
        "cache_gb":          req.cache_gb,
    }

    results = {}
    errors  = {}

    def fetch(name, fn, *args):
        try:
            results[name] = fn(*args)
        except Exception as e:
            logger.error(f"{name} error: {e}")
            errors[name] = str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [
            ex.submit(fetch, "AWS",          get_aws_total,   tier, req.storage_gb, req.database, req.selected_services, extra),
            ex.submit(fetch, "Azure",        get_azure_total, tier, req.storage_gb, req.selected_services, extra),
            ex.submit(fetch, "GCP",          get_gcp_total,   tier, req.storage_gb, req.selected_services, extra),
            ex.submit(fetch, "DigitalOcean", get_do_total,    tier, req.storage_gb, req.selected_services, extra),
            ex.submit(fetch, "Oracle Cloud", get_oci_total,   tier, req.storage_gb, req.selected_services, extra),
        ]
        concurrent.futures.wait(futures)

    if not results:
        raise HTTPException(status_code=503, detail={"message": "All pricing APIs failed", "errors": errors})

    pricing_list = sorted(results.values(), key=lambda x: x["total_monthly_usd"])

    ai_rec = None
    try:
        req_dict = req.dict()
        ai_rec   = get_ai_recommendation(req_dict, pricing_list)
    except Exception as e:
        logger.error(f"Bedrock error: {e}")
        ai_rec = _fallback_recommendation(pricing_list, req)

    return {
        "requirements":      req.dict(),
        "compute_tier":      tier,
        "pricing":           pricing_list,
        "failed_providers":  errors or None,
        "ai_recommendation": ai_rec,
    }


@app.post("/compare-service/{service_category}")
def compare_single_service(service_category: str, req: AppRequirements):
    """Get focused recommendation for a single service category."""
    if service_category not in ALL_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service_category}")

    tier  = _compute_tier(req.users)
    extra = {"ai_ml_requests": req.ai_ml_requests_per_month, "cache_gb": req.cache_gb}

    results = {}
    def fetch(name, fn, *args):
        try:
            results[name] = fn(*args)
        except Exception as e:
            errors[name] = str(e)

    errors = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [
            ex.submit(fetch, "AWS",          get_aws_total,   tier, req.storage_gb, req.database, [service_category], extra),
            ex.submit(fetch, "Azure",        get_azure_total, tier, req.storage_gb, [service_category], extra),
            ex.submit(fetch, "GCP",          get_gcp_total,   tier, req.storage_gb, [service_category], extra),
            ex.submit(fetch, "DigitalOcean", get_do_total,    tier, req.storage_gb, [service_category], extra),
            ex.submit(fetch, "Oracle Cloud", get_oci_total,   tier, req.storage_gb, [service_category], extra),
        ]
        concurrent.futures.wait(futures)

    providers = list(results.values())
    ai_insight = get_service_recommendation(service_category, providers)

    return {
        "service":    service_category,
        "providers":  sorted(providers, key=lambda x: x.get(service_category, {}).get("monthly_usd", 9999)),
        "ai_insight": ai_insight,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_tier(users: int) -> str:
    if users < 100:   return "small"
    if users < 1000:  return "medium"
    if users < 10000: return "large"
    return "xlarge"


def _fallback_recommendation(pricing_list: list, req: AppRequirements) -> dict:
    best   = pricing_list[0]
    second = pricing_list[1] if len(pricing_list) > 1 else pricing_list[0]

    service_breakdown = []
    for svc in req.selected_services:
        candidates = [p for p in pricing_list if p.get(svc) and p[svc].get("monthly_usd", 0) > 0]
        if candidates:
            cheapest = min(candidates, key=lambda x: x[svc]["monthly_usd"])
            service_breakdown.append({
                "category":     svc,
                "provider":     cheapest["provider"],
                "service":      cheapest[svc].get("service", svc),
                "monthly_cost": cheapest[svc]["monthly_usd"],
                "why_best":     "Lowest cost for this service category"
            })

    multi_total = sum(s["monthly_cost"] for s in service_breakdown)

    return {
        "summary": f"{best['provider']} is the most cost-effective at ${best['total_monthly_usd']}/month. Bedrock AI unavailable — cost-based fallback shown.",
        "budget_status": "within_budget" if best["total_monthly_usd"] <= req.budget_usd else "over_budget",
        "budget_gap": round(best["total_monthly_usd"] - req.budget_usd, 2),
        "best_single_cloud": {
            "provider": best["provider"],
            "monthly_cost": best["total_monthly_usd"],
            "reason": f"Lowest total cost across all selected services.",
            "architecture_pattern": "Cost-optimized deployment",
            "services": {k: best.get(k, {}).get("service") for k in ALL_SERVICES},
            "well_architected": {
                "operational_excellence": "Use managed services to reduce ops overhead.",
                "security":               "Enable IAM least-privilege and encryption at rest.",
                "reliability":            "Deploy across multiple availability zones.",
                "performance":            "Use auto-scaling and CDN for performance.",
                "cost_optimization":      "Use reserved instances for 30-40% savings."
            }
        },
        "second_best_single_cloud": {
            "provider": second["provider"],
            "monthly_cost": second["total_monthly_usd"],
            "reason": "Second lowest total cost."
        },
        "multi_cloud_solution": {
            "total_monthly_cost": round(multi_total, 2),
            "strategy": "Best-of-breed: cheapest provider per service.",
            "service_breakdown": service_breakdown,
            "benefits": ["Maximum cost savings", "Avoid vendor lock-in", "Best tool per job"],
            "risks":    ["Operational complexity", "Data egress costs between clouds"]
        },
        "service_winners": [],
        "optimization_tips": [
            "Use reserved instances for 30-40% compute savings",
            "Enable auto-scaling to right-size workloads",
            "Use CDN to offload static assets",
            "Right-size your database — most teams over-provision 2x"
        ],
        "warnings": ["AI recommendation unavailable — cost-based fallback shown"]
    }
