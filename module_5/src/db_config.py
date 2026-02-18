"""Environment-driven database connection configuration."""

import os


def _build_conn_info(
    host: str,
    port: str,
    dbname: str,
    user: str | None,
    password: str | None,
) -> str:
    parts = [
        f"host={host}",
        f"port={port}",
        f"dbname={dbname}",
    ]
    if user:  # pragma: no cover - optional env branch
        parts.append(f"user={user}")
    if password:  # pragma: no cover - optional env branch
        parts.append(f"password={password}")
    return " ".join(parts)


def get_db_name() -> str:
    """Return target application database name from environment."""
    return os.getenv("DB_NAME", "grad_data")


def get_db_conn_info() -> str:
    """Return application connection info using env vars.

    Uses ``DATABASE_URL`` when present for compatibility, otherwise composes a
    connection string from ``DB_*`` variables.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    return _build_conn_info(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=get_db_name(),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_admin_conn_info() -> str:
    """Return admin connection info for provisioning the database."""
    admin_url = os.getenv("DATABASE_ADMIN_URL")
    if admin_url:  # pragma: no cover - optional DSN override branch
        return admin_url
    return _build_conn_info(
        host=os.getenv("DB_ADMIN_HOST", os.getenv("DB_HOST", "localhost")),
        port=os.getenv("DB_ADMIN_PORT", os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_ADMIN_NAME", "postgres"),
        user=os.getenv("DB_ADMIN_USER"),
        password=os.getenv("DB_ADMIN_PASSWORD"),
    )
