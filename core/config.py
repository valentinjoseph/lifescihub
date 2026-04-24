import os

from dotenv import load_dotenv

load_dotenv("infra/.env")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
API_TITLE = os.getenv("API_TITLE", "Life Science Watch API")
API_VERSION = os.getenv("API_VERSION", "0.1.0")
API_ENABLE_DOCS = env_bool("API_ENABLE_DOCS", True)
API_REQUIRE_AUTH = env_bool("API_REQUIRE_AUTH", True)
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", os.getenv("LSW_RUN_TOKEN"))
VIEWER_ACCESS_TOKEN = os.getenv("VIEWER_ACCESS_TOKEN")
VIEWER_USERNAME = os.getenv("VIEWER_USERNAME", "guest")
VIEWER_PASSWORD_HASH = os.getenv("VIEWER_PASSWORD_HASH")
REQUEST_GUEST_USERNAME = os.getenv("REQUEST_GUEST_USERNAME", os.getenv("GUEST_USERNAME", VIEWER_USERNAME or "guest"))
REQUEST_GUEST_PASSWORD = os.getenv("REQUEST_GUEST_PASSWORD", os.getenv("GUEST_PASSWORD", VIEWER_PASSWORD_HASH or ""))
REQUEST_ADMIN_USERNAME = os.getenv("REQUEST_ADMIN_USERNAME", os.getenv("ADMIN_USERNAME", "admin"))
REQUEST_ADMIN_PASSWORD = os.getenv("REQUEST_ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", API_AUTH_TOKEN or ""))
REQUEST_SESSION_SECRET = os.getenv("REQUEST_SESSION_SECRET", API_AUTH_TOKEN or VIEWER_ACCESS_TOKEN or "request-portal-secret")
RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", True)
PUBLIC_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("PUBLIC_RATE_LIMIT_WINDOW_SECONDS", "60"))
PUBLIC_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("PUBLIC_RATE_LIMIT_MAX_REQUESTS", "240"))
CHAT_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("CHAT_RATE_LIMIT_MAX_REQUESTS", "30"))
LISCIHUB_PUBLIC_HOST = os.getenv("LISCIHUB_PUBLIC_HOST", "").strip()
ALLOWED_HOSTS = [
    host
    for host in [
        "127.0.0.1",
        "localhost",
        LISCIHUB_PUBLIC_HOST or None,
        f"www.{LISCIHUB_PUBLIC_HOST}" if LISCIHUB_PUBLIC_HOST else None,
    ]
    if host
]

DATABASE_URL = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
