"""Row Level Security on every recall table, including the 16 log partitions (ERD 0.12). PostgreSQL only."""

import pytest
from django.apps import apps
from django.db import connection

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Row Level Security only exists on PostgreSQL"),
]


def recall_tables() -> list[str]:
    return sorted(m._meta.db_table for m in apps.get_app_config("recall").get_models())


def test_rls_is_on_for_every_recall_table_and_every_partition():
    with connection.cursor() as c:
        c.execute(
            "SELECT relname, relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND relname LIKE 'recall_%'"
        )
        found = dict(c.fetchall())
    expected = recall_tables() + [f"recall_reviewlog_p{n:02d}" for n in range(16)]
    assert len(recall_tables()) >= 18
    assert [t for t in expected if t not in found] == [], "tables missing from the database"
    assert [t for t, on in found.items() if not on] == [], "RLS is off on these tables"


def test_no_policy_opens_a_recall_table_to_the_data_api():
    with connection.cursor() as c:
        c.execute(
            "SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' AND tablename LIKE 'recall_%'"
        )
        assert c.fetchall() == []


def test_the_postgres_only_extras_exist():
    with connection.cursor() as c:
        c.execute("SELECT 1 FROM pg_trigger WHERE tgname = 'recall_reviewlog_immutable' AND NOT tgisinternal")
        assert c.fetchone()
        c.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = 'recall_item' AND column_name = 'search_tsv'"
        )
        assert c.fetchone()
        c.execute(
            "SELECT conname FROM pg_constraint WHERE conname IN ('recall_params_weights_len', 'recall_scheduleevent_card_user_fk')"
        )
        assert len(c.fetchall()) == 2
