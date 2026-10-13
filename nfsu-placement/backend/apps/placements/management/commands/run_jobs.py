from django.core.management.base import BaseCommand

from apps.placements.jobs import run_all


class Command(BaseCommand):
    help = "Expire overdue offers, close past-deadline drives, and mark absentees for ended events."

    def handle(self, *args, **options):
        self.stdout.write(str(run_all()))
