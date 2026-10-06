"""Send a real test push to a student's active devices. For checking a deployment and the spike subscription."""

from django.core.management.base import BaseCommand, CommandError

from ...selectors import list_devices
from ...services.notify import send_test_push


class Command(BaseCommand):
    help = "Send a test push to every active device of a student (or to one device with --device)."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="Student (Supabase user) UUID")
        parser.add_argument("--device", help="Only this device UUID")

    def handle(self, *args, user, device=None, **options):
        targets = [str(row["id"]) for row in list_devices(user)]
        if device:
            targets = [d for d in targets if d == device]
        if not targets:
            raise CommandError("No active device matches.")
        for device_id in targets:
            result = send_test_push(user, device_id)
            self.stdout.write(f"{device_id}: {result.outcome}" + (f" ({result.reason.value})" if result.reason else ""))
