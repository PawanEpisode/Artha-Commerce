"""
python manage.py sync_today_providers [--dry-run] [--prune]

Makes the admin list every provider that is registered in code: a missing `today_providerconfig` row is created with the defaults
(enabled, weight 100). Rows of providers that are no longer registered are reported, and deleted with `--prune`. Safe to repeat;
run it after a deploy that adds or removes a provider.
"""

from django.core.management.base import BaseCommand

from modules.today import registry
from modules.today.models import ProviderConfig


class Command(BaseCommand):
    help = (
        "Create a provider config row for every registered provider and report rows of providers that no longer exist."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would change and change nothing.")
        parser.add_argument(
            "--prune", action="store_true", help="Delete the rows of providers that are not registered."
        )

    def handle(self, *args, dry_run, prune, **options):
        registered = {p.name for p in registry.providers()}
        existing = set(ProviderConfig.objects.values_list("provider", flat=True))
        missing, stale = sorted(registered - existing), sorted(existing - registered)
        if not dry_run:
            ProviderConfig.objects.bulk_create(
                [ProviderConfig(provider=name) for name in missing], ignore_conflicts=True
            )
            if prune and stale:
                ProviderConfig.objects.filter(provider__in=stale).delete()
        verb = "Would create" if dry_run else "Created"
        self.stdout.write(f"{verb} {len(missing)} row(s): {', '.join(missing) or 'none'}.")
        action = "Would delete" if dry_run and prune else "Deleted" if prune else "Not registered (kept, use --prune)"
        self.stdout.write(f"{action}: {len(stale)} row(s): {', '.join(stale) or 'none'}.")
