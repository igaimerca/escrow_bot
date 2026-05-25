"""
Configuration - set your values in .env file
"""
import os
from dotenv import load_dotenv

load_dotenv()


def build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    pg_user = os.getenv("POSTGRES_USER", "postgres")
    pg_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = os.getenv("POSTGRES_PORT", "5432")
    pg_db = os.getenv("POSTGRES_DB", "trusthold_escrow")
    return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"


BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))
ADMIN_CONTACT_USERNAME = os.getenv("ADMIN_CONTACT_USERNAME", "@BruceWilliamsx")
DATABASE_URL = build_database_url()
BOT_NAME = "TrustHold_EscrowBot"

ESCROW_FEE_FLAT = float(os.getenv("ESCROW_FEE_FLAT", "5.0"))
ESCROW_FEE_HIGH_PERCENT = float(os.getenv("ESCROW_FEE_HIGH_PERCENT", "5.0"))
ESCROW_FEE_THRESHOLD = float(os.getenv("ESCROW_FEE_THRESHOLD", "100"))


def calculate_escrow_fee(amount: float) -> float:
    if amount <= ESCROW_FEE_THRESHOLD:
        return round(ESCROW_FEE_FLAT, 2)
    return round(amount * ESCROW_FEE_HIGH_PERCENT / 100, 2)


def get_escrow_fee_label(amount: float) -> str:
    if amount <= ESCROW_FEE_THRESHOLD:
        return f"${ESCROW_FEE_FLAT:.2f} flat"
    return f"{ESCROW_FEE_HIGH_PERCENT:.1f}%"
