import React, { useState, useEffect, useRef } from 'react';
import type { ChatMessage } from '../types/chatbot';
import { sendChatMessage } from '../services/chatbotApi';

const SUGGESTED_PROMPTS = [
  "Prepare me for a cybersecurity interview.",
  "Show me JPMorgan interview practice questions.",
  "Explain my placement eligibility.",
  "How does the placement process work?"
];

export const FloatingChatbot: React.FC = () => {
  // Start open by default for immediate accessibility, but easily minimizable
  const [isOpen, setIsOpen] = useState(true);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'bot',
      text: "👋 Hello! I am **U.J. — NFSU Placement Assistant**.\n\nI can help you with:\n• **Interview Preparation:** Technical and behavioral questions for JPMorgan, Amazon, Microsoft, Google, Deloitte, and Accenture.\n• **General Placement Info:** Official NFSU procedures, drive stages, recruiter details, and aggregated statistics.\n• **Personal Eligibility:** Deterministic checks via the NFSU policy engine.\n\nSelect a prompt below or type your question to begin!",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new message or loading state change
  useEffect(() => {
    if (isOpen && !isMinimized) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen, isMinimized, isLoading]);

  // Focus input when open
  useEffect(() => {
    if (isOpen && !isMinimized) {
      inputRef.current?.focus();
    }
  }, [isOpen, isMinimized]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isLoading) return;

    setErrorText(null);
    setInputMessage('');

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await sendChatMessage(text);
      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: response.answer,
        intent: response.intent,
        status: response.status,
        generation_mode: response.generation_mode,
        sources: response.sources,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg = err.message || 'Unable to connect to backend service.';
      setErrorText(errorMsg);
      const errorBotMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'bot',
        text: `⚠️ **Connection Notice:** ${errorMsg}`,
        status: 'unavailable',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, errorBotMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const renderProvenanceBadge = (prov: string) => {
    const p = (prov || '').toLowerCase();
    if (p === 'official') {
      return <span className="prov-badge badge-official">Official</span>;
    }
    if (p === 'reported') {
      return <span className="prov-badge badge-reported">Reported</span>;
    }
    return <span className="prov-badge badge-practice">Practice</span>;
  };

  const formatInline = (str: string) => {
    let res = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    res = res.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    res = res.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer" class="source-link">$1</a>');
    return res;
  };

  const renderFormattedText = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      if (line.startsWith('### ')) {
        return <h4 key={idx} className="msg-h4">{line.replace('### ', '')}</h4>;
      }
      if (line.startsWith('## ')) {
        return <h3 key={idx} className="msg-h3">{line.replace('## ', '')}</h3>;
      }
      if (line.startsWith('• ') || line.startsWith('- ')) {
        const itemText = line.substring(2);
        return (
          <li key={idx} className="msg-bullet" dangerouslySetInnerHTML={{ __html: formatInline(itemText) }} />
        );
      }
      if (line.trim() === '---') {
        return <hr key={idx} className="msg-divider" />;
      }
      if (!line.trim()) {
        return <div key={idx} className="msg-spacer" />;
      }

      return (
        <p key={idx} className="msg-para" dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
      );
    });
  };

  return (
    <>
      {/* Floating Bottom-Right Launcher Trigger */}
      {!isOpen && (
        <button
          onClick={() => { setIsOpen(true); setIsMinimized(false); }}
          className="chatbot-launcher"
          aria-label="Open U.J. — NFSU Placement Assistant"
          title="Open U.J. — NFSU Placement Assistant"
        >
          <div className="launcher-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
          </div>
          <div className="launcher-text">
            <span className="launcher-title">U.J. Assistant</span>
            <span className="launcher-subtitle">NFSU Placement Support</span>
          </div>
          <span className="launcher-badge">AI</span>
        </button>
      )}

      {/* Floating Assistant Panel */}
      {isOpen && (
        <aside
          className={`chatbot-panel ${isMinimized ? 'panel-minimized' : ''}`}
          aria-label="U.J. — NFSU Placement Assistant"
        >
          {/* Header */}
          <div className="panel-header">
            <div className="header-branding">
              <div className="header-logo-badge">🏛️</div>
              <div>
                <h3 className="header-title">U.J. — NFSU Placement Assistant</h3>
                <p className="header-subtitle">Career Development Centre • Grounded AI</p>
              </div>
            </div>
            <div className="header-actions">
              <button
                onClick={() => setIsMinimized(!isMinimized)}
                className="action-btn"
                title={isMinimized ? "Expand chat" : "Minimize chat"}
                aria-label={isMinimized ? "Expand chat" : "Minimize chat"}
              >
                {isMinimized ? '▲' : '─'}
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="action-btn close-btn"
                title="Close chat"
                aria-label="Close chat"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Panel Body */}
          {!isMinimized && (
            <>
              {/* Message List */}
              <div className="panel-messages">
                {messages.map((msg) => (
                  <div key={msg.id} className={`chat-bubble-container ${msg.sender === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
                    <div className="chat-bubble">
                      {msg.sender === 'bot' && (
                        <div className="bubble-bot-header">
                          <span className="bot-tag">U.J.</span>
                          {msg.generation_mode && (
                            <span className="mode-tag">
                              {msg.generation_mode === 'grounded_llm' ? '✨ Gemini LLM' :
                               msg.generation_mode === 'policy_engine' ? '⚖️ Policy Engine' :
                               msg.generation_mode === 'student_records' ? '📋 Student Registry' :
                               '📚 Grounded Retrieval'}
                            </span>
                          )}
                        </div>
                      )}

                      <div className="bubble-content">
                        {renderFormattedText(msg.text)}
                      </div>

                      {/* Source Citations */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="sources-container">
                          <div className="sources-header">Verified Sources & Citations:</div>
                          <div className="sources-list">
                            {msg.sources.map((s, sIdx) => (
                              <div key={s.id || sIdx} className="source-chip">
                                <div className="source-chip-top">
                                  {renderProvenanceBadge(s.provenance || 'practice')}
                                  <span className="source-title">{s.title || s.id}</span>
                                </div>
                                {s.pdf_document && (
                                  <span className="doc-indicator">
                                    📄 {s.pdf_document}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="bubble-time">{msg.timestamp}</div>
                    </div>
                  </div>
                ))}

                {/* Loading state indicator */}
                {isLoading && (
                  <div className="chat-bubble-container bubble-bot">
                    <div className="chat-bubble loading-bubble">
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <span className="loading-text">U.J. is consulting the NFSU knowledge base...</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Suggested Prompt Chips */}
              {messages.length <= 3 && !isLoading && (
                <div className="suggested-prompts-container">
                  <div className="suggested-title">Quick Inquiries:</div>
                  <div className="suggested-grid">
                    {SUGGESTED_PROMPTS.map((prompt, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSendMessage(prompt)}
                        className="prompt-chip"
                        disabled={isLoading}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Banner */}
              {errorText && (
                <div className="error-banner">
                  <span>{errorText}</span>
                  <button onClick={() => setErrorText(null)} className="error-close">✕</button>
                </div>
              )}

              {/* Message Input Area */}
              <div className="panel-input-container">
                <textarea
                  ref={inputRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask U.J. about interview prep, placement rules..."
                  rows={2}
                  className="chat-textarea"
                  disabled={isLoading}
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={isLoading || !inputMessage.trim()}
                  className="send-button"
                  aria-label="Send Message"
                  title="Send message"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                </button>
              </div>
            </>
          )}
        </aside>
      )}
    </>
  );
};
