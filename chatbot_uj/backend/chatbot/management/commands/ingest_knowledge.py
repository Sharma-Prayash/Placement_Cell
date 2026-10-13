import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from chatbot.models import QABankEntry


class Command(BaseCommand):
    help = "Idempotently ingests structured question-answer records into the knowledge bank."

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default=None,
            help='Path to custom JSON file containing question records.'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing entries before ingestion (use with care).'
        )

    def handle(self, *args, **options):
        if options['file']:
            file_path = Path(options['file'])
        else:
            file_path = Path(settings.BASE_DIR) / 'chatbot' / 'seed_data' / 'questions.json'

        if not file_path.exists():
            self.stderr.write(self.style.ERROR(f"Seed file not found at: {file_path}"))
            return

        if options['clear']:
            deleted_count, _ = QABankEntry.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing records."))

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                records = json.load(f)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to parse JSON: {e}"))
                return

        created_count = 0
        updated_count = 0
        error_count = 0

        required_fields = ['entry_id', 'domain', 'topic', 'question', 'answer']
        valid_provenances = {'official', 'reported', 'practice'}
        valid_statuses = {'pending', 'approved', 'rejected', 'revoked'}

        for idx, rec in enumerate(records):
            # Validate required fields
            missing = [k for k in required_fields if not rec.get(k)]
            if missing:
                self.stderr.write(self.style.ERROR(f"Record #{idx} missing required fields {missing}: {rec.get('entry_id', 'unknown')}"))
                error_count += 1
                continue

            provenance = rec.get('provenance', 'practice')
            if provenance not in valid_provenances:
                self.stderr.write(self.style.WARNING(f"Invalid provenance '{provenance}' in {rec['entry_id']}, defaulting to 'practice'"))
                provenance = 'practice'

            status = rec.get('verification_status', 'pending')
            if status not in valid_statuses:
                self.stderr.write(self.style.WARNING(f"Invalid verification_status '{status}' in {rec['entry_id']}, defaulting to 'pending'"))
                status = 'pending'

            entry_id = rec['entry_id'].strip()
            defaults = {
                'company': rec.get('company') or None,
                'domain': rec.get('domain', '').strip(),
                'role': rec.get('role', 'General / SDE / Security Analyst').strip(),
                'topic': rec.get('topic', '').strip(),
                'subtopic': rec.get('subtopic', '').strip(),
                'question': rec.get('question', '').strip(),
                'answer': rec.get('answer', '').strip(),
                'difficulty': rec.get('difficulty', 'medium'),
                'provenance': provenance,
                'source_title': rec.get('source_title', '').strip(),
                'source_url': rec.get('source_url', '').strip(),
                'research_date': rec.get('research_date', '').strip(),
                'verification_status': status,
                'reviewer_name': rec.get('reviewer_name', '').strip(),
                'tags': rec.get('tags', []),
                'pdf_document': rec.get('pdf_document', '').strip(),
                'is_active': rec.get('is_active', True),
            }

            obj, created = QABankEntry.objects.update_or_create(
                entry_id=entry_id,
                defaults=defaults
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully processed {len(records)} records: "
            f"{created_count} created, {updated_count} updated, {error_count} errors."
        ))
