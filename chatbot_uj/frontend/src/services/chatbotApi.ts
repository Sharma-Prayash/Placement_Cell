import type { ChatbotResponse, ChatbotInfo } from '../types/chatbot';

const BASE_URL = '/api/chatbot';

export async function sendChatMessage(message: string, conversationId?: string): Promise<ChatbotResponse> {
  const response = await fetch(`${BASE_URL}/message/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || '',
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || errorData.details?.message?.[0] || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchChatbotInfo(): Promise<ChatbotInfo> {
  const response = await fetch(`${BASE_URL}/info/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch system info: ${response.status}`);
  }
  return response.json();
}
