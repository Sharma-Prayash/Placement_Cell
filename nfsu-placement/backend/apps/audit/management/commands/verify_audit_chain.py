from django.core.management.base import BaseCommand

from apps.audit.services import verify_chain


class Command(BaseCommand):
    help = "Recompute the audit hash chain and report the first tampered row."

    def handle(self, *args, **options):
        ok, bad_id, count = verify_chain()
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Audit chain intact: {count} records verified."))
        else:
            self.stdout.write(self.style.ERROR(f"Audit chain BROKEN at record id={bad_id} (after {count} valid records)."))
            raise SystemExit(1)
