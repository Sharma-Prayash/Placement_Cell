from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.assistant import llm


class Command(BaseCommand):
    help = "Send one tiny test prompt to Gemini and report whether the configured key and model work."

    def handle(self, *args, **opts):
        if not llm.is_enabled():
            raise CommandError("Gemini is off: set GEMINI_API_KEY (and ASSISTANT_LLM_ENABLED=true) in backend/.env.")
        reply = llm.answer_open("In one sentence, what is a hash function?")
        if reply:
            self.stdout.write(self.style.SUCCESS(f"Gemini works with model {settings.GEMINI_MODEL}. Sample: {reply[:160]}"))
            return
        status = llm.last_status() or {}
        raise CommandError(f"Gemini call failed with model {settings.GEMINI_MODEL}: {status.get('error', '').rstrip('.') or 'no response'}. "
                           "The assistant keeps answering from the question bank until this is fixed.")
