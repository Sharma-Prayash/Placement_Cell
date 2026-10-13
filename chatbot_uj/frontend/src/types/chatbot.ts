export type ProvenanceType = 'official' | 'reported' | 'practice';

export interface SourceCitation {
  id: string;
  title: string;
  company?: string | null;
  domain?: string | null;
  topic?: string;
  subtopic?: string;
  difficulty?: string;
  provenance: ProvenanceType;
  source_title?: string;
  source_url?: string;
  pdf_document?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  intent?: string;
  status?: 'answered' | 'insufficient_evidence' | 'unavailable';
  generation_mode?: string;
  sources?: SourceCitation[];
  timestamp: string;
}

export interface ChatbotResponse {
  answer: string;
  intent: string;
  sources: SourceCitation[];
  status: 'answered' | 'insufficient_evidence' | 'unavailable';
  generation_mode: string;
}

export interface ChatbotInfo {
  service: string;
  version: string;
  status: string;
  total_knowledge_entries: number;
  approved_entries: number;
  supported_companies: string[];
  domains: string[];
  llm_provider: {
    name: string;
    model: string;
    is_configured: boolean;
    fallback_mode: string;
  };
}
