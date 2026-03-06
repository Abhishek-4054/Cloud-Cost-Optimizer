"""
AWS Pricing — Live from AWS Pricing API + published rates for new services.
Services: Compute, DB, Storage, CDN, AI/ML (Bedrock+SageMaker),
          Serverless (Lambda), Kubernetes (EKS), Analytics (Redshift+Athena),
          Messaging (SQS+SNS), Cache (ElastiCache)
"""
import boto3
import json
import logging
from config.settings import AWSConfig

logger     = logging.getLogger(__name__)
HOURS      = 730
REGION     = AWSConfig.REGION


def _client():
    return boto3.client(
        "pricing", region_name=AWSConfig.PRICING_REGION,
        aws_access_key_id=AWSConfig.ACCESS_KEY_ID,
        aws_secret_access_key=AWSConfig.SECRET_ACCESS_KEY,
    )


def get_ec2_price(instance_type: str) -> dict:
    c        = _client()
    location = AWSConfig.get_location()
    resp     = c.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type":"TERM_MATCH","Field":"instanceType",   "Value":instance_type},
            {"Type":"TERM_MATCH","Field":"location",       "Value":location},
            {"Type":"TERM_MATCH","Field":"operatingSystem","Value":"Linux"},
            {"Type":"TERM_MATCH","Field":"tenancy",        "Value":"Shared"},
            {"Type":"TERM_MATCH","Field":"preInstalledSw", "Value":"NA"},
            {"Type":"TERM_MATCH","Field":"capacitystatus", "Value":"Used"},
        ], MaxResults=1
    )
    pl = resp.get("PriceList", [])
    if not pl:
        raise ValueError(f"No EC2 price for {instance_type}")
    prod = json.loads(pl[0])
    for term in prod["terms"]["OnDemand"].values():
        for dim in term["priceDimensions"].values():
            h = float(dim["pricePerUnit"]["USD"])
            return {"service":f"EC2 {instance_type}","instance":instance_type,"hourly_usd":round(h,6),"monthly_usd":round(h*HOURS,2),"source":"AWS Pricing API (live)"}
    raise ValueError("Parse error EC2")


def get_rds_price(instance: str = "db.t3.medium", engine: str = "PostgreSQL") -> dict:
    c    = _client()
    resp = c.get_products(
        ServiceCode="AmazonRDS",
        Filters=[
            {"Type":"TERM_MATCH","Field":"instanceType",     "Value":instance},
            {"Type":"TERM_MATCH","Field":"location",         "Value":AWSConfig.get_location()},
            {"Type":"TERM_MATCH","Field":"databaseEngine",   "Value":engine},
            {"Type":"TERM_MATCH","Field":"deploymentOption", "Value":"Single-AZ"},
        ], MaxResults=1
    )
    pl = resp.get("PriceList", [])
    if not pl:
        raise ValueError(f"No RDS price for {instance}")
    prod = json.loads(pl[0])
    for term in prod["terms"]["OnDemand"].values():
        for dim in term["priceDimensions"].values():
            h = float(dim["pricePerUnit"]["USD"])
            return {"service":f"RDS {engine} {instance}","instance":instance,"engine":engine,"hourly_usd":round(h,6),"monthly_usd":round(h*HOURS,2),"source":"AWS Pricing API (live)"}
    raise ValueError("Parse error RDS")


def get_s3_price(storage_gb: int) -> dict:
    # S3 Standard: $0.023/GB in ap-south-1
    per_gb = 0.023
    return {"service":"Amazon S3 Standard","storage_gb":storage_gb,"per_gb_usd":per_gb,"monthly_usd":round(per_gb*storage_gb,2),"source":"AWS Published Pricing"}


def get_cloudfront_price() -> dict:
    # $0.14/GB egress APAC, estimate 50GB/mo
    return {"service":"Amazon CloudFront","transfer_gb":50,"monthly_usd":round(50*0.14,2),"source":"AWS Published Pricing"}


# ── AI/ML ─────────────────────────────────────────────────────────────────────
def get_bedrock_price(requests: int = 100000) -> dict:
    # Claude Haiku: $0.00025/1K input tokens, $0.00125/1K output tokens
    # Assume avg 500 input + 200 output tokens per request
    input_cost  = (requests * 500 / 1000) * 0.00025
    output_cost = (requests * 200 / 1000) * 0.00125
    total       = input_cost + output_cost
    return {"service":"Amazon Bedrock (Claude Haiku)","requests":requests,"monthly_usd":round(total,2),"source":"AWS Published Pricing"}


def get_sagemaker_price(instance: str = "ml.t3.medium") -> dict:
    # SageMaker ml.t3.medium: $0.0464/hr
    rates = {"ml.t3.medium":0.0464,"ml.m5.large":0.115,"ml.m5.xlarge":0.230}
    h     = rates.get(instance, 0.0464)
    return {"service":f"SageMaker {instance}","instance":instance,"hourly_usd":h,"monthly_usd":round(h*HOURS,2),"source":"AWS Published Pricing"}


# ── Serverless ────────────────────────────────────────────────────────────────
def get_lambda_price(invocations: int = 1000000) -> dict:
    # First 1M free, then $0.20 per 1M. Duration: 128MB 200ms avg
    billable    = max(0, invocations - 1000000)
    req_cost    = (billable / 1000000) * 0.20
    # GB-seconds: 128MB * 0.2s * invocations
    gb_seconds  = (128/1024) * 0.2 * invocations
    dur_cost    = max(0, gb_seconds - 400000) * 0.0000166667
    total       = req_cost + dur_cost
    return {"service":"AWS Lambda","invocations":invocations,"monthly_usd":round(total,2),"source":"AWS Published Pricing"}


# ── Kubernetes ────────────────────────────────────────────────────────────────
def get_eks_price(nodes: int = 3, node_type: str = "t3.medium") -> dict:
    # EKS cluster: $0.10/hr + worker nodes
    cluster_cost = 0.10 * HOURS
    try:
        node_data = get_ec2_price(node_type)
        node_cost = node_data["monthly_usd"] * nodes
    except:
        node_cost = 36.0 * nodes  # fallback
    total = cluster_cost + node_cost
    return {"service":f"Amazon EKS ({nodes}x {node_type})","nodes":nodes,"monthly_usd":round(total,2),"source":"AWS Pricing API (live)"}


# ── Analytics ─────────────────────────────────────────────────────────────────
def get_redshift_price() -> dict:
    # dc2.large: $0.25/hr
    return {"service":"Amazon Redshift dc2.large","hourly_usd":0.25,"monthly_usd":round(0.25*HOURS,2),"source":"AWS Published Pricing"}


def get_athena_price(tb_scanned: float = 1.0) -> dict:
    # $5.00 per TB scanned
    return {"service":"Amazon Athena","tb_scanned":tb_scanned,"monthly_usd":round(tb_scanned*5.0,2),"source":"AWS Published Pricing"}


# ── Messaging ─────────────────────────────────────────────────────────────────
def get_sqs_price(messages: int = 1000000) -> dict:
    # First 1M free, then $0.40 per million
    billable = max(0, messages - 1000000)
    cost     = (billable / 1000000) * 0.40
    return {"service":"Amazon SQS","messages":messages,"monthly_usd":round(cost,2),"source":"AWS Published Pricing"}


# ── Cache ─────────────────────────────────────────────────────────────────────
def get_elasticache_price(cache_gb: int = 10) -> dict:
    # cache.t3.micro: $0.017/hr
    return {"service":"ElastiCache (Redis t3.micro)","cache_gb":cache_gb,"hourly_usd":0.017,"monthly_usd":round(0.017*HOURS,2),"source":"AWS Published Pricing"}


# ── Aggregator ────────────────────────────────────────────────────────────────
def get_aws_total(compute_tier: str, storage_gb: int, database: str = "PostgreSQL",
                  selected: list = None, extra: dict = None) -> dict:
    if selected is None:
        selected = ["compute","database","storage","cdn"]
    if extra is None:
        extra = {}

    instance_map = {"small":{"ec2":"t3.small","rds":"db.t3.small"},"medium":{"ec2":"t3.medium","rds":"db.t3.medium"},"large":{"ec2":"t3.large","rds":"db.t3.large"},"xlarge":{"ec2":"t3.xlarge","rds":"db.t3.xlarge"}}
    sizes  = instance_map.get(compute_tier, instance_map["medium"])
    result = {"provider":"AWS","region":REGION}
    total  = 0.0

    fetchers = {
        "compute":    lambda: get_ec2_price(sizes["ec2"]),
        "database":   lambda: get_rds_price(sizes["rds"], database),
        "storage":    lambda: get_s3_price(storage_gb),
        "cdn":        lambda: get_cloudfront_price(),
        "ai_ml":      lambda: get_bedrock_price(extra.get("ai_ml_requests", 100000)),
        "serverless": lambda: get_lambda_price(extra.get("lambda_invocations", 1000000)),
        "kubernetes": lambda: get_eks_price(extra.get("k8s_nodes", 3), sizes["ec2"]),
        "analytics":  lambda: get_redshift_price(),
        "messaging":  lambda: get_sqs_price(extra.get("messages", 1000000)),
        "cache":      lambda: get_elasticache_price(extra.get("cache_gb", 10)),
    }

    for svc in selected:
        if svc in fetchers:
            try:
                data = fetchers[svc]()
                result[svc] = data
                total += data.get("monthly_usd", 0)
            except Exception as e:
                logger.error(f"AWS {svc} error: {e}")

    result["total_monthly_usd"] = round(total, 2)
    return result
