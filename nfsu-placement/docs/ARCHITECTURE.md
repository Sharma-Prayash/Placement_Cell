# Architecture

## Components

```
Browser (React SPA, Vite dev server :5173)
   │  same-origin /api/* (Vite proxy in dev, Nginx in production)
   ▼
Django + DRF (:8000) ── views (thin) ──► services (all writes) ──► models / PostgreSQL or SQLite
                              │                    │
                              │                    ├─► policy.engine.evaluate()  (pure function)
                              │                    └─► audit.log()                (hash chain)
                              └─► permission classes (deny by default, one per endpoint)
Background jobs: `manage.py run_jobs` (cron or Celery beat in production)
```

Rules that keep it secure by construction:

- **Views never write placement records directly.** Student and offer changes from staff go through `approvals.services.propose()` and `approve()`. Students have exactly two write paths: their own safe profile fields, and accepting or declining their own offer.
- **The policy engine runs server-side** at every decision point: student apply, offer proposal, offer approval (re-checked at apply time), offer acceptance, the join-event eligibility check, and the recruiter candidate view.
- **Identity always comes from the session.** A student's record is `request.user.student`, never an ID taken from the URL or body.

## Backend apps (`backend/apps/`)

| App | Owns |
|---|---|
| `accounts` | User (one table, five roles), login with lockout and an emailed sign-in code (or TOTP), activation links, demo seed |
| `audit` | Append-only hash-chained `AuditLog`, `verify_audit_chain` |
| `approvals` | `ChangeRequest` maker-checker, handlers per entity and action, sealing of sensitive fields |
| `students` | `Student` (incl. CGPA, backlogs, 10th/12th, skills, consents), self-service, staff list, export, resumes |
| `recruiters` | `Company`, public `RecruiterRequest`, `Recruiter` (Recruiter ID = login) |
| `placements` | `Drive`, `Application` (candidate = applicant), `Offer`, `OfferStatusEvent`, background jobs |
| `policy` | `engine.py` (pure), `services.py` (model adapters), `PolicyConfig`, `PolicyFlag` |
| `bulletin` | `Post` (common bulletin), `Attendance`, join endpoint |
| `analytics` | Internal report and sanitised public report |

`core/` holds the shared security code: permission classes, the encrypted field and blind index, rate limiting, sanitisers, the security headers middleware, and the safe exception handler.

## Data model (main tables)

| Table | Key fields | Notes |
|---|---|---|
| `accounts_user` | username (login ID), role, coordinator_course, mfa_secret (encrypted), failed_attempts, locked_until | Students: username = Placement ID. Recruiters: username = Recruiter ID |
| `students_student` | placement_id (unique, immutable), email (unique), mobile (encrypted) + mobile_index (HMAC, unique), course, batch, registration/eligibility status, cgpa, backlogs, skills, consents, archived_at | Placement status and category are **derived**, never stored |
| `recruiters_company` | name, website, verified_at | Category is **not** stored per company |
| `placements_drive` | company, offer_type I/F/IF, ctc_lpa, stipend, eligible_courses, min_cgpa, max_backlogs, deadlines | Category derived from the drive's CTC |
| `placements_application` | drive, student, status, policy_decision, policy_reasons | One per student per drive |
| `placements_offer` | student, drive, company, type, ctc/stipend, ppo, acceptance, joining, deadline, source, noc | New event = new row; status changes logged in `OfferStatusEvent` |
| `approvals_changerequest` | entity, action, before, proposed (sensitive values sealed), proposer, approver, status, expires_at | `CHECK approver <> proposer` |
| `policy_policyflag` | student, rule_code, explanation, drives_remaining, status | Absenteeism flags count down as drives close |
| `bulletin_post` / `bulletin_attendance` | kind, visibility, status, meeting_url (encrypted) / status present-absent-excused | Recruiter posts start as pending |
| `audit_auditlog` | ts, actor, role, action, entity, before, after, ip, prev_hash, hash | Model refuses update and delete; Postgres REVOKE in `scripts/postgres_hardening.sql` |

**Derived placement status** (from accepted offers):
- no accepted offers → unplaced
- only I → internship only
- only F → FTE only
- I+F, or both I and F → internship + FTE

## Frontend (`frontend/src/`)

- `lib/api.ts`: the fetch wrapper. It sends the CSRF header; the session cookie is HttpOnly, so no tokens are stored in JS.
- `lib/auth.tsx`: holds the current user.
- `pages/`:
  - `Home` (public overview)
  - `Login`, `Activate`
  - `Recruit` (public form)
  - `Bulletin`
  - `Student`
  - `Recruiter` (filters and decisions)
  - `Staff` (console tabs: approvals, students, offers, drives, recruiters, bulletin queue, flags, reports, audit, policy)
- Route guards in `App.tsx` exist for navigation only; the server enforces every rule.

## Production deployment notes

Put Nginx in front with TLS and serve `frontend/dist` as static files. Proxy `/api` to gunicorn with `proxy_set_header X-Real-IP $remote_addr`, list Nginx's address in `TRUSTED_PROXIES`, and set `DJANGO_DEBUG=false`. That enables HSTS, secure cookies and the SSL redirect. Also use `DB_ENGINE=postgres`, set `REDIS_URL` so rate limits are shared across workers, configure SMTP so sign-in codes reach users' official mailboxes, schedule `run_jobs` every 5 minutes, and run nightly `scripts/backup.sh`.
