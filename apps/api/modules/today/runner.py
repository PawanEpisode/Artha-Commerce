"""
Runs the registered providers for one student and one day (ERD 3.2, PRD 4.2). Each provider gets its own timeout; one that is
slow, broken or switched off never stops the others, and the plan records what happened (`provider_status`, `partial`).

Providers run in a small shared thread pool, in parallel, so the page waits for the slowest provider and not the sum of them.
A thread cannot be killed: a provider that overruns is abandoned (its answer is thrown away when it finally returns) and the
pool is shared, so a stuck provider costs one of its few threads, not one per request. Tests and `TODAY_PROVIDER_PARALLEL=0`
run providers one after another in the calling thread (same results, the timeout is judged afterwards), which keeps them inside
the test's database transaction.

Operator switches live in `today_providerconfig` and are cached in process for 60 seconds.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field

from django.conf import settings
from django.db import connections

from core.feature_flags import flag_enabled

from . import registry
from .models import ProviderConfig
from .registry import PlanContext, ProviderResult, ProviderSpec, TaskRequest

logger = logging.getLogger(__name__)

CONFIG_TTL_SECONDS = 60.0
POOL_WORKERS = 8

#: What `provider_status` says per provider. Only `timeout` and `error` make the plan partial.
OK, TIMEOUT, ERROR, OFF, DISABLED, SKIPPED = "ok", "timeout", "error", "off", "disabled", "skipped"
PARTIAL_STATUSES = frozenset({TIMEOUT, ERROR})


@dataclass(frozen=True)
class Outcome:
    spec: ProviderSpec
    status: str
    ms: int = 0
    result: ProviderResult | None = None
    weight_pct: int = 100


@dataclass(frozen=True)
class RunResult:
    outcomes: tuple[Outcome, ...] = field(default_factory=tuple)

    @property
    def partial(self) -> bool:
        return any(o.status in PARTIAL_STATUSES for o in self.outcomes)

    def status_map(self) -> dict[str, dict]:
        """The `today_dayplan.provider_status` payload: per provider the status, the time, how many it offered and its backlog."""
        out: dict[str, dict] = {}
        for o in self.outcomes:
            entry: dict = {"status": o.status, "ms": o.ms, "n": len(o.result.candidates) if o.result else 0}
            if o.result and o.result.backlog_count > 0:
                link = o.result.backlog_link
                entry["backlog"] = {
                    "count": o.result.backlog_count,
                    "label": o.result.backlog_label[:80],
                    "link": {"path": link.path, "search": dict(link.search)} if link else None,
                }
            out[o.spec.name] = entry
        return out


# ---- operator config --------------------------------------------------------------------------------------------------------

_config_cache: tuple[float, dict[str, ProviderConfig]] | None = None


def _configs() -> dict[str, ProviderConfig]:
    global _config_cache
    now = time.monotonic()
    if _config_cache is None or now - _config_cache[0] > CONFIG_TTL_SECONDS:
        _config_cache = (now, {c.provider: c for c in ProviderConfig.objects.all()})
    return _config_cache[1]


def clear_config_cache() -> None:
    global _config_cache
    _config_cache = None


# ---- the pool ---------------------------------------------------------------------------------------------------------------

_pool: ThreadPoolExecutor | None = None


def _executor() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=POOL_WORKERS, thread_name_prefix="today-provider")
    return _pool


def _in_thread(spec: ProviderSpec, request: TaskRequest) -> ProviderResult:
    try:
        return spec.provide(request)
    finally:
        connections.close_all()  # a pool thread must not keep a database connection open after its answer


def _parallel() -> bool:
    return bool(getattr(settings, "TODAY_PROVIDER_PARALLEL", True))


# ---- running ----------------------------------------------------------------------------------------------------------------


def _skip_reason(spec: ProviderSpec, ctx: PlanContext, cfg: ProviderConfig | None) -> str | None:
    if cfg is not None and not cfg.enabled:
        return DISABLED
    if spec.flag and not flag_enabled(spec.flag, ctx.user_id):
        return OFF
    if spec.enabled_for is not None:
        try:
            if not spec.enabled_for(ctx.user_id):
                return SKIPPED
        except Exception:  # noqa: BLE001 - a broken eligibility check must not stop the plan
            logger.exception("today: enabled_for of %s failed", spec.name)
            return ERROR
    return None


def _checked(result: object, max_candidates: int) -> ProviderResult | None:
    if not isinstance(result, ProviderResult):
        return None
    candidates = tuple(result.candidates)[:max_candidates]
    return ProviderResult(candidates, result.backlog_count, result.backlog_label, result.backlog_link)


def run_providers(ctx: PlanContext, *, clock: Callable[[], float] = time.monotonic) -> RunResult:
    configs = _configs()
    outcomes: dict[str, Outcome] = {}
    pending: list[tuple[ProviderSpec, ProviderConfig | None, TaskRequest, int, Future | None, float]] = []
    parallel = _parallel()

    for spec in registry.providers():
        cfg = configs.get(spec.name)
        weight = cfg.weight_pct if cfg else 100
        reason = _skip_reason(spec, ctx, cfg)
        if reason is not None:
            outcomes[spec.name] = Outcome(spec, reason, weight_pct=weight)
            continue
        timeout_ms = (cfg.timeout_ms if cfg and cfg.timeout_ms else None) or spec.timeout_ms
        limit = (cfg.max_candidates if cfg and cfg.max_candidates else None) or spec.max_candidates
        request = TaskRequest(ctx=ctx, limit=limit, deadline_ms=timeout_ms)
        started = clock()
        future = _executor().submit(_in_thread, spec, request) if parallel else None
        pending.append((spec, cfg, request, timeout_ms, future, started))

    for spec, cfg, request, timeout_ms, future, started in pending:
        weight = cfg.weight_pct if cfg else 100
        status, result = OK, None
        try:
            if future is not None:
                raw = future.result(timeout=max(started + timeout_ms / 1000 - clock(), 0))
            else:
                raw = spec.provide(request)
            elapsed = int((clock() - started) * 1000)
            if future is None and elapsed > timeout_ms:
                status = TIMEOUT  # inline mode cannot preempt, but a late answer is still a timeout
            else:
                result = _checked(raw, request.limit)
                status = OK if result is not None else ERROR
        except FutureTimeout:
            status, elapsed = TIMEOUT, timeout_ms
            future.cancel()
        except Exception:  # noqa: BLE001 - one broken provider must never take the page down
            logger.exception("today: provider %s failed", spec.name)
            status, elapsed = ERROR, int((clock() - started) * 1000)
        if status != OK:
            result = None
        outcomes[spec.name] = Outcome(spec, status, elapsed, result, weight)

    return RunResult(tuple(outcomes[s.name] for s in registry.providers()))
