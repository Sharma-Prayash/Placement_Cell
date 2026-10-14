# NFSU Placement Management System

A secure, policy-driven placement platform for the NFSU Placement Cell (session 2026–27), covering M.Tech. CS, M.Tech. AIDS, B.Tech.–M.Tech. CSE, M.Sc. CS and M.Sc. DFIS.

**Stack:** Django 5.2 + Django REST Framework, React 18 + TypeScript (Vite), SQLite for local runs or PostgreSQL 16.

## Quick start

You need Python 3.11+ and Node.js 18+. All Python packages install into `backend/.venv` and all JavaScript packages into `frontend/node_modules`; nothing is installed system-wide.

**macOS / Linux**
```bash
./setup.sh      # creates backend/.venv, generates secrets in backend/.env, migrates, seeds demo data, installs frontend
./run.sh        # backend on :8000, frontend on http://localhost:5173
./test.sh       # 40 backend tests + frontend type-check
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
powershell -ExecutionPolicy Bypass -File run.ps1
```

The setup script prints the demo password for every seeded account (it is stored as `SEED_PASSWORD` in `backend/.env`). Emails, including recruiter activation links, are printed in the backend terminal.

| Role | Sign in as | What to try |
|---|---|---|
| Public | no account | Overview page, public bulletin, "Recruit at NFSU" form |
| Student | `NFSU26-DFIS-001` (any Placement ID) | Drives with verdicts, apply, accept or decline offers, join a talk |
| Recruiter | `REC-DEMO1` … `REC-DEMO5` | Filter candidates by CGPA, skills and category; shortlist; post a talk |
| Placement Administrator | `admin.mehta`, `admin.shah` | Propose with one admin, approve with the other |
| Placement Officer | `officer.desai` | Verify recruiter requests, moderate the bulletin |
| Course Coordinator | `coord.dfis`, `coord.aids` | Approve changes for their own programme only |

To use the Python environment manually: `source backend/.venv/bin/activate` (Windows: `backend\.venv\Scripts\activate`).

## What is in the box

- **Student database** with create, update and archive through maker-checker. Placement IDs are immutable, duplicates are detected on ID, email and mobile, and records can be filtered by programme and batch. Exports are audited CSV.
- **Policy engine** (`backend/apps/policy/engine.py`). It hard-blocks registration and cut-off failures plus the agreed offer-type rules. Category switching and absenteeism are advisory flags that recruiters see and decide on. One setting turns switching into hard blocks.
- **Offer management** for I, F and I+F offers, including PPO, joining and NOC. Each offer is its own row with a status history, so nothing is overwritten. The acceptance deadline is the earlier of 24 hours and the company's window.
- **Recruiter side:**
  - a public interest form (rate-limited, with a honeypot), plus admin-added recruiters
  - Recruiter IDs with single-use activation links
  - candidate statistics and filters, with contacts masked until shortlisting
- **Common bulletin** for placement updates, Placement Cell events, and talks, tests and interviews. Recruiter posts wait for approval. Meeting links come only through the join endpoint, which records attendance.
- **Reports** at university and programme level. Unique placed students and total offers are counted separately, and stipend is reported separately from CTC.
- **Public overview** with sanitised aggregates. Any group under 5 students is suppressed.
- **Security:**
  - Argon2, account lockout, a sign-in code emailed to the official address (or TOTP), 15-minute idle sessions, CSRF protection, CSP
  - encrypted columns with a blind index
  - a hash-chained audit log
  - maker-checker enforced by a database constraint

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): components, data model, request flow
- [docs/POLICY.md](docs/POLICY.md): every rule, team decisions, open questions
- [docs/SECURITY.md](docs/SECURITY.md): each control and the test that proves it
- [docs/DEMO.md](docs/DEMO.md): an 8-minute judge demo script
- [CLAUDE.md](CLAUDE.md): working notes for Claude Code and new teammates

## Useful commands (from `backend/` with the venv active)

```bash
python manage.py test tests                 # full suite
python manage.py test tests.test_policy_engine
python manage.py run_jobs                   # expire offers, close drives, flag absentees (schedule with cron)
python manage.py verify_audit_chain         # detects any edited or deleted audit row
python manage.py seed_demo --reset          # wipe and reseed (SQLite only)
```

Backups: `BACKUP_PASSPHRASE=… scripts/backup.sh`, then restore-drill with `scripts/restore.sh <file>`.
