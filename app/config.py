import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "CentrAlign AI Operator"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_PATH: str = str(BASE_DIR / "enterprise.db")
    AUTO_REFUND_THRESHOLD: float = 5000.0
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    PLAYWRIGHT_HEADLESS: bool = True
    POLICY_FILE_PATH: str = str(BASE_DIR / "policies" / "refund_policy.md")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
