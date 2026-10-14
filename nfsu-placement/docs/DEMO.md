# Demo script (about 8 minutes)

Open three browser profiles or windows (admin, recruiter, student) and keep the backend terminal visible: emails print there.
Every sign-in asks for a 6-digit code after the password; copy it from the "Your NFSU placement portal sign-in code" email in that terminal. Show once that a wrong code says how many tries are left, and that the code from one browser does not work in another.

1. **Public overview** (signed out). Point out the stats: unique students placed vs offers made, CTC and stipend shown separately, and suppressed cells (`<5`). Then show the public bulletin.
2. **Recruit at NFSU.** Submit the form. Submit it again from the same browser six times: the sixth is refused with 429. Show the notification email in the terminal.
3. **Officer** (`officer.desai`): Console → Recruiters shows every recruiter account and whether it has been activated. To add one directly, an admin fills in "Add a recruiter directly" and an officer approves it in Approvals (nobody approves their own). Then verify the public request: the terminal shows the Recruiter ID and the single-use activation link. Open the link, set a password and sign in as the new recruiter.
4. **Recruiter** (`REC-DEMO1`): open the Candidates page, then:
   - filter by CGPA 8+ and the skill "forensics"
   - show the verdict tags and their reasons (a student holding an FTE offer is blocked from another FTE role)
   - note the contacts are masked; shortlist one candidate and the contacts appear
   - post a pre-placement talk, which shows "waiting for approval"
5. **Officer**: open the Bulletin queue and publish the talk.
6. **Student** (`NFSU26-DFIS-001`): open the drives list, where each drive has a verdict with plain-language reasons. Then:
   - apply to an allowed drive
   - try the blocked one through the API with `curl` or the devtools console: it is refused with the same reason
   - open the bulletin and join the talk; attendance is recorded and the link opens
7. **Tamper attempts** as the student, from the devtools console:
   ```js
   const t = document.cookie.match(/csrftoken=([^;]+)/)[1];
   fetch("/api/student/me", {method: "PATCH", headers: {"Content-Type": "application/json", "X-CSRFToken": t},
     body: JSON.stringify({placement_status: "fte_only", cgpa: "10"})}).then(r => r.json()).then(console.log)
   fetch("/api/staff/students/2").then(r => console.log(r.status))   // 403
   ```
   Show the `security.mass_assignment_blocked` entry in the admin's audit log.
8. **Maker-checker.** As `admin.mehta`, open Students, edit a student's eligibility and add an offer. Approvals shows "You cannot approve this one". Switch to `admin.shah` and approve; the diff, the policy verdict and the audit entries show both steps.
9. **Audit tamper.** Click "Verify the hash chain" to show it intact. Then edit a row directly:
   ```bash
   cd backend
   .venv/bin/python -c "import sqlite3; c=sqlite3.connect('db.sqlite3'); c.execute(\"UPDATE audit_auditlog SET action='nothing.to.see' WHERE id=3\"); c.commit()"
   ```
   Verify again: the chain is reported broken at record 3.
10. **Run tests live**: `./test.sh` passes 40 tests (the policy case table plus the attack tests).

Run `python manage.py run_jobs` after a talk's end time to show absent applicants getting flagged. Only applicants are flagged, not every eligible student.
