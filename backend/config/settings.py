import os
from dotenv import load_dotenv
load_dotenv(override=True)

class AWSConfig:
    ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID", "")
    SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    REGION            = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    PRICING_REGION    = "us-east-1"
    REGION_LOCATION_MAP = {
        "us-east-1":      "US East (N. Virginia)",
        "us-west-2":      "US West (Oregon)",
        "eu-west-1":      "Europe (Ireland)",
        "ap-south-1":     "Asia Pacific (Mumbai)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
        "ap-northeast-1": "Asia Pacific (Tokyo)",
    }
    @classmethod
    def get_location(cls): return cls.REGION_LOCATION_MAP.get(cls.REGION, "Asia Pacific (Mumbai)")

class BedrockConfig:
    REGION     = os.getenv("BEDROCK_REGION", "us-east-1")
    MODEL_ID   = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    MAX_TOKENS = 3000

class AzureConfig:
    PRICING_URL = "https://prices.azure.microsoft.com/api/retail/prices"
    REGION      = os.getenv("AZURE_REGION", "southindia")
    API_VERSION = "2023-01-01-preview"

class GCPConfig:
    REGION = os.getenv("GCP_REGION", "asia-south1")

class DOConfig:
    REGION = os.getenv("DO_REGION", "blr1")

class AppConfig:
    PORT         = int(os.getenv("APP_PORT", 8000))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS","http://localhost:3000,http://localhost:5173").split(",")
