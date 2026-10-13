from rest_framework import serializers


class ChatMessageRequestSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=1000,
        required=True,
        trim_whitespace=True,
        error_messages={
            'required': 'Message cannot be empty.',
            'max_length': 'Message cannot exceed 1000 characters.'
        }
    )
    conversation_id = serializers.CharField(required=False, allow_blank=True, default='')


class SourceCitationSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    company = serializers.CharField(allow_null=True, required=False)
    domain = serializers.CharField(allow_null=True, required=False)
    topic = serializers.CharField(required=False)
    difficulty = serializers.CharField(required=False)
    provenance = serializers.CharField(required=False)
    source_title = serializers.CharField(required=False)
    source_url = serializers.CharField(required=False)
    pdf_document = serializers.CharField(required=False, allow_blank=True)


class ChatMessageResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    intent = serializers.CharField()
    sources = SourceCitationSerializer(many=True)
    status = serializers.ChoiceField(choices=['answered', 'insufficient_evidence', 'unavailable'])
    generation_mode = serializers.CharField()
