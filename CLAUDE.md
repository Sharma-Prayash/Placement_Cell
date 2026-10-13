# CLAUDE.md

Working notes for Claude Code (and any new teammate) on the NFSU Placement Management System. Read this before changing code.

## What this project is

A hackathon prototype for the NFSU Placement Cell, session 2026–27. It is a Django REST API (`backend/`) and a React + TypeScript SPA (`frontend/`). The judges grade policy enforcement and security as much as features, so **never trade a security property for convenience**.

## Commands

Python always runs from the project's virtual environment at `backend/.venv`. Do not install packages globally and do not use the system `python` for project commands.

```bash
./setup.sh                                   # first time: venv, .env with secrets, migrate, seed, npm install
./run.sh                                     # backend :8000 + frontend :5173 (Vite proxies /api)
./test.sh                                    # backend tests + frontend type-check; must stay green

cd backend
.venv/bin/python manage.py test tests                        # all backend tests
.venv/bin/python manage.py test tests.test_policy_engine     # policy case table only
.venv/bin/python manage.py makemigrations <app>              # after any model change; commit the migration
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo --reset                 # wipe and reseed local SQLite
.venv/bin/python manage.py run_jobs                          # deadline expiry, drive closing, absentee flags
.venv/bin/python manage.py verify_audit_chain
.venv/bin/pip install <pkg>==<exact version> && .venv/bin/pip freeze | grep -i <pkg>   # then pin it in requirements.txt

cd frontend
npm run dev | npm run build | npx tsc -b --noEmit
```

On Windows, use `backend\.venv\Scripts\python.exe` instead of `.venv/bin/python`.

`backend/.env` holds the secrets and is gitignored. If it is missing, run `./setup.sh`; never hard-code keys. Emails print to the Django console in development.

## Layout

```
backend/
  config/settings.py   all security settings; secrets from env
  config/urls.py       every endpoint in one file, grouped by audience (public, student, recruiter, staff)
  core/                permissions.py (deny-by-default role classes), fields.py (EncryptedTextField, blind_index),
                       ratelimit.py, sanitize.py, middleware.py (CSP etc.), exceptions.py
  apps/accounts        User with roles; login, lockout, MFA, activation; management/commands/seed_demo.py
  apps/audit           AuditLog (append-only, hash chain); services.log(); verify_audit_chain
  apps/approvals       ChangeRequest + services.propose/approve/reject + HANDLERS registry
  apps/students        Student model, self-service, staff list, export, resumes
  apps/recruiters      Company, RecruiterRequest (public form), Recruiter; services.create_recruiter
  apps/placements      Drive, Application, Offer, OfferStatusEvent; jobs.py; student/staff/recruiter views
  apps/policy          engine.py (PURE), services.py (model adapters), PolicyConfig, PolicyFlag
  apps/bulletin        Post (common bulletin), Attendance, join endpoint
  apps/analytics       internal_report() and public_report()
  tests/               test_policy_engine.py (case table), test_security.py (attack tests), factories.py
frontend/src/
  lib/api.ts           fetch wrapper; sends X-CSRFToken; never store tokens in JS
  lib/auth.tsx         current user context
  pages/               Home (public), Login, Activate, Recruit, Bulletin, Student, Recruiter, Staff (console tabs)
  components/ui.tsx    Verdict (evidence tag), Category, Reasons, Errors, Section
docs/                  ARCHITECTURE, POLICY, SECURITY, DEMO
```

## Roles and vocabulary

- Roles are `admin` (Placement Administrator), `officer` (Placement Officer), `coordinator` (Course Coordinator, scoped to `coordinator_course`), `recruiter` and `student`. **Public** means anonymous. A **candidate** is a student with an `Application` to a drive; it is not a role.
- Programme codes: `MTECH_CS`, `MTECH_AIDS`, `BTECH_MTECH_CSE`, `MSC_CS`, `MSC_DFIS`.
- Offer types: `I` (internship only), `F` (FTE only), `IF` (internship + PPO/FTE).
- The login ID is `User.username`: the Placement ID for students, the Recruiter ID (`REC-XXXXXX`) for recruiters.

## Non-negotiable rules

1. **Every endpoint names its permission class** from `core/permissions.py`. Do not rely on the DRF default, and never use `AllowAny` except on public endpoints that also set `authentication_classes = []` and a rate limit.
2. **Staff changes to students, offers, attendance excuses, flag waivers and admin-added recruiters go through maker-checker.** Call `approvals.services.propose(...)`. To support a new change type, add a handler to `HANDLERS` in `apps/approvals/services.py` with `prepare()`, which validates and returns `(before, proposed, course, preview)`, and `apply()`, which runs inside the approval transaction. Never write these records directly from a view.
3. **Students have exactly two write paths:** `PATCH /api/student/me` (only fields in `SELF_EDITABLE`; anything else is a 400 plus an audit entry) and `POST /api/student/offers/<id>/respond`. Do not add student write paths to status, package, eligibility or placement data.
4. **Resolve the student from the session** with `own_student(request)`, never from a URL or body ID. Objects the caller may not see return **404, not 403**, so their existence is not revealed.
5. **Call `audit.log(actor, action, entity, entity_id, before, after, request)` in the same transaction as the change** for every write and every sensitive read (resume views, exports, candidate lists). Use dotted action names such as `offer.accepted` or `security.mass_assignment_blocked`. System jobs pass `actor=None`.
6. **Never put sensitive values in the audit log, change requests, logs or error messages in plaintext.** Today that means mobile numbers, meeting URLs and MFA secrets. Use `EncryptedTextField` for new sensitive columns, add the field to `SENSITIVE_FIELDS` in approvals, and use `redact()` for anything shown or logged.
7. **The policy engine stays pure.** `apps/policy/engine.py` imports nothing from Django. Add a rule as a `Reason(code, severity, message)` with severity `block`, `flag` or `info`, then add rows to the case table in `tests/test_policy_engine.py`. Thresholds belong in `PolicyConfig`, not in code. Messages are full sentences a student or recruiter can understand.
8. **Call the engine through `policy.services.evaluate_for()` wherever a decision is made** (apply, propose, approve, accept, join). The UI only displays verdicts; it never decides.
9. **Recruiters see statistics, not secrets:** the category band only (never another company's name or exact CTC), contacts only after shortlisting, and only consenting students in the talent pool.
10. **Public endpoints return aggregates only.** Any figure computed from fewer than `PUBLIC_STATS_MIN_CELL` students must be `None`.
11. **No raw SQL** in application code; use ORM bound parameters. Rich text goes through `core.sanitize.clean_html`, everything else through `clean_text`. Validate on the server even if the form validates. User input never reaches email headers.
12. **Every new endpoint ships with a test**, including at least one negative test (wrong role, another user's object, tampered field). `./test.sh` must stay green.
13. **Pin exact dependency versions** at least two weeks old. Never commit `.env`, `db.sqlite3`, `private_media/` or `.venv/`.

## Frontend conventions

- Use `api()` from `lib/api.ts` for every request. It handles CSRF and errors; show errors with `<Errors lines={errorLines(e)} />`.
- Never use `dangerouslySetInnerHTML`. Bulletin bodies are sanitised server-side and still rendered as text.
- Keep the design tokens in `styles.css` (navy ink, cool paper, three verdict colours). The evidence-tag `Verdict` is the one decorative element; do not add others.
- Copy should be plain, in sentence case, and name the action ("Send for approval", "Publish"). Error text says what happened and how to fix it.

## Things that are deliberately not built yet

- Candidate chatbot (E3 in the team plan)
- Celery: jobs run via `manage.py run_jobs` on cron
- Nginx/TLS deployment files
- Automated retention/deletion
- Encoding the official NFSU guideline PDF: see the open questions in `docs/POLICY.md`

Ask the team before implementing any of these, because each one touches the security model.

## Before you finish a change

Run `./test.sh`. Also run `makemigrations --check --dry-run` if you touched models. If you changed a rule or a control, update `docs/POLICY.md` or `docs/SECURITY.md`. Explain in the PR how the change keeps rules 1–11 intact.
