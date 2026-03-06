"""
Amazon Bedrock Agent — Claude-powered multi-service architecture recommendation.
Handles all service types: Compute, DB, Storage, AI/ML, Serverless,
Kubernetes, Analytics, Messaging, Cache, CDN.
Returns BOTH single-cloud well-architected + multi-cloud solutions.
"""
import boto3
import json
import logging
from config.settings import AWSConfig, BedrockConfig

logger = logging.getLogger(__name__)


def _call_bedrock(prompt: str, max_tokens: int = None) -> str:
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=BedrockConfig.REGION,
        aws_access_key_id=AWSConfig.ACCESS_KEY_ID,
        aws_secret_access_key=AWSConfig.SECRET_ACCESS_KEY,
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens or BedrockConfig.MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = client.invoke_model(
        modelId=BedrockConfig.MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"].strip()


def _parse_json(text: str) -> dict:
    """Safely parse JSON from Claude response, stripping markdown fences."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    return json.loads(text)


def get_ai_recommendation(requirements: dict, pricing: list) -> dict:
    """
    Full multi-service recommendation:
    - Single-cloud well-architected solution
    - Multi-cloud best-of-breed solution
    - Per-service winner analysis
    """

    # ── Build rich pricing summary ────────────────────────────
    ALL_SERVICES = [
        "compute", "database", "storage", "cdn",
        "ai_ml", "serverless", "kubernetes",
        "analytics", "messaging", "cache"
    ]

    pricing_summary = []
    for p in pricing:
        lines = [f"\n### {p['provider']} | TOTAL: ${p['total_monthly_usd']}/month"]
        for key in ALL_SERVICES:
            svc = p.get(key)
            if svc and svc.get("monthly_usd", 0) > 0:
                name = svc.get("service", key)
                cost = svc.get("monthly_usd", 0)
                src  = "🟢 live" if "live" in svc.get("source","").lower() else "📄 published"
                lines.append(f"  {key.upper():12} → {name} | ${cost}/mo | {src}")
        pricing_summary.append("\n".join(lines))

    pricing_text     = "\n".join(pricing_summary)
    selected         = requirements.get("selected_services", ALL_SERVICES)
    selected_str     = ", ".join(selected)
    priorities_str   = ", ".join(requirements.get("priorities", ["cost"]))
    providers_listed = ", ".join([p["provider"] for p in pricing])

    prompt = f"""You are a Principal Cloud Architect and FinOps expert (15+ years).
You specialize in AWS, Azure, GCP, DigitalOcean, and Oracle Cloud.

A client needs TWO architecture recommendations:
1. A single-cloud "Well-Architected" solution (best single provider)
2. A multi-cloud strategy (best provider per service category)

All pricing below is LIVE data from official provider APIs.

## Client Requirements
- App Type:      {requirements.get('app_type', 'web app')}
- Users:         {requirements.get('users', 500)} concurrent
- Storage:       {requirements.get('storage_gb', 100)} GB
- Database:      {requirements.get('database', 'PostgreSQL')}
- Region:        {requirements.get('region', 'ap-south-1')}
- Budget:        ${requirements.get('budget_usd', 500)}/month
- Priorities:    {priorities_str}
- Services Needed: {selected_str}

## Live Pricing Data
{pricing_text}

## Instructions
Return ONLY a valid JSON object with this EXACT structure.
Use real service names (e.g. "AWS Lambda", "GCP Vertex AI", "Azure OpenAI").
For unused services set value to null.

{{
  "summary": "<3-4 sentence executive summary>",
  "budget_status": "<within_budget|over_budget|well_within_budget>",
  "budget_gap": <best_total - budget_usd as number>,

  "best_single_cloud": {{
    "provider": "<provider>",
    "monthly_cost": <number>,
    "reason": "<2-3 sentences>",
    "architecture_pattern": "<e.g. 3-tier containerized app with managed DB>",
    "services": {{
      "compute":    "<service name + spec or null>",
      "database":   "<service name + spec or null>",
      "storage":    "<service name or null>",
      "cdn":        "<service name or null>",
      "ai_ml":      "<service name or null>",
      "serverless": "<service name or null>",
      "kubernetes": "<service name or null>",
      "analytics":  "<service name or null>",
      "messaging":  "<service name or null>",
      "cache":      "<service name or null>"
    }},
    "well_architected": {{
      "operational_excellence": "<one sentence>",
      "security":               "<one sentence>",
      "reliability":            "<one sentence>",
      "performance":            "<one sentence>",
      "cost_optimization":      "<one sentence>"
    }}
  }},

  "second_best_single_cloud": {{
    "provider":     "<provider>",
    "monthly_cost": <number>,
    "reason":       "<1-2 sentences>"
  }},

  "multi_cloud_solution": {{
    "total_monthly_cost": <number>,
    "strategy": "<2-3 sentences describing approach>",
    "service_breakdown": [
      {{
        "category":       "<service category>",
        "provider":       "<chosen provider>",
        "service":        "<specific service name>",
        "monthly_cost":   <number>,
        "why_best":       "<one sentence reason>"
      }}
    ],
    "benefits": ["<benefit 1>", "<benefit 2>", "<benefit 3>"],
    "risks":    ["<risk 1>", "<risk 2>"]
  }},

  "service_winners": [
    {{
      "category":     "<service category>",
      "winner":       "<provider>",
      "winner_cost":  <number>,
      "runner_up":    "<provider>",
      "insight":      "<one sentence>"
    }}
  ],

  "optimization_tips": [
    "<specific actionable tip 1>",
    "<specific actionable tip 2>",
    "<specific actionable tip 3>",
    "<specific actionable tip 4>"
  ],

  "warnings": ["<real concern 1>", "<real concern 2>"]
}}

Priority rules:
- "cost" → weight price very heavily, recommend cheapest viable option
- "reliability" → favor AWS/Azure, mention SLAs
- "performance" → favor GCP for AI/ML, AWS for compute, note latency
- "security" → mention compliance, encryption, IAM best practices
- For AI/ML: compare Bedrock vs SageMaker vs Vertex AI vs Azure OpenAI specifically
- Return ONLY valid JSON. No markdown. No extra text."""

    try:
        text   = _call_bedrock(prompt)
        result = _parse_json(text)
        return result
    except Exception as e:
        logger.error(f"Bedrock recommendation error: {e}")
        best   = pricing[0]
        second = pricing[1] if len(pricing) > 1 else pricing[0]
        # Build fallback multi-cloud from cheapest per service
        service_breakdown = []
        for svc in selected:
            cheapest = min(
                [p for p in pricing if p.get(svc)],
                key=lambda x: x.get(svc, {}).get("monthly_usd", 9999),
                default=None
            )
            if cheapest and cheapest.get(svc):
                service_breakdown.append({
                    "category":     svc,
                    "provider":     cheapest["provider"],
                    "service":      cheapest[svc].get("service", svc),
                    "monthly_cost": cheapest[svc].get("monthly_usd", 0),
                    "why_best":     "Lowest cost for this service category"
                })

        multi_total = sum(s["monthly_cost"] for s in service_breakdown)

        return {
            "summary": f"{best['provider']} is the most cost-effective single provider at ${best['total_monthly_usd']}/month. AI recommendation temporarily unavailable — showing cost-based analysis.",
            "budget_status": "within_budget" if best["total_monthly_usd"] <= requirements.get("budget_usd", 9999) else "over_budget",
            "budget_gap": round(best["total_monthly_usd"] - requirements.get("budget_usd", 0), 2),
            "best_single_cloud": {
                "provider":           best["provider"],
                "monthly_cost":       best["total_monthly_usd"],
                "reason":             f"Lowest total cost at ${best['total_monthly_usd']}/month across all selected services.",
                "architecture_pattern": "Cost-optimized single-cloud deployment",
                "services":           {k: best.get(k, {}).get("service") for k in ALL_SERVICES},
                "well_architected": {
                    "operational_excellence": "Use managed services to reduce operational overhead.",
                    "security":               "Enable IAM least-privilege and encrypt data at rest and in transit.",
                    "reliability":            "Deploy across multiple availability zones for high availability.",
                    "performance":            "Use auto-scaling and CDN for optimal response times.",
                    "cost_optimization":      "Use reserved instances and right-sizing to reduce costs 30-40%."
                }
            },
            "second_best_single_cloud": {
                "provider":     second["provider"],
                "monthly_cost": second["total_monthly_usd"],
                "reason":       "Second lowest total cost option."
            },
            "multi_cloud_solution": {
                "total_monthly_cost": round(multi_total, 2),
                "strategy":           "Best-of-breed approach selecting the cheapest provider per service.",
                "service_breakdown":  service_breakdown,
                "benefits":           ["Cost savings per service", "Avoid vendor lock-in", "Use best tool for each job"],
                "risks":              ["Increased operational complexity", "Data transfer costs between providers"]
            },
            "service_winners": [],
            "optimization_tips": [
                "Use reserved/committed instances for 30-40% compute savings",
                "Enable auto-scaling to avoid over-provisioning",
                "Use CDN to offload 60-80% of static asset traffic",
                "Right-size databases — most teams over-provision by 2x"
            ],
            "warnings": ["AI recommendation unavailable — showing cost-based fallback"]
        }


def get_service_recommendation(service_category: str, providers_data: list) -> dict:
    """Focused single-service comparison across providers."""
    pricing_text = "\n".join([
        f"- {p['provider']}: ${p.get(service_category, {}).get('monthly_usd', 'N/A')}/mo "
        f"({p.get(service_category, {}).get('service', 'N/A')})"
        for p in providers_data if p.get(service_category)
    ])

    prompt = f"""Compare {service_category.upper()} services across cloud providers.

Pricing:
{pricing_text}

Return JSON:
{{
  "best_provider": "<name>",
  "best_service":  "<specific service>",
  "reason":        "<2-3 sentences>",
  "use_cases":     ["<use case 1>", "<use case 2>"],
  "avoid_if":      "<when NOT to use this>"
}}

Return ONLY valid JSON."""

    try:
        text = _call_bedrock(prompt, max_tokens=600)
        return _parse_json(text)
    except Exception as e:
        logger.error(f"Service recommendation error: {e}")
        return {"best_provider": "N/A", "reason": str(e), "use_cases": [], "avoid_if": "N/A"}
