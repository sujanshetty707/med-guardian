import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "Med-Guardian"
    VERSION: str = "0.1.0"
    
    # Seeds
    ORCHESTRATOR_SEED: str = os.getenv("ORCHESTRATOR_SEED", "med-guardian-orchestrator-seed-default")
    SCHEDULE_SEED: str = os.getenv("SCHEDULE_SEED", "med-guardian-schedule-seed-default")
    SAFETY_SEED: str = os.getenv("SAFETY_SEED", "med-guardian-safety-seed-default")
    PHARMACY_SEED: str = os.getenv("PHARMACY_SEED", "med-guardian-pharmacy-seed-default")
    CAREGIVER_SEED: str = os.getenv("CAREGIVER_SEED", "med-guardian-caregiver-seed-default")
    
    # Ports (for local agents)
    ORCHESTRATOR_PORT: int = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    SCHEDULE_PORT: int = int(os.getenv("SCHEDULE_PORT", "8001"))
    SAFETY_PORT: int = int(os.getenv("SAFETY_PORT", "8002"))
    PHARMACY_PORT: int = int(os.getenv("PHARMACY_PORT", "8003"))
    CAREGIVER_PORT: int = int(os.getenv("CAREGIVER_PORT", "8004"))
    
    # API Keys & Endpoints
    AGENTVERSE_API_KEY: str = os.getenv("AGENTVERSE_API_KEY", "")
    ASI1_API_KEY: str = os.getenv("ASI1_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.asi1.ai/v1")
    
    # DB
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'medguardian.db'}")
    
    # Notifications
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_DEFAULT_CHAT_ID: str = os.getenv("TELEGRAM_DEFAULT_CHAT_ID", "")
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM: str = os.getenv("TWILIO_FROM", "")
    
    # Logic configs
    PRICE_PROVIDERS: list[str] = [p.strip() for p in os.getenv("PRICE_PROVIDERS", "nadac,mock_partner").split(",") if p.strip()]
    FAULT_INJECT: str = os.getenv("FAULT_INJECT", "")  # e.g. "pricing_timeout", "openfda_error"
    REMINDER_GRACE_MINUTES: int = int(os.getenv("REMINDER_GRACE_MINUTES", "20"))
    MISSED_AFTER_MINUTES: int = int(os.getenv("MISSED_AFTER_MINUTES", "40"))
    REFILL_THRESHOLD_DAYS: int = int(os.getenv("REFILL_THRESHOLD_DAYS", "7"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
