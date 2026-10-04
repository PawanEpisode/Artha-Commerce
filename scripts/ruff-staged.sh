#!/usr/bin/env bash
# Runs ruff on staged Python files. Skips with a notice if ruff is not installed locally (CI still enforces it).
if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff not found: skipping Python lint (install with: pip install -r apps/api/requirements-dev.txt)"
  exit 0
fi
ruff check --fix --config apps/api/ruff.toml "$@" && ruff format --config apps/api/ruff.toml "$@"
