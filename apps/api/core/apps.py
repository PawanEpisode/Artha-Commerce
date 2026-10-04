from django.apps import AppConfig
from django.db.models.signals import post_migrate


def enable_rls_everywhere(sender, using="default", **kwargs):
    """
    Defence in depth: Django is the only writer of app data, so PostgREST (Supabase Data API) must never read it.
    After every migrate, enable Row Level Security (with no policies) on every public table.
    The Django DB role owns the tables and therefore bypasses RLS; `anon` and `authenticated` get nothing.
    """
    from django.db import connections

    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            DECLARE t record;
            BEGIN
              FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
              END LOOP;
            END $$;
            """
        )


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        post_migrate.connect(enable_rls_everywhere, dispatch_uid="core.enable_rls_everywhere")
