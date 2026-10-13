import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class QABankEntry(models.Model):
    """
    Structured question-and-answer entry for the NFSU interview knowledge base.
    Maintains provenance and strict verification status.
    """
    PROVENANCE_CHOICES = [
        ('official', 'Official (Supported by official source)'),
        ('reported', 'Reported (Publicly reported student experience)'),
        ('practice', 'Practice (Realistic practice question)'),
    ]

    VERIFICATION_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved / Verified'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    entry_id = models.CharField(max_length=64, unique=True, db_index=True)
    company = models.CharField(max_length=120, blank=True, null=True, db_index=True, help_text="Specific company or null for general domain")
    domain = models.CharField(max_length=120, db_index=True, help_text="e.g. Cybersecurity, DFIS, DSA, AI/ML, HR")
    role = models.CharField(max_length=120, blank=True, default="General / SDE / Security Analyst")
    topic = models.CharField(max_length=120, db_index=True)
    subtopic = models.CharField(max_length=120, blank=True, default="")
    question = models.TextField()
    answer = models.TextField(help_text="Detailed educational model answer")
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    
    provenance = models.CharField(max_length=20, choices=PROVENANCE_CHOICES, default='practice')
    source_title = models.CharField(max_length=255, blank=True, default="")
    source_url = models.URLField(max_length=500, blank=True, default="")
    research_date = models.CharField(max_length=50, blank=True, default="")
    
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default='pending', db_index=True)
    reviewer_name = models.CharField(max_length=150, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    
    tags = models.JSONField(default=list, blank=True, help_text="List of keywords and search tags")
    pdf_document = models.CharField(max_length=255, blank=True, default="", help_text="Associated PDF guide filename")
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Q&A Knowledge Entry"
        verbose_name_plural = "Q&A Knowledge Entries"
        ordering = ['company', 'domain', 'topic', 'difficulty']

    def __str__(self):
        target = self.company or self.domain
        return f"[{self.provenance.upper()} - {self.verification_status}] {target} - {self.question[:60]}..."


class ConversationSession(models.Model):
    """
    Tracks conversation sessions securely without logging sensitive credentials.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.id} (User: {self.user.username if self.user else 'Guest'})"


class ChatLog(models.Model):
    """
    Privacy-conscious log of queries and responses.
    Pii is redacted; no passwords or tokens are stored.
    """
    session = models.ForeignKey(ConversationSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    user_message = models.TextField()
    bot_response = models.TextField()
    intent = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=32)
    generation_mode = models.CharField(max_length=32)
    sources_cited = models.JSONField(default=list, blank=True)
    latency_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.intent}] {self.user_message[:40]} -> {self.status}"
