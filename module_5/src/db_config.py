"""Environment-driven database connection configuration."""

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env-style file into os.environ.

    Existing environment variables are preserved.

    :param path: Filesystem path to the ``.env``-style file.
    :type path: pathlib.Path
    :returns: ``None``.
    :rtype: None
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _autoload_env() -> None:
    """Load local .env defaults when variables were not pre-exported.

    :returns: ``None``.
    :rtype: None
    """
    src_dir = Path(__file__).resolve().parent
    env_candidates = (
        src_dir.parent.parent / ".env",  # jhu_software_concepts/.env
        src_dir.parent / ".env",         # module_5/.env (optional local override)
    )
    for env_path in env_candidates:
        _load_env_file(env_path)


_autoload_env()


def _build_conn_info(
    host: str,
    port: str,
    dbname: str,
    user: str | None,
    password: str | None,
) -> str:
    """Compose a psycopg connection-info string from discrete settings.

    :param host: Database host name.
    :type host: str
    :param port: Database port.
    :type port: str
    :param dbname: Database name.
    :type dbname: str
    :param user: Optional login role/user.
    :type user: str | None
    :param password: Optional login password.
    :type password: str | None
    :returns: Space-delimited connection info string for psycopg.
    :rtype: str
    """
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
    """Return target application database name from environment.

    :returns: Configured application database name.
    :rtype: str
    """
    return os.getenv("DB_NAME", "grad_data")


def get_db_conn_info() -> str:
    """Return application connection info using env vars.

    Uses ``DATABASE_URL`` when present for compatibility, otherwise composes a
    connection string from ``DB_*`` variables.

    :returns: Connection info for the app role.
    :rtype: str
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
    """Return admin connection info for provisioning the database.

    :returns: Connection info for the admin/provisioning role.
    :rtype: str
    """
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
