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