"""U.J., the placement assistant: routes a question to the right source of truth and words the answer.

Where each kind of answer comes from:
- personal  -> the signed-in student's own record, resolved from the session, and verdicts from
               policy.services.evaluate_for(). Never anyone else's record, never an LLM.
- placement -> public_report() (small groups already suppressed), PolicyConfig and the public bulletin.
- prep      -> the approved question bank; Gemini may reword it if configured, and may answer general
               prep questions the bank does not cover, labelled as AI-generated (see llm.py).
The assistant only reads. It cannot apply, accept or change anything; those stay in the normal screens.
"""
import re
import time

from django.utils import timezone

from apps.analytics.services import public_report
from apps.bulletin.models import Post
from apps.placements.models import Application, Drive, Offer
from apps.policy.models import PolicyConfig
from apps.policy.services import current_category, evaluate_for, load_config, placement_status
from apps.students.models import Student
from core.permissions import STUDENT, role_of

from . import knowledge, llm
from .models import AssistantQuery

MAX_LEN = 1000

STATUS_TEXT = {"unplaced": "not placed yet", "internship_only": "internship only", "fte_only": "full-time (FTE) only",
               "internship_plus_fte": "internship and full-time"}
OFFER_TEXT = {"I": "Internship", "F": "Full-time", "IF": "Internship + PPO/FTE"}
DECISION_TEXT = {"ALLOW": "Clear", "FLAG": "Review", "BLOCK": "Blocked"}

PERSONAL = re.compile(
    r"\b(my|mine|am i|can i|do i|have i|did i|i am|i'm|i have|should i)\b.*\b(status|eligib\w*|offers?|apply|applied|"
    r"applications?|drives?|category|placed|placement|blocked|deadlines?|accept\w*|decline|cgpa|record|verdict|chances?)\b"
    r"|\bwhy (was|am|is) (i|my)\b.*\b(blocked|ineligible|not eligible|flagged)\b",
)
HELP = re.compile(r"^\s*(hi|hello|hey|namaste|help|menu|start|what can you do|what do you do)\b")
SMALLTALK = re.compile(r"^\s*(thanks?|thank you|thx|ty|ok(ay)?|cool|great|nice|awesome|got it|bye|goodbye|see you|"
                       r"good (morning|afternoon|evening|night)|how are you)\b")
# Questions about U.J. itself, including attempts to make it reveal or drop its instructions.
META = re.compile(
    r"\b(are you (a |an |the )?(bot|robot|human|real|person|ai|gemini|chatgpt|gpt|llm|internal|machine|program)|"
    r"who (are|made|built|created|developed|trained) you|what are you|what (model|llm|ai) (is this|are you|do you use)|"
    r"which (model|llm|ai)|your (name|model|creator|instructions|prompt|rules)|gemini|chatgpt|openai|"
    r"system prompt|ignore (all |the |your )?(previous|prior|above|earlier)|jailbreak|developer mode|pretend (to be|you are))\b"
)
# "Do it for me" requests. The assistant cannot act, so these get an explanation and the right screen.
ACTION_VERBS = (r"apply|accept|decline|reject|withdraw|submit|upload|update|change|edit|modify|delete|remove|cancel|"
                r"register|enrol+|book|reschedule|schedule|send|email|shortlist|select|approve|reset|mark")
ACTION = re.compile(
    rf"^\s*(please |pls |kindly )?({ACTION_VERBS})\b"
    rf"|\b(can|could|will|would) you\s+(please\s+)?({ACTION_VERBS})\b"
    r"|\b(for me|on my behalf)\b"
)
HOW_TO = re.compile(r"^\s*how (do|can|should|would|to) (i |we |students? |one )?(apply|accept|decline|register|join|get placed|"
                    r"respond|withdraw|upload)\b")
# Words that mean "practise with me". Other questions ("what is SQL injection") also go to the question bank
# unless they are about placement itself.
PREP_STRONG = re.compile(r"\b(interviews?|questions?|mock|coding round|hr round|behaviou?ral|practi[cs]e)\b")
PLACEMENT = re.compile(
    r"\b(placement process|process|procedure|steps?|stages?|rules?|polic(y|ies)|categor(y|ies)|switch\w*|statistics|stats|"
    r"average|median|highest|packages?|ctc|lpa|salar(y|ies)|stipends?|recruiters?|companies|organisations|organizations|"
    r"deadline|acceptance|absen\w*|attendance|register\w*|activate|events?|talks?|ppt|bulletin|upcoming|schedule|"
    r"recruit at nfsu|hire|hiring|placed|placement rate|placements?)\b"
)


def classify(text: str) -> str:
    t = text.lower().strip()
    if HELP.search(t) and len(t) < 40:
        return "help"
    if SMALLTALK.search(t) and len(t) < 40:
        return "smalltalk"
    if META.search(t):
        return "meta"
    if ACTION.search(t):
        return "action"
    if HOW_TO.search(t) and not re.search(r"\b(my|mine)\b", t):
        return "placement"  # "how do I accept an offer" asks about the process, not about the student's record
    if PERSONAL.search(t):
        return "personal"
    if PREP_STRONG.search(t):
        return "prep"
    if PLACEMENT.search(t):
        return "placement"
    return "prep"  # a company name or a technical topic ("what is SQL injection")


def suggestions(role: str | None) -> list[str]:
    if role == STUDENT:
        return ["Which open drives can I apply to?", "What is my placement status?", "When do my offers expire?",
                "Cybersecurity interview questions"]
    return ["How does placement work at NFSU?", "Explain the category rules", "Show this session's placement statistics",
            "Cybersecurity interview questions"]


def _reply(answer, intent, mode, status="answered", sources=None, drives=None):
    return {"answer": answer, "intent": intent, "mode": mode, "status": status, "sources": sources or [], "drives": drives or []}


def lpa(v):
    return "—" if v is None else f"₹{float(v):g} LPA"


# ------------------------------------------------------------------ personal (students only)
def _drive_rows(student, text):
    applied = dict(Application.objects.filter(student=student).values_list("drive_id", "status"))
    drives = (Drive.objects.filter(status="open", application_deadline__gt=timezone.now()).select_related("company")
              .order_by("application_deadline"))
    rows = []
    for d in drives:
        if student.course not in d.eligible_courses:
            continue
        v = evaluate_for(student, d)  # rule 8: the engine decides, the assistant only reports
        rows.append({"id": d.id, "company": d.company.name, "title": d.title, "offer_type": d.offer_type,
                     "package": lpa(d.ctc_lpa) if d.ctc_lpa else money(d.stipend_amount, d.stipend_period),
                     "closes": d.application_deadline.isoformat(), "decision": v.decision,
                     "reasons": [r for r in v.to_dict()["reasons"] if r["severity"] != "info"],
                     "application_status": applied.get(d.id)})
    asked = set(re.findall(r"[a-z0-9]+", text.lower()))
    # "kavach" names Kavach Cyber Labs: match the company's distinctive first word, or its full name.
    named = [r for r in rows if r["company"].lower() in text.lower()
             or (len(first := r["company"].lower().split()[0]) >= 4 and first in asked)]
    return named or rows


def answer_personal(user, text):
    if role_of(user) is None:
        return _reply("I can answer questions about your own placement once you sign in with your Placement ID. "
                      "Until then I can explain the placement process, the rules and this session's statistics.",
                      "personal", "sign_in", "sign_in_required")
    if role_of(user) != STUDENT:
        return _reply("Personal placement answers are only for students, about their own record. Staff and recruiters "
                      "can use their dashboards; I can still explain the rules or the statistics.", "personal", "refused", "not_available")
    try:
        student = user.student  # resolved from the session, never from the question text
    except Student.DoesNotExist:
        return _reply("Your account is not linked to a student record yet. Contact the Placement Cell.", "personal", "refused", "not_available")

    t = text.lower()
    status = placement_status(student)
    category = current_category(student)

    if re.search(r"\b(offers?|deadlines?|accept\w*|decline|expire\w*)\b", t):
        offers = Offer.objects.filter(student=student).select_related("company").order_by("-offer_date")
        if not offers:
            return _reply("You have no offers recorded yet. Offers appear here once the Placement Cell records them.",
                          "personal", "student_record")
        lines = ["**Your offers**"]
        for o in offers:
            pkg = lpa(o.ctc_lpa) if o.offer_type != "I" else money(o.stipend_amount, o.stipend_period)
            line = f"- **{o.company.name}**, {OFFER_TEXT[o.offer_type]}, {pkg}: {o.acceptance}"
            if o.acceptance == "pending":
                line += f". Respond by {timezone.localtime(o.acceptance_deadline):%d %b, %I:%M %p}"
            lines.append(line)
        lines.append("Accept or decline on the My placement page. An offer you do not answer in time expires.")
        return _reply("\n".join(lines), "personal", "student_record")

    rows = _drive_rows(student, t)
    clear = sum(r["decision"] == "ALLOW" for r in rows)
    review = sum(r["decision"] == "FLAG" for r in rows)
    blocked = sum(r["decision"] == "BLOCK" for r in rows)
    lines = [
        f"**{student.name}**, here is what the placement policy says right now.",
        f"- Placement status: **{STATUS_TEXT.get(status, status)}**",
        f"- Current category: **{category or 'none (no accepted full-time offer)'}**",
        f"- Registration: {student.get_registration_status_display().lower()}, eligibility: {student.get_eligibility_status_display().lower()}",
        f"- CGPA: {student.cgpa}, backlogs: {student.backlogs}",
    ]
    if rows:
        lines.append(f"- Open drives for your programme: **{len(rows)}** ({clear} clear, {review} for review, {blocked} blocked)")
        lines.append("Each drive below shows the policy engine's verdict and the reason in full.")
    else:
        lines.append("- There are no open drives for your programme right now.")
    return _reply("\n".join(lines), "personal", "policy_engine", drives=rows)


# ------------------------------------------------------------------ general placement information
def answer_placement(text):
    t = text.lower()
    if re.search(r"\b(statistics|stats|average|median|highest|packages?|ctc|lpa|salar(y|ies)|stipends?|pay|placement rate|how many)\b", t):
        r = public_report()
        k = r["min_cell_size"]
        shown = lambda n: f"{n}" if n is not None else f"fewer than {k} (not published)"
        lines = []
        if knowledge.detect_company(t) or any(c.lower() in t for c in r["past_recruiters"]):
            lines.append("Packages are not published per company. These are the session-wide figures; the package for a "
                         "specific drive is shown on the drive itself to eligible students.")
        lines += [f"**Placement statistics, session {r['session']}**",
                 f"- Students placed: {shown(r['students_placed'])}",
                 f"- Offers made: {shown(r['offers_made'])}",
                 f"- Recruiting organisations: {r['recruiters']}"]
        if r["fte_ctc_lpa"]:
            f = r["fte_ctc_lpa"]
            lines.append(f"- Full-time packages: median {lpa(f['median'])}, average {lpa(f['average'])}, highest {lpa(f['highest'])}")
        else:
            lines.append("- Full-time packages: not enough accepted offers yet to publish")
        for c in r["by_course"]:
            rate = f"{c['placement_rate']}% placed" if c["placement_rate"] is not None else "not published (small group)"
            lines.append(f"- {c['course']}: {rate}")
        lines.append(f"Figures from fewer than {k} students are withheld so no one can be identified.")
        return _reply("\n".join(lines), "placement", "placement_data", sources=[_official("Public placement statistics", "/")])

    if re.search(r"\b(recruiters?|companies|organisations|organizations|hire|hiring|who recruit\w*)\b", t) and "recruit at" not in t:
        names = public_report()["past_recruiters"]
        body = ("**Organisations that recruited this session**\n" + "\n".join(f"- {n}" for n in names)) if names else \
            "The first drives of the session are still under way, so no organisation is listed yet."
        return _reply(body + "\nOrganisations can register through Recruit at NFSU; the Placement Cell verifies each one.",
                      "placement", "placement_data", sources=[_official("Recruiting organisations", "/")])

    if re.search(r"\b(categor(y|ies)|switch\w*|a\+|upgrade|dream)\b", t):
        c = load_config()
        mode = "blocked" if c.enforce_switching else "flagged for the recruiter to review"
        body = (f"**Offer categories** are bands on annual CTC: **A+** from {lpa(c.a_plus_min)}, **A** from {lpa(c.a_min)} "
                f"up to {lpa(c.a_plus_min)}, **B** from {lpa(c.b_min)} up to {lpa(c.a_min)}, and **C** below {lpa(c.b_min)}. "
                "Your category is your highest accepted full-time offer.\n"
                "- A+: the guideline says you leave the placement process\n"
                "- A: you may move only to an A+ drive\n"
                f"- B: the new package must be at least {float(c.b_multiplier):g} × your current one\n"
                "- C: you may move only to a higher category\n"
                f"Moves that break these rules are currently {mode}. Hard rules (registration, eligibility, programme, "
                "CGPA and backlog cut-offs, repeat offer types) always block.")
        return _reply(body, "placement", "placement_data", sources=[_official("Placement policy settings", "/")])

    if re.search(r"\b(deadline|acceptance|accept|expire\w*|respond)\b", t):
        hours = PolicyConfig.current().acceptance_hours
        return _reply(f"After an offer is recorded you have **{hours} hours** to accept or decline it on the My placement page "
                      "(less if the company set a shorter window). Offers you do not answer in time expire automatically.",
                      "placement", "placement_data", sources=[_official("Placement policy settings", "/")])

    if re.search(r"\b(absen\w*|attendance|miss\w*|talks?|ppt|events?|upcoming|schedule|bulletin)\b", t):
        n = PolicyConfig.current().absence_exclusion_drives
        posts = Post.objects.filter(status="approved", visibility="public", starts_at__gte=timezone.now()).order_by("starts_at")[:5]
        lines = ["Talks, tests and interviews are announced on the placement bulletin. Students join them through the platform, "
                 "which records attendance.",
                 f"If you applied to a drive and miss its talk, test or interview, you are flagged for the next **{n} drives** "
                 "open to your programme, unless the Placement Cell excuses the absence."]
        if posts:
            lines.append("**Coming up**")
            lines += [f"- {p.title}, {timezone.localtime(p.starts_at):%d %b, %I:%M %p}" for p in posts]
        return _reply("\n".join(lines), "placement", "placement_data", sources=[_official("Placement bulletin", "/")])

    if re.search(r"\b(recruit at nfsu|register (my|our) (company|organi[sz]ation)|we want to hire|as a recruiter)\b", t):
        return _reply("**Recruiting at NFSU**\n- Send the Recruit at NFSU form with your roles and dates\n"
                      "- The Placement Cell verifies the organisation\n- You receive a Recruiter ID and a single-use link to set a password\n"
                      "- Drives are scheduled with the Cell; you then see applicants, shortlist and announce talks",
                      "placement", "placement_data", sources=[_official("Recruit at NFSU", "/recruit")])

    return _reply("**How placement works at NFSU**\n"
                  "- **Register:** the Placement Cell creates your record and emails a single-use activation link\n"
                  "- **Drive opens:** a verified recruiter's drive lists eligible programmes, cut-offs and the package\n"
                  "- **Policy check:** before you apply, the policy engine shows Clear, Review or Blocked with the reason\n"
                  "- **Apply:** one click; recruiters see your profile and resume only if you consented\n"
                  "- **Talks, tests and interviews:** joined through the platform so attendance is recorded\n"
                  "- **Offer:** recorded by one staff member and approved by another\n"
                  "- **Accept and join:** respond within the acceptance window on the My placement page",
                  "placement", "placement_data", sources=[_official("How placement works", "/")])


def _official(title, path):
    """Citation for live NFSU data. `path` is a page of this site, not an external link."""
    return {"id": f"nfsu:{title.lower().replace(' ', '-')}", "title": title, "provenance": "official", "source_url": "",
            "path": path, "company": None, "domain": "NFSU"}


def money(amount, period="month"):
    return f"₹{amount:,} / {period or 'month'}" if amount else "—"


# ------------------------------------------------------------------ interview preparation
def answer_prep(text):
    entries = knowledge.search(text)
    if not entries:
        # Not in the reviewed bank: Gemini may answer a general prep question, clearly labelled as AI-generated.
        generated = llm.answer_open(text)
        if generated:
            return _reply(generated, "prep", "gemini_open")
        return _reply("I don't have a reviewed answer for that, and I won't guess. I can help with placement at NFSU "
                      "(process, rules, statistics, your own drives and offers) and with interview preparation in "
                      "cybersecurity, digital forensics, data structures, DBMS, networking, operating systems, cryptography, "
                      "AI and data science, and HR rounds, or for companies such as Amazon or Deloitte.",
                      "prep", "question_bank", "insufficient_evidence")
    sources = [knowledge.citation(e) for e in entries]
    worded = llm.reword(text, entries)
    if worded:
        return _reply(worded, "prep", "gemini", sources=sources)
    parts = []
    for i, e in enumerate(entries, 1):
        parts.append(f"**{i}. {e.question}**\n{e.answer}\n_{e.get_provenance_display()} · {e.company or e.domain} · {e.difficulty}_")
    return _reply("\n\n".join(parts), "prep", "question_bank", sources=sources)


HELP_TEXT = ("I am **U.J.**, the placement assistant. I can:\n"
             "- explain how placement works, the category rules and deadlines\n"
             "- show this session's published statistics and recruiters\n"
             "- practise interview questions by topic or company, with sources\n"
             "- for signed-in students: check your status, offers and which open drives you can apply to\n"
             "I only read information. Applying and accepting offers stay on your dashboard.")


def answer_meta():
    """Honest answer about what U.J. is and whether Gemini is actually in use right now."""
    last = llm.last_status()
    if not llm.is_enabled():
        ai = "Gemini is switched off, so every answer comes from NFSU's own data or the reviewed question bank."
    elif last and not last["ok"]:
        ai = ("Gemini is configured but is not responding right now, so answers are coming straight from NFSU's data "
              "and the reviewed question bank.")
    elif not last:
        ai = ("Gemini is configured, but I have not reached it since the server started, so I can't confirm it is working. "
              "Only answers labelled Gemini or AI-generated were written by it; everything else comes from NFSU's data or "
              "the reviewed question bank.")
    else:
        ai = ("For interview-prep questions I may use Google Gemini to explain question-bank entries, or to answer prep "
              "questions the bank does not cover. Those answers are labelled Gemini or AI-generated.")
    return _reply("I am **U.J.**, the NFSU Training and Placement Cell's assistant: a program built into this portal, "
                  "not a person.\n"
                  f"- {ai}\n"
                  "- Answers about you come only from your own record and the placement policy engine, and never go to Gemini.\n"
                  "- Every answer is labelled with where it came from.\n"
                  "I keep to placement and interview preparation, and I don't change my instructions on request.",
                  "meta", "meta")


def smalltalk(message: str) -> str:
    t = message.lower()
    if re.search(r"\b(thanks?|thank you|thx|ty)\b", t):
        return "You're welcome. Ask me about placement or interview preparation whenever you need."
    if re.search(r"\b(bye|goodbye|see you)\b", t):
        return "Goodbye, and good luck with your placements."
    if "how are you" in t:
        return "I'm working fine, thanks. What would you like to know about placement or interview preparation?"
    if re.search(r"\b(ok(ay)?|cool|great|nice|awesome|got it)\b", t):
        return "Glad that helped. Anything else?"
    return "Hello. Ask me about placement at NFSU or interview preparation."


def answer_action(user, text):
    """U.J. never acts. Say so, point to the screen that does it, and for students show the relevant facts."""
    t = text.lower()
    role = role_of(user)
    if re.search(r"\b(resume|cv|profile|skills?|consent)\b", t):
        where = "the Profile and consent section of My placement"
    elif re.search(r"\b(offers?|accept|decline)\b", t):
        where = "the Offers section of My placement"
    elif re.search(r"\b(apply|drives?|applications?|withdraw)\b", t):
        where = "Open drives on My placement, where the Apply button checks the policy first"
    elif re.search(r"\b(talks?|interviews?|tests?|book|schedule|reschedule|slot)\b", t):
        where = "the Bulletin: talks, tests and interviews are scheduled by recruiters and the Placement Cell, and you join them there"
    elif re.search(r"\b(company|organi[sz]ation|recruit)\b", t):
        where = "the Recruit at NFSU form"
    else:
        where = "your dashboard, or the Placement Cell for account changes"
    intro = f"I can't do that for you: I only read information, so nothing changes without you. Use {where}."
    if role == STUDENT and re.search(r"\b(apply|drives?|offers?|accept|decline)\b", t):
        result = answer_personal(user, text)
        result["answer"] = intro + "\n\n" + result["answer"]
        result.update(intent="action", mode="read_only")
        return result
    if role is None and where.startswith(("Open drives", "the Offers", "the Profile")):
        intro += " Sign in with your Placement ID first."
    return _reply(intro, "action", "read_only")


def answer(user, message: str) -> dict:
    start = time.monotonic()
    intent = classify(message)
    if intent == "help":
        result = _reply(HELP_TEXT, "help", "help")
    elif intent == "smalltalk":
        result = _reply(smalltalk(message), "help", "help")
    elif intent == "meta":
        result = answer_meta()
    elif intent == "action":
        result = answer_action(user, message)
    elif intent == "personal":
        result = answer_personal(user, message)
    elif intent == "placement":
        result = answer_placement(message)
    else:
        result = answer_prep(message)
    result["suggestions"] = suggestions(role_of(user))
    AssistantQuery.objects.create(role=role_of(user) or "public", intent=result["intent"], mode=result["mode"],
                                  status=result["status"], source_ids=[s["id"] for s in result["sources"]],
                                  latency_ms=int((time.monotonic() - start) * 1000))
    return result
