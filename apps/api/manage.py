#!/usr/bin/env python
import os
import sys
from pathlib import Path


def load_env(env_path: Path):
    """Load key-value pairs from .env into os.environ without overriding existing vars."""
    if not env_path.is_file():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            os.environ.setdefault(key, val)


def main():
    base_dir = Path(__file__).resolve().parent
    load_env(base_dir / ".env")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        non_options = [arg for arg in sys.argv[2:] if not arg.startswith("-")]
        if not non_options:
            port = os.environ.get("PORT") or os.environ.get("DJANGO_PORT") or "8000"
            sys.argv.append(port)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
