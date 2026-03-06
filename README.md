# ☁️ Cloud Cost Optimizer v2

## Setup
1. `cd backend && cp .env.example .env` — fill AWS keys only
2. `pip install -r requirements.txt`
3. `uvicorn main:app --reload --port 8000`
4. `cd ../frontend && python -m http.server 3000`
5. Open http://localhost:3000

## What's New in v2
- 10 service categories: Compute, DB, Storage, CDN, AI/ML, Serverless, K8s, Analytics, Messaging, Cache
- AWS: Bedrock, SageMaker, Lambda, EKS, Redshift, Athena, SQS, ElastiCache
- Azure: OpenAI, ML Studio, Functions, AKS, Synapse, Service Bus, Redis Cache
- GCP: Vertex AI, Cloud Functions, GKE, BigQuery, Pub/Sub, Memorystore
- DigitalOcean: Droplets, Functions, DOKS
- Oracle Cloud: Compute, DB, Storage, CDN
- AI gives BOTH single-cloud + multi-cloud recommendations
- Well-Architected Framework analysis
- Service-by-service winner comparison
>>>>>>>>>>>>>>>>>>

To run:
powershellcd backend
cp .env.example .env   # fill AWS keys
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
Then in another terminal:
powershellcd "C:\...\v2\frontend"
python -m http.server 3000
>>>>>>>>>>>>>


**create .env file also :**
....................................................................... start ....................................................................................
# ============================================================
# Cloud Cost Optimizer — Environment Configuration
# 1. Copy this file:  cp .env.example .env
# 2. Fill in your values below
# 3. Never commit .env to git
# ============================================================

# ── AWS ──────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID="your key"
AWS_SECRET_ACCESS_KEY="your key "
AWS_DEFAULT_REGION=ap-south-1

# ── Amazon Bedrock (AI reasoning) ────────────────────────────
BEDROCK_REGION=ap-south-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0

# ── Azure (no auth needed — public API) ──────────────────────
AZURE_REGION=southindia

# ── GCP (no auth needed — public catalog) ────────────────────
GCP_REGION=asia-south1

# ── DigitalOcean (no auth needed) ────────────────────────────
DO_REGION=blr1

# ── App ──────────────────────────────────────────────────────
APP_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:5678


..........................................................  end ............................................................................
