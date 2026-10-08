"""
DDL of `recall_reviewlog` (ERD 2.8). Django has no partitioned-table model, so migration 0003 runs this by hand.

PostgreSQL: hash partitioned by `user_id` into 16 partitions, with the immutability trigger `recall_reviewlog_immutable`.
SQLite (the quick tests): an ordinary table with the same columns and checks, no trigger.

The trigger lets nothing change a fact column and nothing delete a row, except:
- `SET LOCAL recall.erasing = 'on'` (the account-erasure service) allows DELETE;
- `SET LOCAL recall.replaying = 'on'` (the replay service) allows the derived columns, `counts_for_scheduling` and `flags` to change.
"""

from __future__ import annotations

PARTITIONS = 16

FACT_COLUMNS = (
    "id", "user_id", "kind", "card_id", "item_id", "item_version_id", "session_id", "rating", "reviewed_at", "received_at",
    "duration_ms", "mode", "device_id", "tz_offset_min", "local_date", "voids_id",
)  # fmt: skip

REWRITABLE_COLUMNS = (
    "counts_for_scheduling", "flags", "phase_before", "stability_before", "difficulty_before", "elapsed_days",
    "retrievability_before", "phase_after", "stability_after", "difficulty_after", "scheduled_days", "due_after",
    "params_id", "scheduler_version",
)  # fmt: skip

_CHECKS = """
    CONSTRAINT recall_reviewlog_kind_valid CHECK (kind IN ('review', 'undo')),
    CONSTRAINT recall_reviewlog_mode_valid CHECK (mode IN ('normal', 'catchup', 'quick_revision', 'cram', 'review_ahead')),
    CONSTRAINT recall_reviewlog_rating_by_kind CHECK (
        (kind = 'review' AND rating IS NOT NULL AND rating BETWEEN 1 AND 4) OR (kind = 'undo' AND rating IS NULL)),
    CONSTRAINT recall_reviewlog_undo_has_target CHECK ((kind = 'undo') = (voids_id IS NOT NULL)),
    CONSTRAINT recall_reviewlog_duration_range CHECK (duration_ms IS NULL OR duration_ms BETWEEN 0 AND 600000)
"""


def _columns(*, vendor: str) -> str:
    pg = vendor == "postgresql"
    uuid, ts, real, text, jsonb = (
        ("uuid", "timestamptz", "real", "text", "jsonb") if pg else ("char(32)", "datetime", "real", "text", "text")
    )
    return f"""
    user_id {uuid} NOT NULL,
    id {uuid} NOT NULL,
    kind varchar(8) NOT NULL DEFAULT 'review',
    card_id {uuid} NOT NULL,
    item_id {uuid} NOT NULL,
    item_version_id {uuid} NOT NULL,
    session_id {uuid},
    rating smallint,
    reviewed_at {ts} NOT NULL,
    received_at {ts} NOT NULL,
    duration_ms integer,
    mode varchar(16) NOT NULL DEFAULT 'normal',
    counts_for_scheduling boolean NOT NULL DEFAULT {"true" if pg else "1"},
    device_id varchar(64),
    tz_offset_min smallint NOT NULL DEFAULT 0,
    local_date date NOT NULL,
    voids_id {uuid},
    flags {jsonb} NOT NULL DEFAULT '[]',
    phase_before smallint,
    stability_before {real},
    difficulty_before {real},
    elapsed_days integer,
    retrievability_before {real},
    phase_after smallint,
    stability_after {real},
    difficulty_after {real},
    scheduled_days {real},
    due_after {ts},
    params_id {uuid},
    scheduler_version {text},
    PRIMARY KEY (user_id, id),
    {_CHECKS.strip()}
"""


def create_statements(vendor: str) -> list[str]:
    if vendor != "postgresql":
        return [
            f"CREATE TABLE recall_reviewlog ({_columns(vendor=vendor)})",
            "CREATE INDEX recall_reviewlog_card_idx ON recall_reviewlog (user_id, card_id, reviewed_at, id)",
            "CREATE INDEX recall_reviewlog_time_idx ON recall_reviewlog (user_id, reviewed_at DESC)",
            "CREATE INDEX recall_reviewlog_again_idx ON recall_reviewlog (user_id, reviewed_at DESC)"
            " WHERE kind = 'review' AND rating = 1",
            "CREATE UNIQUE INDEX recall_reviewlog_voids_uniq ON recall_reviewlog (user_id, voids_id)"
            " WHERE voids_id IS NOT NULL",
        ]
    statements = [f"CREATE TABLE recall_reviewlog ({_columns(vendor=vendor)}) PARTITION BY HASH (user_id)"]
    statements += [
        f"CREATE TABLE recall_reviewlog_p{n:02d} PARTITION OF recall_reviewlog "
        f"FOR VALUES WITH (MODULUS {PARTITIONS}, REMAINDER {n})"
        for n in range(PARTITIONS)
    ]
    statements += [
        "CREATE INDEX recall_reviewlog_card_idx ON recall_reviewlog (user_id, card_id, reviewed_at, id)",
        "CREATE INDEX recall_reviewlog_time_idx ON recall_reviewlog (user_id, reviewed_at DESC)",
        "CREATE INDEX recall_reviewlog_again_idx ON recall_reviewlog (user_id, reviewed_at DESC)"
        " WHERE kind = 'review' AND rating = 1",
        "CREATE UNIQUE INDEX recall_reviewlog_voids_uniq ON recall_reviewlog (user_id, voids_id)"
        " WHERE voids_id IS NOT NULL",
        _trigger_function(),
        "CREATE TRIGGER recall_reviewlog_immutable BEFORE UPDATE OR DELETE ON recall_reviewlog "
        "FOR EACH ROW EXECUTE FUNCTION recall_reviewlog_guard()",
    ]
    return statements


def drop_statements(vendor: str) -> list[str]:
    if vendor != "postgresql":
        return ["DROP TABLE IF EXISTS recall_reviewlog"]
    return ["DROP TABLE IF EXISTS recall_reviewlog CASCADE", "DROP FUNCTION IF EXISTS recall_reviewlog_guard()"]


def _trigger_function() -> str:
    facts_new = ", ".join(f"NEW.{c}" for c in FACT_COLUMNS)
    facts_old = ", ".join(f"OLD.{c}" for c in FACT_COLUMNS)
    derived_new = ", ".join(f"NEW.{c}" for c in REWRITABLE_COLUMNS)
    derived_old = ", ".join(f"OLD.{c}" for c in REWRITABLE_COLUMNS)
    return f"""
CREATE OR REPLACE FUNCTION recall_reviewlog_guard() RETURNS trigger AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF coalesce(current_setting('recall.erasing', true), '') = 'on' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'recall_reviewlog is append only' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ROW({facts_new}) IS DISTINCT FROM ROW({facts_old}) THEN
        RAISE EXCEPTION 'recall_reviewlog facts cannot change' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ROW({derived_new}) IS DISTINCT FROM ROW({derived_old})
       AND coalesce(current_setting('recall.replaying', true), '') <> 'on' THEN
        RAISE EXCEPTION 'recall_reviewlog derived columns are rewritten by the replay service only'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$ LANGUAGE plpgsql
"""
