# Security controls

Each control in the problem statement maps to code and to at least one test in `backend/tests/test_security.py`. Run `./test.sh`.

| Area | Implementation | Test |
|---|---|---|
| Passwords | Argon2id hasher, minimum length 12, common and numeric password validators | `test_password_hash_is_argon2_and_never_returned` |
| Brute force | 5 failures lock the account for 15 min; per-IP login rate limit; generic error text | `test_brute_force_locks_account` |
| MFA | TOTP (pyotp); required for staff and recruiters when `REQUIRE_STAFF_MFA=true` | `test_staff_login_without_mfa_code_fails` |
| Sessions | HttpOnly, SameSite=Lax (Secure in production); 15 min idle timeout; key rotated on login; server-side logout | `test_session_cookie_is_httponly_and_dead_after_logout` |
| CSRF | Django CSRF on every state change, including anonymous login and the public form | `test_login_requires_csrf_token` |
| SQL injection | ORM-only bound parameters; no raw SQL in application code | `test_sql_injection_in_search_and_login` |
| XSS | bleach allow-list on rich text, plain text elsewhere; React escapes output; CSP `default-src 'none'` on the API | `test_xss_in_bulletin_is_stripped` |
| IDOR | Student data resolved from the session; other students' and companies' objects return 404 | `test_student_cannot_respond_to_another_students_offer`, `test_recruiter_cannot_see_other_company_drive…` |
| Mass assignment | Student PATCH rejects any field outside skills and consents with 400, and the attempt is audited | `test_mass_assignment_of_status_or_package_is_rejected_and_logged` |
| Switching bypass | Policy engine runs in services (apply, propose, approve, accept), not only in the UI | `test_blocked_offer_cannot_be_created_through_any_path`, `test_student_apply_blocked_server_side` |
| Maker-checker | DB `CHECK approver <> proposer`, a service guard, coordinators scoped to their course, expiry | `MakerCheckerTests` |
| Integrity | Immutable Placement ID; uniqueness on ID, email and mobile (blind index); serializer validation | `test_placement_id_is_immutable` |
| Audit log | Append-only model; SHA-256 hash chain; advisory lock on Postgres; `verify_audit_chain` | `test_editing_a_row_breaks_the_chain` |
| Encryption at rest | Fernet column encryption for mobile, meeting links and MFA secrets; sealed values in change requests; never logged in plaintext | `test_mobile_is_ciphertext_in_database`, `SensitiveDataInApprovalsTests` |
| Encryption in transit | Production: Nginx TLS, HSTS, SSL redirect, Secure cookies (`DJANGO_DEBUG=false`) | `manage.py check --deploy` in CI |
| Recruiter privacy | Contacts masked until shortlisted; only the category band is shown, never another company's CTC or name; talent pool limited to consenting students; resumes only for own applicants, with each view logged | `test_contacts_revealed_after_shortlisting`, `test_talent_pool_excludes_non_consenting_students` |
| Public data | Aggregates only; any figure based on fewer than 5 students is suppressed; top packages only for opted-in students | `test_public_stats_suppress_small_cells_and_hold_no_personal_data` |
| Meeting links | Encrypted; absent from every list API; issued only by `/join` after eligibility and time-window checks | `test_meeting_link_only_from_join_endpoint` |
| Rate limiting | Public form: 5 per hour per IP and 3 per day per email. Also login, activation and resume views | `test_public_recruiter_form_limited` |
| Uploads | PDF magic-byte check, 2 MB cap, random filenames, private storage outside the web root | `test_upload_rejects_non_pdf` |
| Email | Constant subjects; CR/LF rejected in names; activation links instead of passwords | `test_email_header_injection_rejected` |
| Exports | Staff only, reason required, row cap, watermark line, formula-injection escaping, audited | covered by the role permission tests |
| Backups | `scripts/backup.sh` (AES-256, PBKDF2), `scripts/restore.sh` restore drill with row-count comparison | manual drill |
| Dependencies | Pinned versions; `pip-audit` and `npm audit` in CI; secrets only in `.env` (gitignored) | `.github/workflows/ci.yml` |
| Retention | Archive instead of delete; consent flags; the retention schedule is a policy decision for the Placement Cell (see limitations) | — |

## Known limitations

- Attendance proves the student clicked through the platform link, not that they stayed. Mitigations would be a check-in code read out by the recruiter, or reconciliation against an attendee list.
- Rate limits use the local-memory cache unless `REDIS_URL` is set. With several workers, set Redis.
- The model-level append-only rule can be bypassed by anyone with direct DB access, which is why the hash chain and the Postgres REVOKE exist.
- `seed_demo` uses one shared password for convenience. Never use it outside a demo.
- There is no automated retention or deletion job yet. The Placement Cell needs to define the retention period first.
- The prototype uses fictional data. Real student data needs institutional approval and a hardened deployment.
