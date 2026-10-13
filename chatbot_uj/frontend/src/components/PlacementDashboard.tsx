import React, { useState, useEffect } from 'react';
import { fetchChatbotInfo } from '../services/chatbotApi';
import type { ChatbotInfo } from '../types/chatbot';

export const PlacementDashboard: React.FC = () => {
  const [sysInfo, setSysInfo] = useState<ChatbotInfo | null>(null);

  useEffect(() => {
    fetchChatbotInfo().then(setSysInfo).catch(() => {});
  }, []);

  return (
    <div className="dashboard-container">
      {/* Top Navigation */}
      <header className="dashboard-nav">
        <div className="nav-left">
          <div className="portal-logo">NFSU</div>
          <div>
            <h1 className="portal-title">National Forensic Sciences University</h1>
            <p className="portal-subtitle">Career Development Centre (CDC) — Student Placement Portal</p>
          </div>
        </div>
        <div className="nav-right">
          <span className="student-badge">Radhika Nair (M.Tech Cyber Security)</span>
          <span className="status-pill status-active">Academic Year 2026-27</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="dashboard-main">
        {/* Welcome & Stats Row */}
        <section className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Academic Profile</span>
            <span className="stat-val">8.75 CGPA</span>
            <span className="stat-sub">Attendance: 88.5% • Zero Backlogs</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Recorded Offer</span>
            <span className="stat-val text-green">12.5 LPA</span>
            <span className="stat-sub">Deloitte (Cyber Risk Consultant)</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Placement Drive Average</span>
            <span className="stat-val text-blue">14.8 LPA</span>
            <span className="stat-sub">Highest: 44.5 LPA • 89.4% Placed</span>
          </div>
          <div className="stat-card stat-system">
            <span className="stat-label">Knowledge Repository</span>
            <span className="stat-val">{sysInfo?.total_knowledge_entries || 52} Q&As</span>
            <span className="stat-sub">
              {sysInfo?.llm_provider?.is_configured ? '✨ Gemini Enabled' : '📚 Deterministic Grounded'}
            </span>
          </div>
        </section>

        {/* Two-column layout */}
        <div className="dashboard-grid">
          {/* Active Placement Drives */}
          <section className="content-card">
            <div className="card-header">
              <h2>Active & Upcoming Campus Placement Drives</h2>
              <span className="badge-notification">4 Drives Active</span>
            </div>
            <div className="drives-list">
              <div className="drive-item">
                <div className="drive-info">
                  <h4 className="drive-company">JPMorgan Chase</h4>
                  <p className="drive-role">Cybersecurity Analyst & Technology Analyst</p>
                  <span className="drive-pkg">Package: 19.5 LPA • Minimum CGPA: 7.0</span>
                </div>
                <div className="drive-action">
                  <span className="elig-tag elig-allow">Eligible to Apply</span>
                  <button className="btn-secondary">View JNF</button>
                </div>
              </div>

              <div className="drive-item">
                <div className="drive-info">
                  <h4 className="drive-company">Amazon</h4>
                  <p className="drive-role">Software Development Engineer (SDE-1)</p>
                  <span className="drive-pkg">Package: 28.0 LPA • Minimum CGPA: 7.5</span>
                </div>
                <div className="drive-action">
                  <span className="elig-tag elig-review">Dream Offer (1.5x Waiver)</span>
                  <button className="btn-secondary">View JNF</button>
                </div>
              </div>

              <div className="drive-item">
                <div className="drive-info">
                  <h4 className="drive-company">Microsoft</h4>
                  <p className="drive-role">Software Engineer & Systems Associate</p>
                  <span className="drive-pkg">Package: 24.5 LPA • Minimum CGPA: 7.5</span>
                </div>
                <div className="drive-action">
                  <span className="elig-tag elig-allow">Eligible to Apply</span>
                  <button className="btn-secondary">View JNF</button>
                </div>
              </div>

              <div className="drive-item">
                <div className="drive-info">
                  <h4 className="drive-company">National Cyber Coordination Centre (NCCC)</h4>
                  <p className="drive-role">Cyber Defense & Incident Response Fellow</p>
                  <span className="drive-pkg">Package: 16.0 LPA • Minimum CGPA: 7.0</span>
                </div>
                <div className="drive-action">
                  <span className="elig-tag elig-allow">Eligible to Apply</span>
                  <button className="btn-secondary">View JNF</button>
                </div>
              </div>
            </div>
          </section>

          {/* Quick Notice & Placement Guidelines */}
          <section className="content-card">
            <div className="card-header">
              <h2>CDC Notices & Student Guidelines</h2>
            </div>
            <div className="guidelines-content">
              <div className="notice-box">
                <span className="notice-icon">📢</span>
                <div>
                  <strong>One-Student-One-Job Institutional Rule:</strong>
                  <p>Students with an existing Category A offer (e.g., Deloitte) are permitted to interview only for Dream and Super-Dream offers exceeding a 1.5x CTC multiplier.</p>
                </div>
              </div>

              <div className="notice-box notice-blue">
                <span className="notice-icon">🤖</span>
                <div>
                  <strong>AI Placement Assistant Online:</strong>
                  <p>Click the floating assistant at the bottom right anytime to ask company-specific interview questions, review DSA/Security concepts, or check your policy eligibility.</p>
                </div>
              </div>

              <div className="quick-links-group">
                <h3>Placement Resources:</h3>
                <ul className="resource-list">
                  <li>📄 NFSU Standardized Resume Template</li>
                  <li>📋 Pre-Placement Talk (PPT) Mandatory Attendance Policy</li>
                  <li>🔐 Off-Campus Internship NOC Guidelines</li>
                  <li>📊 Historical Placement Reports & Recruiter Directory</li>
                </ul>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};
