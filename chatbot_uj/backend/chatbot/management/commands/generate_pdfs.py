import os
import json
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


GUIDES_DATA = [
    {
        "filename": "jpmorgan_interview_guide.pdf",
        "title": "JPMorgan Chase — Campus Placement Interview Guide",
        "company": "JPMorgan Chase",
        "domain": "FinTech & Enterprise Engineering",
        "roles": ["Software Engineer", "Cybersecurity Analyst", "Technology Analyst"],
        "source_doc": "jpmorgan_interview_guide.md",
        "provenance_summary": {"reported": 4, "practice": 1, "official": 0},
        "overview": "JPMorgan Chase evaluates engineering rigor, financial transaction integrity, web security (OWASP), and behavioral alignment with their core principles of exceptional client service and regulatory compliance.",
        "interview_format": "Round 1: Coding & Technical Assessment (HackerRank/HireVue) -> Round 2: Technical Interview (DSA, Systems, Security) -> Round 3: Architectural/Scenario Discussion -> Round 4: Behavioral & Leadership.",
        "sample_topics": [
            ("Application Security", "reported", "Prevention of XSS, CSRF, and session hijacking in banking systems."),
            ("ACID & Concurrency", "reported", "Database isolation levels, phantom reads, and two-phase locking in ledger systems."),
            ("PKI & TLS 1.3", "reported", "Mutual TLS authentication (mTLS) and SSL pinning in mobile banking applications."),
            ("Behavioral STAR", "practice", "Handling production security vulnerabilities under tight release schedules.")
        ]
    },
    {
        "filename": "amazon_interview_guide.pdf",
        "title": "Amazon — SDE & Cloud Campus Interview Guide",
        "company": "Amazon",
        "domain": "Cloud Computing & Distributed Systems",
        "roles": ["Software Development Engineer (SDE-1)", "Cloud Support Associate"],
        "source_doc": "amazon_interview_guide.md",
        "provenance_summary": {"official": 1, "reported": 4, "practice": 0},
        "overview": "Amazon emphasizes mastery of Data Structures, Algorithms, Distributed System Design, and deep immersion in their 16 Leadership Principles, particularly Customer Obsession and Bias for Action.",
        "interview_format": "Round 1: Online Assessment (Coding + Work Style Simulation) -> Round 2: Technical DSA (Graphs, DP, Trees) -> Round 3: Low-Level Design & System Internals -> Round 4: Bar Raiser & Leadership Principles.",
        "sample_topics": [
            ("Graph Algorithms", "reported", "Topological Sort (Kahn's algorithm) and dependency cycle detection."),
            ("API Rate Limiting", "reported", "Distributed Token Bucket implementation with atomic Redis Lua scripts."),
            ("NoSQL & DynamoDB", "reported", "Partition key hashing, hot partition mitigation, and CAP Theorem tradeoffs."),
            ("Leadership Principles", "official", "Demonstrating Customer Obsession and Ownership in academic or production projects.")
        ]
    },
    {
        "filename": "microsoft_interview_guide.pdf",
        "title": "Microsoft — Software Engineering Interview Guide",
        "company": "Microsoft",
        "domain": "Enterprise Software & Cloud Platforms",
        "roles": ["Software Engineer", "Systems Engineer"],
        "source_doc": "microsoft_interview_guide.md",
        "provenance_summary": {"reported": 3, "practice": 0, "official": 0},
        "overview": "Microsoft focuses on clean object-oriented architecture, SOLID design principles, operating system internals, scalable data structures, and collaborative problem-solving.",
        "interview_format": "Round 1: Online Coding Round -> Round 2: Data Structures & Problem Solving -> Round 3: OOP, SOLID & Low-Level Design -> Round 4: Systems, OS & Culture Fit.",
        "sample_topics": [
            ("SOLID Principles", "reported", "Practical application of Open/Closed (OCP) and Dependency Inversion (DIP)."),
            ("Operating Systems", "reported", "Process vs Thread differences and virtual memory paging mechanics."),
            ("Priority Queues", "reported", "Dual-heap streaming median calculation in O(1) query time.")
        ]
    },
    {
        "filename": "google_interview_guide.pdf",
        "title": "Google — Software Engineer Technical Interview Guide",
        "company": "Google",
        "domain": "Large-Scale Systems & Core Algorithms",
        "roles": ["Software Engineer", "Site Reliability Engineer (SRE)"],
        "source_doc": "google_interview_guide.md",
        "provenance_summary": {"reported": 3, "practice": 0, "official": 0},
        "overview": "Google technical interviews require mathematical rigor, edge-case analysis, optimal time-space algorithmic complexity, and foundational networking/systems knowledge.",
        "interview_format": "Round 1: Google Online Challenge (GOC) -> Round 2 & 3: Algorithmic Interviews (Google Docs/Meet) -> Round 4: Systems / SRE / Googleyness & Leadership.",
        "sample_topics": [
            ("Intervals & DP", "reported", "Non-overlapping interval greedy activity selection in O(N log N)."),
            ("QUIC & HTTP/3", "reported", "Overcoming transport-layer Head-of-Line blocking over UDP with integrated TLS."),
            ("Linux Systems", "reported", "Event-driven asynchronous scalability using epoll vs select (C10K problem).")
        ]
    },
    {
        "filename": "deloitte_interview_guide.pdf",
        "title": "Deloitte — Cyber Risk & Technology Consulting Guide",
        "company": "Deloitte",
        "domain": "Cyber Risk, IT Audit & Advisory",
        "roles": ["Cyber Risk Consultant", "Technology Audit Associate"],
        "source_doc": "deloitte_interview_guide.md",
        "provenance_summary": {"reported": 4, "practice": 0, "official": 0},
        "overview": "Deloitte USI and India advisory practices assess knowledge of security frameworks (NIST CSF, ISO 27001), IT auditing (SOC 2, Segregation of Duties), cloud IAM governance, and consulting communication.",
        "interview_format": "Round 1: Aptitude & Domain Online Test -> Round 2: Technical Interview (Cyber Risk / Compliance / VAPT) -> Round 3: Case Study & Scenario Analysis -> Round 4: Partner / HR Round.",
        "sample_topics": [
            ("NIST CSF 2.0", "reported", "Govern, Identify, Protect, Detect, Respond, Recover core functions."),
            ("SOC 2 Auditing", "reported", "Type I vs Type II reports and Segregation of Duties (SoD) enforcement."),
            ("Cloud IAM Security", "reported", "Least privilege and AWS IAM privilege escalation attack vectors."),
            ("Case Problem Solving", "reported", "MECE framework application to organizational diagnostics.")
        ]
    },
    {
        "filename": "accenture_interview_guide.pdf",
        "title": "Accenture — Advanced Technology & Cloud Guide",
        "company": "Accenture",
        "domain": "Digital Transformation & Cloud Delivery",
        "roles": ["Associate Software Engineer", "Advanced ASE"],
        "source_doc": "accenture_interview_guide.md",
        "provenance_summary": {"reported": 3, "practice": 0, "official": 0},
        "overview": "Accenture evaluates modern DevOps practices, Infrastructure as Code, Agile delivery, cloud fundamentals, and machine learning model evaluation.",
        "interview_format": "Round 1: Cognitive Assessment & Coding Round -> Round 2: Technical Interview -> Round 3: HR / Cultural Alignment.",
        "sample_topics": [
            ("DevOps & CI/CD", "reported", "Infrastructure as Code (Terraform) and zero-downtime deployment pipelines."),
            ("AI & Data Science", "reported", "Precision, Recall, and PR-AUC in imbalanced fraud detection workloads."),
            ("Agile Methodologies", "reported", "Scrum ceremonies and continuous sprint retrospective improvement.")
        ]
    },
    {
        "filename": "cybersecurity_guide.pdf",
        "title": "NFSU Core Cybersecurity & VAPT Subject Guide",
        "company": None,
        "domain": "Cybersecurity & DFIS",
        "roles": ["Security Analyst", "Penetration Tester", "Application Security Engineer"],
        "source_doc": "cybersecurity_guide.md",
        "provenance_summary": {"official": 6, "practice": 1, "reported": 0},
        "overview": "Comprehensive preparation on Web Application Security (OWASP Top 10), Cryptography, Network Defense, Digital Forensics (DFIR), and Zero Trust Architecture.",
        "interview_format": "Technical domain interviews, hands-on CTF scenarios, and code vulnerability review exercises.",
        "sample_topics": [
            ("SQL Injection", "official", "Parser AST alteration and parameterized queries compilation defense."),
            ("SSRF & Cloud Metadata", "official", "Exploitation of 169.254.169.254 and IMDSv2 token mitigation."),
            ("Password Security", "official", "Why SHA-256 is inadequate for passwords; Argon2, bcrypt, and scrypt KDFs."),
            ("Zero Trust", "official", "NIST SP 800-207 microsegmentation and continuous session verification.")
        ]
    },
    {
        "filename": "soc_siem_ir_guide.pdf",
        "title": "NFSU SOC Operations, SIEM & Incident Response Guide",
        "company": None,
        "domain": "SOC Operations & Threat Intelligence",
        "roles": ["SOC Analyst (L1/L2)", "Incident Responder"],
        "source_doc": "soc_siem_ir_guide.md",
        "provenance_summary": {"official": 3, "practice": 0, "reported": 0},
        "overview": "Guidelines for Security Operations Centers: Log aggregation, SIEM correlation rules, incident response lifecycle, and phishing artifact extraction.",
        "interview_format": "Scenario-based incident triage interviews, log analysis simulations, and playbook walk-throughs.",
        "sample_topics": [
            ("NIST IR Lifecycle", "official", "Preparation, Detection/Analysis, Containment/Eradication, and Lessons Learned."),
            ("SIEM Correlation", "official", "Brute-force detection via Windows Event ID 4625 & 4624 thresholds."),
            ("Phishing Triage", "official", "SPF, DKIM, DMARC alignment and email header artifact extraction.")
        ]
    },
    {
        "filename": "networking_guide.pdf",
        "title": "Networking, TCP/IP & Systems Architecture Guide",
        "company": None,
        "domain": "Computer Networks & Systems",
        "roles": ["Network Engineer", "Systems Architect", "Cloud Associate"],
        "source_doc": "networking_guide.md",
        "provenance_summary": {"official": 4, "practice": 0, "reported": 0},
        "overview": "Covers TCP/IP protocol suite, DNSSEC resolution, container kernel isolation (namespaces & cgroups), and concurrency paradigms.",
        "interview_format": "Protocols, packet analysis, handshake steps, and OS virtualization mechanisms.",
        "sample_topics": [
            ("TCP Handshake", "official", "SYN flood vulnerability and stateless cryptographic SYN cookie mitigation."),
            ("DNS Resolution", "official", "Recursive resolution flow and DNSSEC cryptographic signature chains."),
            ("Docker Isolation", "official", "Linux Namespaces (view isolation) and cgroups (resource limits).")
        ]
    },
    {
        "filename": "dsa_algorithms_guide.pdf",
        "title": "Data Structures & Algorithmic Problem Solving Guide",
        "company": None,
        "domain": "Data Structures & Algorithms",
        "roles": ["Software Development Engineer", "Backend Developer"],
        "source_doc": "dsa_algorithms_guide.md",
        "provenance_summary": {"practice": 4, "reported": 0, "official": 0},
        "overview": "Curated solutions for essential coding patterns: Two Pointers, Sliding Window, Binary Search Trees, Heaps, and Dynamic Programming.",
        "interview_format": "Live coding, time and space complexity analysis, and edge-case handling.",
        "sample_topics": [
            ("Two Pointers / 3Sum", "practice", "Sorted array two-pointer technique avoiding duplicate triplets in O(N^2)."),
            ("Sliding Window", "practice", "Longest Substring Without Repeating Characters using hash map tracking in O(N)."),
            ("0/1 Knapsack", "practice", "Optimal substructure, 2D recurrence, and 1D reverse space optimization in O(W).")
        ]
    },
    {
        "filename": "dbms_sql_guide.pdf",
        "title": "Database Management Systems & SQL Query Design Guide",
        "company": None,
        "domain": "Database Engineering",
        "roles": ["Database Administrator", "Backend Engineer"],
        "source_doc": "dbms_sql_guide.md",
        "provenance_summary": {"practice": 2, "reported": 0, "official": 0},
        "overview": "Explains relational schema design, Normalization (1NF through BCNF), B+ Tree indexing mechanics, and query optimization.",
        "interview_format": "SQL queries, schema design, index performance tuning, and normalization drills.",
        "sample_topics": [
            ("B+ Tree Indexing", "practice", "Why relational engines choose high fan-out B+ Trees for disk I/O and range scans."),
            ("Normalization", "practice", "3NF vs BCNF superkey requirements and non-loss functional decompositions.")
        ]
    },
    {
        "filename": "ai_machine_learning_guide.pdf",
        "title": "AI, Machine Learning & LLM Security Guide",
        "company": None,
        "domain": "Artificial Intelligence & Data Science",
        "roles": ["Machine Learning Engineer", "Data Scientist", "AI Security Specialist"],
        "source_doc": "ai_machine_learning_guide.md",
        "provenance_summary": {"official": 1, "practice": 1, "reported": 0},
        "overview": "Fundamentals of supervised learning, regularization (L1/L2), Transformer self-attention, and OWASP Top 10 for LLM security.",
        "interview_format": "Mathematical derivations, model evaluation, and LLM safety guardrails.",
        "sample_topics": [
            ("Regularization", "practice", "Mathematical proof of Lasso weight sparsity and Ridge weight shrinkage."),
            ("Transformers & GenAI", "official", "Scaled Dot-Product attention formula and Prompt Injection defenses.")
        ]
    },
    {
        "filename": "hr_behavioral_guide.pdf",
        "title": "NFSU HR, Behavioral & Placement Procedures Guide",
        "company": None,
        "domain": "Career Development & HR",
        "roles": ["All Campus Applicants"],
        "source_doc": "hr_behavioral_guide.md",
        "provenance_summary": {"official": 2, "practice": 2, "reported": 0},
        "overview": "Mastering the STAR method for behavioral interviews, self-introductions, answering weaknesses, and understanding NFSU placement policies.",
        "interview_format": "Personal interviews, cultural fit, and placement policy compliance.",
        "sample_topics": [
            ("Elevator Pitch", "practice", "Present, Past, Future, and Hook framework for technical students."),
            ("NFSU Policies", "official", "CDC registration rules, CGPA eligibility, and One-Student-One-Job policy."),
            ("Drive Stages", "official", "Step-by-step drive sequence from JNF release to offer acceptance.")
        ]
    }
]


class Command(BaseCommand):
    help = "Generates reproducible PDF interview guides from structured sources and writes manifest.json"

    def handle(self, *args, **options):
        project_root = Path(settings.PROJECT_ROOT)
        docs_dir = project_root / 'docs' / 'chatbot' / 'knowledge'
        guides_source_dir = docs_dir / 'guides_source'
        output_pdf_dir = docs_dir / 'interview_guides'

        guides_source_dir.mkdir(parents=True, exist_ok=True)
        output_pdf_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "title": "NFSU Interview Preparation Knowledge Guides Manifest",
            "last_generated": datetime.now().isoformat(),
            "total_documents": len(GUIDES_DATA),
            "generated_by": "generate_pdfs management command",
            "documents": []
        }

        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#1E3A8A'),
            alignment=TA_CENTER
        )
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#4B5563'),
            alignment=TA_CENTER
        )
        h2_style = ParagraphStyle(
            'CustomH2',
            parent=styles['Heading2'],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#1E3A8A'),
            spaceBefore=8,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor('#1F2937')
        )
        table_text = ParagraphStyle(
            'TableText',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11.5
        )

        for doc in GUIDES_DATA:
            pdf_path = output_pdf_dir / doc["filename"]
            md_path = guides_source_dir / doc["source_doc"]

            # 1. Write Markdown source file for maintainability
            md_content = f"""# {doc['title']}

**Company:** {doc['company'] or 'General Technical Domain'}  
**Domain:** {doc['domain']}  
**Target Roles:** {', '.join(doc['roles'])}  
**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}  

## Overview
{doc['overview']}

## Reported Interview Format
{doc['interview_format']}

## Key Questions & Topics
"""
            for topic, prov, desc in doc["sample_topics"]:
                md_content += f"- **{topic}** `[{prov.upper()}]`: {desc}\n"

            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            # 2. Build ReportLab PDF
            pdf_doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=letter,
                rightMargin=40,
                leftMargin=40,
                topMargin=40,
                bottomMargin=40
            )

            story = []

            # Header Banner
            story.append(Paragraph(doc["title"], title_style))
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"NFSU Career Development Centre (CDC) — Official Knowledge Resource | {doc['domain']}",
                subtitle_style
            ))
            story.append(Spacer(1, 8))
            story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceBefore=2, spaceAfter=8))

            # Metadata Table
            meta_data = [
                [Paragraph("<b>Target Entity:</b>", table_text), Paragraph(doc["company"] or "All Eligible Branches", table_text),
                 Paragraph("<b>Domain:</b>", table_text), Paragraph(doc["domain"], table_text)],
                [Paragraph("<b>Roles:</b>", table_text), Paragraph(", ".join(doc["roles"]), table_text),
                 Paragraph("<b>Provenance:</b>", table_text), Paragraph(str(doc["provenance_summary"]), table_text)]
            ]
            t = Table(meta_data, colWidths=[80, 180, 70, 190])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))

            # Section: Overview
            story.append(Paragraph("1. Preparation Overview", h2_style))
            story.append(Paragraph(doc["overview"], body_style))
            story.append(Spacer(1, 8))

            # Section: Format
            story.append(Paragraph("2. Selection Stages & Interview Format", h2_style))
            story.append(Paragraph(doc["interview_format"], body_style))
            story.append(Spacer(1, 8))

            # Section: Key Focus Questions
            story.append(Paragraph("3. Curated Question Bank & Conceptual Drills", h2_style))
            
            q_table_data = [[
                Paragraph("<b>Topic</b>", table_text),
                Paragraph("<b>Provenance</b>", table_text),
                Paragraph("<b>Model Focus & Concepts</b>", table_text)
            ]]
            for topic, prov, desc in doc["sample_topics"]:
                prov_color = "#047857" if prov == "official" else ("#1D4ED8" if prov == "reported" else "#B45309")
                q_table_data.append([
                    Paragraph(f"<b>{topic}</b>", table_text),
                    Paragraph(f"<font color='{prov_color}'><b>[{prov.upper()}]</b></font>", table_text),
                    Paragraph(desc, table_text)
                ])

            qt = Table(q_table_data, colWidths=[120, 80, 320])
            qt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E5E7EB')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#9CA3AF')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(qt)
            story.append(Spacer(1, 12))

            # Footer notice
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#9CA3AF'), spaceBefore=6, spaceAfter=6))
            story.append(Paragraph(
                "<i>Source Note: Practice material is compiled for pedagogical preparedness. Official trademarks belong to their respective corporate entities. Verify actual drive criteria with NFSU CDC notifications.</i>",
                subtitle_style
            ))

            pdf_doc.build(story)

            manifest["documents"].append({
                "filename": doc["filename"],
                "source_file": doc["source_doc"],
                "title": doc["title"],
                "company": doc["company"],
                "domain": doc["domain"],
                "roles": doc["roles"],
                "provenance_summary": doc["provenance_summary"],
                "generated_at": datetime.now().isoformat()
            })

            self.stdout.write(self.style.SUCCESS(f"Generated PDF guide: {doc['filename']}"))

        # Write manifest.json
        manifest_path = docs_dir / 'manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f"Successfully built all {len(GUIDES_DATA)} PDF guides and wrote manifest to {manifest_path}"
        ))
