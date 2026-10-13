# Placement policy rules

The engine is `backend/apps/policy/engine.py`. It is a pure function that takes a student, a drive, the student's offers, open flags and the config, and returns a decision (`ALLOW`, `FLAG` or `BLOCK`) with reasons. Every reason is a sentence shown to students, recruiters and staff. The rule table is tested in `backend/tests/test_policy_engine.py`.

## Team decisions (October 2026)

1. **Recruiters decide; the system informs.** Academic statistics (CGPA, backlogs, 10th/12th, skills), current category band, offer types held and policy notes are shown to recruiters as data with filters. Only the rules below marked *hard* block anything.
2. **Internship-only students** cannot take another internship-only role, but **can** take FTE-only and Internship + PPO/FTE roles.
3. **Candidates** are students who applied to a drive. They are not a separate role.
4. The official NFSU guideline PDF is **not** encoded yet; thresholds are configurable when it is.

## Hard rules (always BLOCK)

| Code | Rule |
|---|---|
| `NOT_REGISTERED` | The student must be registered for the session |
| `INELIGIBLE` | The Placement Cell has marked the student ineligible |
| `COURSE_NOT_ELIGIBLE` | The drive is not open to the student's programme |
| `CGPA_BELOW_CUTOFF` / `BACKLOGS_ABOVE_LIMIT` | The company's cut-offs |
| `OFFER_TYPE_I_REPEAT` | Holds an accepted I offer, and the drive is I |
| `OFFER_TYPE_F_REPEAT` | Holds an accepted F offer, and the drive is F |
| `OFFER_TYPE_IF_LOCK` | Holds an accepted I+F offer; any I, F or I+F drive at another organisation is blocked |

## Advisory rules (FLAG, or BLOCK when `enforce_switching` is on)

Categories are half-open bands on annual CTC, defined per drive: **A+** is 16 LPA or more, **A** is [10, 16), **B** is [6, 10), and **C** is below 6 LPA. Internship-only drives have no category. The student's current category is the highest FTE/I+F CTC among accepted offers.

| Code | Holding | New drive must be |
|---|---|---|
| `SWITCH_A_PLUS_EXIT` | A+ | — (the guideline says A+ students leave the process) |
| `SWITCH_A_ONLY_TO_A_PLUS` | A | A+ |
| `SWITCH_B_MULTIPLIER` | B | at least 1.5 × the current CTC (exactly 1.5× passes) |
| `SWITCH_C_SAME_CATEGORY` | C | a higher category than C |
| `OFFER_TYPE_F_TO_IF` | F-only, and the drive is I+F | not covered by the agreed rules, so flagged for review |
| `ELIGIBILITY_PENDING` | eligibility still pending | — |
| `ABSENTEEISM` | missed a talk, test or interview of a drive they applied to | flagged for the next 3 drives open to their programme, unless excused |

Some notes on how the rules apply:

- Only **accepted** offers count as "held". Pending offers appear as information; declined and expired offers are ignored.
- An offer that came from the drive being evaluated is excluded, because it is the outcome of that drive.
- Switching rules compare FTE packages only. Internship-only drives skip them.

## Deadlines and jobs

The acceptance deadline is `offer_date + min(24 h, company window)`. Students accept or decline in their portal, and `run_jobs` marks overdue offers as expired. When an event ends, **only applicants** to its drive who did not join through the platform are marked absent. Staff can excuse an absence through maker-checker, which also waives the flag.

## Open questions to settle against the official guideline

- Whether a C → C move with a higher package is a valid switch
- How an F-only holder applying to an I+F drive should be treated
- Whether A+ students may still take internship-only roles
- Whether absenteeism should become a hard block
