from django.urls import path
from chatbot.views import ChatMessageView, ChatbotInfoView

urlpatterns = [
    path('message/', ChatMessageView.as_view(), name='chatbot-message'),
    path('info/', ChatbotInfoView.as_view(), name='chatbot-info'),
]
