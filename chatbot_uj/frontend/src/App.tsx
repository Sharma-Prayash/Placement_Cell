import React from 'react';
import { FloatingChatbot } from './components/FloatingChatbot';

export const App: React.FC = () => {
  return (
    <div className="portal-wrapper">
      <header className="minimal-header">
        <div className="header-inner">
          <div className="brand-group">
            <div className="brand-crest">NFSU</div>
            <div>
              <h1 className="brand-title">National Forensic Sciences University</h1>
              <p className="brand-subtitle">Career Development Centre (CDC) • Gandhinagar Campus</p>
            </div>
          </div>
          <div className="campus-badge">
            <span className="dot-pulse"></span>
            <span>Placement Portal Active</span>
          </div>
        </div>
      </header>

      <main className="portal-hero">
        <div className="hero-card">
          <div className="hero-emblem">🎓</div>
          <h2 className="hero-title">Student Placement & Interview Portal</h2>
          <p className="hero-description">
            Welcome to the official NFSU Placement platform. Use the <strong>U.J. — NFSU Placement Assistant</strong> located at the bottom-right of your screen for real-time company interview preparation, institutional placement guidelines, and policy-driven eligibility evaluations.
          </p>
          <div className="quick-info-pills">
            <span className="pill">💼 52+ Verified Interview Guides</span>
            <span className="pill">⚖️ Policy Engine Integration</span>
            <span className="pill">🛡️ Cybersecurity & Forensics Focused</span>
          </div>
        </div>
      </main>

      {/* Floating Bottom-Right Chatbot */}
      <FloatingChatbot />
    </div>
  );
};

export default App;
