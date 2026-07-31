import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _database_url() -> str:
    """
    Database URL handling for local development and Render production.

    Local:
    - If DATABASE_URL is empty, use absolute SQLite path:
      sqlite:////.../instance/austria_express.db

    Windows/OneDrive:
    - Relative SQLite URLs such as sqlite:///instance/austria_express.db
      are normalized to an absolute project path.

    Render/PostgreSQL:
    - Render may provide postgres:// or postgresql://.
    - This app uses psycopg v3, so URLs are normalized to postgresql+psycopg://.
    """
    fallback_path = BASE_DIR / "instance" / "austria_express.db"
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{fallback_path.as_posix()}"

    if url.startswith("postgresql+psycopg://"):
        return url

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    if url.startswith("sqlite:///"):
        raw_path = url.replace("sqlite:///", "", 1)

        is_windows_abs = len(raw_path) >= 2 and raw_path[1] == ":"
        is_posix_abs = raw_path.startswith("/")

        if not is_windows_abs and not is_posix_abs:
            db_path = BASE_DIR / raw_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path.as_posix()}"

        db_path = Path(raw_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"

    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")

    UPLOAD_FOLDER = BASE_DIR / "app" / "static" / "uploads"
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "10")) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

    # Behind Render proxy, Flask still works normally.
    # Cookie flags are kept conservative; can be hardened later when final domain/HTTPS is fixed.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
