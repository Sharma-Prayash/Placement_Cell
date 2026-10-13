"""Search over the approved interview-preparation bank. ORM only; nothing user-typed reaches SQL.

Matching is on whole words (never substrings, so "are" does not match "hardware"), rarer words weigh more
(IDF), and an entry is returned only when at least half of the question's meaningful words appear in its
title, tags or question. A weak match is worse than none: the caller then says the bank does not cover it.
"""
import math
import re

from .models import KnowledgeEntry

STOPWORDS = set("""
a an the is are was were be been being am do does did done to for of in on at by with from about as into over under
and or but so if then than also just only very really too not no yes and/or i me my mine we us our you your yours he she
it its they them their this that these those there here what which who whom whose when where why how can could would
should will shall may might must have has had having get got give gave tell explain show describe define list ask asked
please kindly some any all each every other more most much many few one two something anything thing things way ways
good best better important common top basic basics know learn study understand need want help like let use using used
make example examples interview interviews question questions prepare preparation prep practice practise round rounds
topic topics related regarding around today now im i'm difference between vs versus work works working concept concepts
nfsu university student students placement placements job jobs career careers company companies
""".split())

# Words students use for a domain, mapped to text that appears in KnowledgeEntry.domain or .topic.
DOMAIN_SYNONYMS = {
    "cyber": "cybersecurity", "cybersecurity": "cybersecurity", "security": "cybersecurity", "soc": "soc", "siem": "siem",
    "vapt": "penetration", "pentest": "penetration", "forensic": "forensics", "forensics": "forensics", "dfis": "forensics",
    "dsa": "dsa", "algorithm": "dsa", "algorithms": "dsa", "dbms": "dbms", "sql": "dbms", "database": "dbms",
    "databases": "dbms", "network": "networking", "networking": "networking", "os": "operating systems",
    "linux": "linux", "ai": "ai & data science", "ml": "ai & data science", "crypto": "cryptography",
    "cryptography": "cryptography", "hr": "hr & behavioral", "behavioural": "hr & behavioral", "behavioral": "hr & behavioral",
    "devops": "devops", "cloud": "cloud", "docker": "devops", "java": "java", "python": "python", "oop": "oop",
}
# Multi-word subjects a student types, folded to one domain word so "machine learning" does not match "virtual machine".
PHRASES = {
    "machine learning": "ml", "deep learning": "ml", "data science": "ai", "artificial intelligence": "ai",
    "data structures": "dsa", "data structure": "dsa", "operating systems": "os", "operating system": "os",
    "digital forensics": "forensics", "cyber security": "cybersecurity", "information security": "cybersecurity",
}
WORD = re.compile(r"[a-z0-9][a-z0-9+#]*")


def _fold(text: str) -> str:
    text = text.lower()
    for phrase, word in PHRASES.items():
        text = re.sub(rf"\b{phrase}\b", word, text)
    return text


def _singular(w: str) -> str:
    """Very light stemming, applied the same way to questions and entries: passwords -> password, hashing -> hash."""
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) >= 7 and w.endswith("ing"):
        w = w[:-3]
    return w


def words(text: str) -> set[str]:
    out = set()
    for w in WORD.findall(text.lower()):
        out.add(w)
        out.add(_singular(w))
    return out


def terms(text: str) -> list[str]:
    """Meaningful words of a question, in order, without duplicates."""
    seen = []
    for w in WORD.findall(_fold(text)):
        w = _singular(w)
        if len(w) >= 2 and w not in STOPWORDS and w not in seen:
            seen.append(w)
    return seen


def detect_company(text: str) -> str:
    """Company named in the question, matched as a whole word against companies that actually have entries."""
    q = words(text)
    names = KnowledgeEntry.objects.filter(status="approved").exclude(company="").values_list("company", flat=True).distinct()
    for name in sorted(names, key=len, reverse=True):
        first = name.lower().split()[0]
        if first in q:
            return name
    return ""


def detect_domain(text: str) -> str:
    q = words(_fold(text))
    for word, domain in DOMAIN_SYNONYMS.items():
        if word in q:
            return domain
    return ""


def search(text: str, top_k: int = 3) -> list[KnowledgeEntry]:
    """Best approved entries for the question, or [] when nothing matches well enough. Pending and revoked
    entries are never returned."""
    entries = list(KnowledgeEntry.objects.filter(status=KnowledgeEntry.Status.APPROVED))
    qterms = terms(text)
    if not entries or not qterms:
        return []
    company = detect_company(text)
    lowered = text.lower()

    index = []
    for e in entries:
        strong = words(" ".join([e.company, e.domain, e.topic, e.subtopic, e.question, " ".join(map(str, e.tags or []))]))
        index.append((e, strong, words(e.answer)))
    n = len(entries)
    idf = {t: math.log((n + 1) / (sum(t in s or t in w for _, s, w in index) + 0.5)) for t in qterms}

    scored = []
    for e, strong, weak in index:
        covered = {t for t in qterms if t in strong}
        if company and e.company == company:
            covered.add(company.lower().split()[0])
        in_domain = False
        for t in qterms:  # a domain word ("dbms", "cyber") counts when the entry is in that domain
            d = DOMAIN_SYNONYMS.get(t)
            if d and (d in e.domain.lower() or d in e.topic.lower()):
                covered.add(t)
                in_domain = True
        for tag in e.tags or []:  # multi-word tags ("tell me about yourself") match as a phrase
            tag = str(tag).lower()
            if " " in tag and re.search(rf"\b{re.escape(tag)}\b", lowered):
                covered.update(t for t in qterms if t in words(tag))
        if not covered or len(covered & set(qterms) | ({company.lower().split()[0]} if company else set())) < 0.5 * len(qterms):
            continue
        score = sum(idf[t] * (3.0 if t in covered else 0.5 if t in weak else 0.0) for t in qterms)
        if in_domain:
            score += 3.0  # "cybersecurity questions" should rank security entries above an HR entry that mentions it
        if company and e.company == company:
            score += 4.0
        elif not company and not e.company:
            score += 0.5  # no company asked: prefer general entries over another company's
        scored.append((len(covered), score, e.entry_id, e))

    if not scored:
        return []
    # Only entries that match as many of the question's words as the best one; "SQL injection" should not
    # also return a prompt-injection entry that matches "injection" alone.
    most = max(c for c, _, _, _ in scored)
    scored = sorted((x for x in scored if x[0] == most), key=lambda x: (-x[1], x[2]))
    return [e for _, _, _, e in scored[:top_k]]


def citation(e: KnowledgeEntry) -> dict:
    return {
        "id": e.entry_id, "title": f"{e.company or e.domain}: {e.topic}", "company": e.company or None, "domain": e.domain,
        "topic": e.topic, "difficulty": e.difficulty, "provenance": e.provenance, "source_title": e.source_title,
        "source_url": e.source_url if e.source_url.startswith("https://") else "",
    }
