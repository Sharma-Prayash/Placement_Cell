import html
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assistant.models import KnowledgeEntry
from core.sanitize import clean_text

DEFAULT_FILE = Path(__file__).resolve().parents[2] / "knowledge_seed.json"
FIELDS = ["company", "domain", "role", "topic", "subtopic", "question", "answer", "source_title"]


def plain(value) -> str:
    """Tags stripped, then entities turned back into characters: stored as plain text, rendered as text."""
    return html.unescape(clean_text(str(value or "")))


class Command(BaseCommand):
    help = "Load or update interview-preparation entries from JSON (idempotent, keyed by entry_id)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_FILE), help="JSON list of entries")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        records = json.loads(path.read_text(encoding="utf-8"))
        created = updated = skipped = 0
        for rec in records:
            if not all(rec.get(k) for k in ("entry_id", "domain", "topic", "question", "answer")):
                skipped += 1
                continue
            data = {k: plain(rec.get(k))[:5000] for k in FIELDS}
            url = str(rec.get("source_url") or "")
            data.update(
                difficulty=rec.get("difficulty") if rec.get("difficulty") in {"easy", "medium", "hard"} else "medium",
                provenance=rec.get("provenance") if rec.get("provenance") in KnowledgeEntry.Provenance.values else "practice",
                status=rec.get("status") if rec.get("status") in KnowledgeEntry.Status.values else "pending",
                source_url=url if url.startswith("https://") else "",
                tags=[plain(t)[:40] for t in rec.get("tags", [])][:20],
            )
            _, is_new = KnowledgeEntry.objects.update_or_create(entry_id=plain(rec["entry_id"])[:64], defaults=data)
            created += is_new
            updated += not is_new
        self.stdout.write(self.style.SUCCESS(f"Question bank: {created} added, {updated} updated, {skipped} skipped."))
