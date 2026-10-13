from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings

from chatbot.serializers import ChatMessageRequestSerializer, ChatMessageResponseSerializer
from chatbot.orchestrator import ChatbotOrchestrator
from chatbot.models import QABankEntry


orchestrator = ChatbotOrchestrator()


class ChatMessageView(APIView):
    """
    Main endpoint for student interaction with the NFSU Placement Chatbot.
    POST /api/chatbot/message/
    """
    permission_classes = [AllowAny]  # Allows demo use; internal auth extracted from request.user

    def post(self, request, *args, **kwargs):
        serializer = ChatMessageRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": "Validation Error",
                    "details": serializer.errors,
                    "status": "unavailable"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user_message = serializer.validated_data['message']
        conversation_id = serializer.validated_data.get('conversation_id', '')

        # Server-side user identity resolution
        user_obj = request.user if request.user and request.user.is_authenticated else None

        result = orchestrator.process_message(
            user_message=user_message,
            user_obj=user_obj,
            session_id=conversation_id
        )

        resp_serializer = ChatMessageResponseSerializer(data=result)
        if resp_serializer.is_valid():
            return Response(resp_serializer.data, status=status.HTTP_200_OK)

        # Fallback to direct dict response if serializer encounters subtle field mismatch
        return Response(result, status=status.HTTP_200_OK)


class ChatbotInfoView(APIView):
    """
    System status and knowledge repository information.
    GET /api/chatbot/info/
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        total_questions = QABankEntry.objects.filter(is_active=True).count()
        approved_count = QABankEntry.objects.filter(is_active=True, verification_status='approved').count()
        companies = list(
            QABankEntry.objects.filter(is_active=True, company__isnull=False)
            .values_list('company', flat=True)
            .distinct()
        )
        domains = list(
            QABankEntry.objects.filter(is_active=True)
            .values_list('domain', flat=True)
            .distinct()
        )

        gemini_avail = orchestrator.llm_provider.is_available()

        return Response({
            "service": "NFSU AI Placement Chatbot Assistant",
            "version": "1.0.0",
            "status": "operational",
            "total_knowledge_entries": total_questions,
            "approved_entries": approved_count,
            "supported_companies": [c for c in companies if c],
            "domains": domains,
            "llm_provider": {
                "name": "Google Gemini",
                "model": getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash'),
                "is_configured": gemini_avail,
                "fallback_mode": "deterministic_grounded_retrieval"
            }
        })
