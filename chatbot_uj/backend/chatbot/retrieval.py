import re
from typing import List, Dict, Any, Optional
from django.db.models import Q
from chatbot.models import QABankEntry


class KnowledgeRetrievalService:
    """
    Search and ranking engine for interview preparation Q&A records.
    Filters by verification status, ranks by keyword and entity relevance,
    and returns source citations with provenance metadata.
    """

    STOPWORDS = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'about', 'like', 'through', 'over', 'before', 'after',
        'between', 'under', 'from', 'up', 'down', 'and', 'but', 'or', 'so', 'me',
        'you', 'he', 'she', 'it', 'we', 'they', 'what', 'how', 'why', 'when', 'where',
        'can', 'could', 'would', 'should', 'tell', 'explain', 'give', 'show', 'ask',
        'questions', 'question', 'interview', 'for', 'preparation', 'prep'
    }

    COMPANIES = ['jpmorgan', 'jpmorgan chase', 'amazon', 'microsoft', 'google', 'deloitte', 'accenture']

    DOMAINS = [
        'cybersecurity', 'dfis', 'forensics', 'dsa', 'algorithms', 'dbms', 'sql',
        'networking', 'operating systems', 'linux', 'ai', 'machine learning',
        'deep learning', 'soc', 'siem', 'incident response', 'vapt', 'cryptography',
        'oop', 'python', 'java', 'devops', 'cloud', 'hr', 'behavioral'
    ]

    def extract_keywords(self, query: str) -> List[str]:
        """Extract clean alphanumeric search terms without common stopwords."""
        words = re.findall(r'[a-zA-Z0-9_\+\#]+', query.lower())
        keywords = [w for w in words if len(w) >= 2 and w not in self.STOPWORDS]
        return keywords

    def search(
        self,
        query: str,
        company_filter: Optional[str] = None,
        domain_filter: Optional[str] = None,
        difficulty_filter: Optional[str] = None,
        top_k: int = 3,
        min_score: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieves relevant approved knowledge entries based on query terms and filters.
        Never returns revoked or rejected entries.
        """
        query_lower = query.lower()
        keywords = self.extract_keywords(query)

        # Detect company intent from query if not passed explicitly
        detected_company = company_filter
        if not detected_company:
            for c in self.COMPANIES:
                if c in query_lower:
                    detected_company = c
                    break

        # Base queryset: only active and approved or valid practice questions
        # Strict rule: Revoked or rejected entries are NEVER returned
        queryset = QABankEntry.objects.filter(
            is_active=True,
            verification_status='approved'
        )

        if detected_company:
            if 'jpmorgan' in detected_company.lower():
                queryset = queryset.filter(company__icontains='JPMorgan')
            elif 'amazon' in detected_company.lower():
                queryset = queryset.filter(company__icontains='Amazon')
            elif 'microsoft' in detected_company.lower():
                queryset = queryset.filter(company__icontains='Microsoft')
            elif 'google' in detected_company.lower():
                queryset = queryset.filter(company__icontains='Google')
            elif 'deloitte' in detected_company.lower():
                queryset = queryset.filter(company__icontains='Deloitte')
            elif 'accenture' in detected_company.lower():
                queryset = queryset.filter(company__icontains='Accenture')
            else:
                queryset = queryset.filter(company__icontains=detected_company)

        if domain_filter:
            queryset = queryset.filter(domain__icontains=domain_filter)

        if difficulty_filter:
            queryset = queryset.filter(difficulty__iexact=difficulty_filter)

        candidates = list(queryset)

        # If strict company filter yielded no results, fall back to general domain entries if appropriate
        if not candidates and detected_company:
            fallback_qs = QABankEntry.objects.filter(
                is_active=True,
                verification_status='approved'
            )
            # Find domain matches in query
            domain_matched = False
            for d in self.DOMAINS:
                if d in query_lower:
                    fallback_qs = fallback_qs.filter(
                        Q(domain__icontains=d) | Q(topic__icontains=d)
                    )
                    domain_matched = True
                    break
            if domain_matched:
                candidates = list(fallback_qs)

        # Score candidates
        scored_entries = []
        for entry in candidates:
            score = 0
            haystack_topic = (entry.topic + ' ' + entry.subtopic).lower()
            haystack_q = entry.question.lower()
            haystack_a = entry.answer.lower()
            haystack_domain = entry.domain.lower()
            tags = [t.lower() for t in entry.tags] if entry.tags else []

            # Company match boost
            if detected_company and entry.company and detected_company in entry.company.lower():
                score += 15

            # Domain match boost
            for d in self.DOMAINS:
                if d in query_lower and d in haystack_domain:
                    score += 12

            # Keyword matching
            for kw in keywords:
                if kw in tags:
                    score += 8
                if kw in haystack_topic:
                    score += 6
                if kw in haystack_q:
                    score += 4
                if kw in haystack_a:
                    score += 1

            if score >= min_score or (detected_company and score > 0):
                scored_entries.append((score, entry))

        # Sort descending by score
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, entry in scored_entries[:top_k]:
            results.append({
                'entry_id': entry.entry_id,
                'company': entry.company,
                'domain': entry.domain,
                'role': entry.role,
                'topic': entry.topic,
                'subtopic': entry.subtopic,
                'question': entry.question,
                'answer': entry.answer,
                'difficulty': entry.difficulty,
                'provenance': entry.provenance,
                'source_title': entry.source_title,
                'source_url': entry.source_url,
                'research_date': entry.research_date,
                'verification_status': entry.verification_status,
                'reviewer_name': entry.reviewer_name,
                'pdf_document': entry.pdf_document,
                'tags': entry.tags,
                'relevance_score': score,
            })

        return results
