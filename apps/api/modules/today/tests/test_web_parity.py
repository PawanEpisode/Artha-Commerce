"""The web Today module mirrors the numbers the UI enforces. This fails when `limits.ts` and `domain/constants.py` drift apart."""

import re
from pathlib import Path

from modules.today.domain import constants

LIMITS_TS = Path(__file__).resolve().parents[4] / "web/src/modules/today/lib/limits.ts"


def _web_limits() -> dict[str, int]:
    return {name: int(value) for name, value in re.findall(r"export const ([A-Z_]+) = (\d+)\b", LIMITS_TS.read_text())}


def test_web_limits_match_the_api():
    web = _web_limits()
    assert web, "no constants found in limits.ts"
    missing = [name for name in web if not hasattr(constants, name)]
    assert not missing, f"limits.ts has constants the API does not define: {missing}"
    assert web == {name: getattr(constants, name) for name in web}
