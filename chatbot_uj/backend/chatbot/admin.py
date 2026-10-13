from django.contrib import admin
from .models import QABankEntry, ConversationSession, ChatLog


@admin.register(QABankEntry)
class QABankEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_id', 'company', 'domain', 'topic', 'difficulty', 'provenance', 'verification_status', 'is_active')
    list_filter = ('verification_status', 'provenance', 'difficulty', 'domain', 'company', 'is_active')
    search_fields = ('question', 'answer', 'topic', 'subtopic', 'company', 'tags')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['mark_approved', 'mark_revoked']

    @admin.action(description="Approve selected entries")
    def mark_approved(self, request, queryset):
        queryset.update(verification_status='approved', reviewer_name=request.user.username)

    @admin.action(description="Revoke selected entries")
    def mark_revoked(self, request, queryset):
        queryset.update(verification_status='revoked')


@admin.register(ConversationSession)
class ConversationSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'updated_at')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'intent', 'status', 'generation_mode', 'created_at')
    list_filter = ('intent', 'status', 'generation_mode')
    search_fields = ('user_message', 'bot_response')
    readonly_fields = ('session', 'user_message', 'bot_response', 'intent', 'status', 'generation_mode', 'sources_cited', 'latency_ms', 'created_at')
