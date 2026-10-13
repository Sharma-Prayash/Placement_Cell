import { FormEvent, useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { BarChart, Donut, Funnel, HBars, PackageRange, SERIES } from "../components/charts";
import { Icon } from "../components/icons";
import { Card, Category, Chip, Done, Empty, Errors, Kpi, Reasons, Section, Verdict } from "../components/ui";
import { api, ApiError, errorLines } from "../lib/api";
import { useAuth } from "../lib/auth";
import { COURSES, inr, lpa, OFFER_TYPES, STATUS, when } from "../lib/format";

/* Every change to a placement record goes through /staff/changes as a proposal.
   Nothing here writes a student or offer directly. */

function useLoad<T>(path: string, initial: T) {
  const [data, setData] = useState<T>(initial);
  const [err, setErr] = useState<string[]>([]);
  const load = useCallback(() => api<T>(path).then((d) => { setData(d); setErr([]); }).catch((e) => setErr(errorLines(e))), [path]);
  useEffect(() => { load(); }, [load]);
  return { data, err, load };
}

function useAction(after?: () => void) {
  const [err, setErr] = useState<string[]>([]);
  const [done, setDone] = useState("");
  const run = async (fn: () => Promise<unknown>, msg: string) => {
    setErr([]); setDone("");
    try { await fn(); setDone(msg); after?.(); return true; }
    catch (e) {
      const lines = errorLines(e);
      const policy = e instanceof ApiError ? (e.data.policy as any) : null;
      if (policy?.reasons) lines.push(...policy.reasons.filter((r: any) => r.severity === "block").map((r: any) => `Policy: ${r.message}`));
      setErr(lines); return false;
    }
  };
  return { err, done, run, feedback: <><Errors lines={err} /><Done text={done} /></> };
}

const propose = (entity: string, action: string, entity_id: unknown, data: unknown, reason: string) =>
  api("/staff/changes", { body: { entity, action, entity_id, data, reason } });

export default function Staff() {
  const { me } = useAuth();
  const isAdmin = me?.role === "admin";
  const adminOrOfficer = me?.role === "admin" || me?.role === "officer";
  return (
    <div className="console">
      <header className="banner" style={{ marginBottom: "1.25rem" }}>
        <span className="kpi-icon" style={{ background: "rgba(255,255,255,0.14)", color: "var(--gold)" }}><Icon name="grid" /></span>
        <div className="grow">
          <h1>Placement console</h1>
          <p>Every change to a student or offer is a proposal until a second person approves it.</p>
        </div>
        <span className="chip"><Icon name="user" />{me?.role}</span>
      </header>
      <nav className="tabs" aria-label="Console sections">
        <NavLink to="/staff/approvals"><Icon name="approve" />Approvals</NavLink>
        <NavLink to="/staff/reports"><Icon name="chart" />Reports</NavLink>
        <NavLink to="/staff/students"><Icon name="users" />Students</NavLink>
        <NavLink to="/staff/offers"><Icon name="trophy" />Offers</NavLink>
        <NavLink to="/staff/drives"><Icon name="briefcase" />Drives</NavLink>
        {adminOrOfficer && <NavLink to="/staff/recruiters"><Icon name="building" />Recruiters</NavLink>}
        {adminOrOfficer && <NavLink to="/staff/bulletin"><Icon name="megaphone" />Bulletin queue</NavLink>}
        <NavLink to="/staff/flags"><Icon name="flag" />Policy flags</NavLink>
        {adminOrOfficer && <NavLink to="/staff/audit"><Icon name="scroll" />Audit log</NavLink>}
        {isAdmin && <NavLink to="/staff/policy"><Icon name="sliders" />Policy settings</NavLink>}
      </nav>
      {me?.role === "coordinator" && <p className="fine">You see and approve records for {COURSES[me.coordinator_course ?? ""]} only.</p>}
      <Routes>
        <Route index element={<Navigate to="approvals" replace />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="students" element={<Students />} />
        <Route path="offers" element={<Offers />} />
        <Route path="drives" element={<Drives />} />
        <Route path="recruiters" element={<Recruiters />} />
        <Route path="bulletin" element={<BulletinQueue />} />
        <Route path="flags" element={<Flags />} />
        <Route path="reports" element={<Reports />} />
        <Route path="audit" element={<Audit />} />
        <Route path="policy" element={<PolicySettings />} />
      </Routes>
    </div>
  );
}

/* ---------------------------------------------------------------- approvals */
function Diff({ before, after }: { before: any; after: any }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]));
  return (
    <table className="diff"><tbody>
      {keys.map((k) => {
        const b = before?.[k], a = after?.[k];
        const changed = before && JSON.stringify(b) !== JSON.stringify(a) && a !== undefined;
        if (before && !changed) return null;
        return <tr key={k}><th>{k.replace(/_/g, " ")}</th>{before && <td className="was">{String(b ?? "—")}</td>}<td className="now">{String(a ?? "—")}</td></tr>;
      })}
    </tbody></table>
  );
}

function Approvals() {
  const [status, setStatus] = useState("pending");
  const { data, err, load } = useLoad<any[]>(`/staff/changes?status=${status}`, []);
  const a = useAction(load);
  const [notes, setNotes] = useState<Record<number, string>>({});
  return (
    <Section title="Changes waiting for a second person" aside={
      <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
        {["pending", "approved", "rejected", "expired"].map((s) => <option key={s}>{s}</option>)}
      </select>}>
      <Errors lines={err} />{a.feedback}
      {data.length === 0 ? <Empty>Nothing {status}. Proposals from colleagues appear here.</Empty> : (
        <ul className="cards">{data.map((c) => (
          <li key={c.id} className="change">
            <div className="drive-head">
              <div>
                <h3>{c.action} {c.entity}{c.entity_id && ` #${c.entity_id}`}</h3>
                <p className="muted small">Proposed by {c.proposer} {when(c.created_at)}{c.course && ` · ${COURSES[c.course]}`} · expires {when(c.expires_at)}</p>
              </div>
              {c.policy_preview && <Verdict decision={c.policy_preview.decision} />}
            </div>
            <p><strong>Reason:</strong> {c.reason}</p>
            <Diff before={c.before} after={c.proposed} />
            {c.policy_preview && <Reasons reasons={c.policy_preview.reasons} />}
            {c.status !== "pending" && <p className="muted small">{c.status} by {c.approver ?? "—"} {when(c.decided_at)} {c.decision_note && `: ${c.decision_note}`}</p>}
            {c.can_approve ? (
              <div className="row">
                <input placeholder="Note (required to reject)" value={notes[c.id] ?? ""} onChange={(e) => setNotes({ ...notes, [c.id]: e.target.value })} maxLength={300} />
                <button className="btn" onClick={() => a.run(() => api(`/staff/changes/${c.id}/approve`, { body: { note: notes[c.id] ?? "" } }), "Approved and applied.")}>Approve</button>
                <button className="btn-quiet" onClick={() => a.run(() => api(`/staff/changes/${c.id}/reject`, { body: { note: notes[c.id] ?? "" } }), "Rejected.")}>Reject</button>
              </div>
            ) : c.status === "pending" && <p className="muted small">You cannot approve this one: either you proposed it or it is outside your scope.</p>}
          </li>
        ))}</ul>
      )}
    </Section>
  );
}

/* ---------------------------------------------------------------- students */
const STUDENT_FIELDS: [string, string, string?][] = [
  ["name", "Full name"], ["email", "Email", "email"], ["mobile", "Mobile"], ["batch", "Batch (e.g. 2025-27)"],
  ["cgpa", "CGPA", "number"], ["backlogs", "Backlogs", "number"], ["tenth_percent", "10th %", "number"], ["twelfth_percent", "12th %", "number"],
  ["skills", "Skills"], ["remarks", "Remarks"],
];

function StudentForm({ student, onClose }: { student?: any; onClose: () => void }) {
  const [f, setF] = useState<Record<string, string>>(() => {
    const base: Record<string, string> = { placement_id: "", course: "MSC_CS", registration_status: "registered", eligibility_status: "pending" };
    if (student) for (const k of [...STUDENT_FIELDS.map((x) => x[0]), "course", "registration_status", "eligibility_status"]) base[k] = student[k] ?? "";
    return base;
  });
  const [reason, setReason] = useState("");
  const a = useAction();
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    let data: Record<string, string> = { ...f };
    if (student) {
      data = Object.fromEntries(Object.entries(f).filter(([k, v]) => String(student[k] ?? "") !== v));
      delete data.placement_id;
      if (!Object.keys(data).length) return a.run(async () => { throw new ApiError(400, { detail: "Change at least one field." }); }, "");
    }
    for (const k of ["tenth_percent", "twelfth_percent"]) if (data[k] === "") delete data[k];
    if (await a.run(() => propose("student", student ? "update" : "create", student?.id, data, reason), "Sent for approval. A colleague must approve it before it takes effect.")) setTimeout(onClose, 1200);
  };
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <form className="form two-col panel" onSubmit={submit}>
      <h3 className="span">{student ? `Propose changes to ${student.placement_id}` : "Propose a new student record"}</h3>
      {!student && <label>Placement ID<input value={f.placement_id} onChange={set("placement_id")} required pattern="[A-Z0-9\-]{4,20}" /></label>}
      {STUDENT_FIELDS.map(([k, l, t]) => <label key={k}>{l}<input type={t ?? "text"} step="0.01" value={f[k] ?? ""} onChange={set(k)} required={["name", "email", "mobile", "batch", "cgpa"].includes(k)} /></label>)}
      <label>Programme<select value={f.course} onChange={set("course")}>{Object.entries(COURSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label>Registration<select value={f.registration_status} onChange={set("registration_status")}><option value="registered">Registered</option><option value="deregistered">Deregistered</option><option value="not_registered">Not registered</option></select></label>
      <label>Eligibility<select value={f.eligibility_status} onChange={set("eligibility_status")}><option value="eligible">Eligible</option><option value="ineligible">Ineligible</option><option value="pending">Pending verification</option></select></label>
      <label className="span">Reason for the change (the approver sees this)<input value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} maxLength={300} /></label>
      <div className="span">{a.feedback}<div className="row"><button className="btn">Send for approval</button><button type="button" className="btn-quiet" onClick={onClose}>Cancel</button></div></div>
    </form>
  );
}

function OfferForm({ student, onClose }: { student: any; onClose: () => void }) {
  const drives = useLoad<any[]>("/staff/drives", []);
  const [f, setF] = useState({ drive: "", offer_date: new Date().toISOString().slice(0, 16), ppo_status: "na", source: "on_campus", noc_status: "na" });
  const [reason, setReason] = useState("");
  const a = useAction();
  const d = drives.data.find((x) => String(x.id) === f.drive);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!d) return;
    const data = { student: student.id, drive: d.id, company: d.company, offer_type: d.offer_type, ctc_lpa: d.ctc_lpa, stipend_amount: d.stipend_amount,
      stipend_period: d.stipend_period, ppo_status: f.ppo_status, offer_date: new Date(f.offer_date).toISOString(), source: f.source, noc_status: f.noc_status };
    if (await a.run(() => propose("offer", "create", null, data, reason), "Offer sent for approval. The policy engine checked it first.")) setTimeout(onClose, 1500);
  };
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <form className="form two-col panel" onSubmit={submit}>
      <h3 className="span">Record an offer for {student.name}</h3>
      <label className="span">Drive<select value={f.drive} onChange={set("drive")} required><option value="">Choose the drive</option>
        {drives.data.map((x) => <option key={x.id} value={x.id}>{x.company_name}: {x.title} ({OFFER_TYPES[x.offer_type]}, {x.ctc_lpa ? lpa(x.ctc_lpa) : inr(x.stipend_amount)})</option>)}</select></label>
      <label>Offer date and time<input type="datetime-local" value={f.offer_date} onChange={set("offer_date")} required /></label>
      <label>PPO status<select value={f.ppo_status} onChange={set("ppo_status")}>{["na", "pending", "offered", "accepted", "declined"].map((v) => <option key={v}>{v}</option>)}</select></label>
      <label>NOC<select value={f.noc_status} onChange={set("noc_status")}>{["na", "required", "submitted", "approved"].map((v) => <option key={v}>{v}</option>)}</select></label>
      <label className="span">Reason<input value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} maxLength={300} placeholder="e.g. Offer letter received from HR on 12 Oct" /></label>
      <div className="span">{a.feedback}<div className="row"><button className="btn">Send for approval</button><button type="button" className="btn-quiet" onClick={onClose}>Cancel</button></div></div>
    </form>
  );
}

function Students() {
  const [q, setQ] = useState({ q: "", course: "", batch: "" });
  const qs = new URLSearchParams(Object.entries(q).filter(([, v]) => v)).toString();
  const { data, err, load } = useLoad<any[]>(`/staff/students?${qs}`, []);
  const [editing, setEditing] = useState<any>(null);
  const [offerFor, setOfferFor] = useState<any>(null);
  const [exportReason, setExportReason] = useState("");
  const a = useAction(load);
  const exportCsv = () => a.run(async () => {
    const blob = await api<Blob>("/staff/export", { body: { reason: exportReason, course: q.course || undefined } });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = "students_export.csv"; link.click();
    URL.revokeObjectURL(url);
  }, "Export downloaded and recorded in the audit log.");
  return (
    <Section title="Student records" aside={<button className="btn" onClick={() => setEditing({})}>Propose new student</button>}>
      <div className="filters">
        <label>Search<input value={q.q} onChange={(e) => setQ({ ...q, q: e.target.value })} placeholder="Name, Placement ID or email" maxLength={60} /></label>
        <label>Programme<select value={q.course} onChange={(e) => setQ({ ...q, course: e.target.value })}><option value="">All</option>{Object.entries(COURSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>Batch<input value={q.batch} onChange={(e) => setQ({ ...q, batch: e.target.value })} maxLength={7} /></label>
        <label>Export reason<input value={exportReason} onChange={(e) => setExportReason(e.target.value)} placeholder="Why you need the file" /></label>
        <button className="btn-quiet" onClick={exportCsv}>Export CSV</button>
      </div>
      <Errors lines={err} />{a.feedback}
      {editing && <StudentForm student={editing.id ? editing : undefined} onClose={() => setEditing(null)} />}
      {offerFor && <OfferForm student={offerFor} onClose={() => setOfferFor(null)} />}
      <div className="table-wrap"><table>
        <thead><tr><th>Placement ID</th><th>Name</th><th>Programme</th><th>Registration</th><th>Eligibility</th><th className="num">CGPA</th><th>Status</th><th>Category</th><th>Mobile</th><th /></tr></thead>
        <tbody>{data.map((s) => (
          <tr key={s.id}>
            <td>{s.placement_id}</td><td>{s.name}</td><td>{COURSES[s.course]}<br /><span className="small muted">{s.batch}</span></td>
            <td><Chip value={s.registration_status} /></td><td><Chip value={s.eligibility_status} /></td><td className="num">{s.cgpa}</td>
            <td>{STATUS[s.placement_status]}</td><td><Category value={s.current_category} /></td><td className="small">{s.mobile}</td>
            <td><div className="row tight">
              <button className="btn-quiet" onClick={() => setEditing(s)}>Edit</button>
              <button className="btn-quiet" onClick={() => setOfferFor(s)}>Add offer</button>
              <button className="btn-quiet" onClick={() => { const r = prompt(`Reason for archiving ${s.placement_id}?`); if (r) a.run(() => propose("student", "archive", s.id, {}, r), "Archive sent for approval."); }}>Archive</button>
            </div></td>
          </tr>
        ))}</tbody>
      </table></div>
    </Section>
  );
}

/* ---------------------------------------------------------------- offers, drives */
function Offers() {
  const { data, err, load } = useLoad<any[]>("/staff/offers", []);
  const a = useAction(load);
  const update = (o: any, field: string, value: string) => {
    const r = prompt(`Reason for setting ${field.replace("_", " ")} to "${value}"?`);
    if (r) a.run(() => propose("offer", "update", o.id, { [field]: value }, r), "Change sent for approval.");
  };
  return (
    <Section title="Offers">
      <Errors lines={err} />{a.feedback}
      {data.length === 0 ? <Empty>No offers recorded yet.</Empty> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Student</th><th>Company</th><th>Type</th><th className="num">Package</th><th>Category</th><th>Acceptance</th><th>Joining</th><th>Deadline</th><th>NOC</th></tr></thead>
          <tbody>{data.map((o) => (
            <tr key={o.id}>
              <td>{o.student_name}<br /><span className="small muted">{o.placement_id}</span></td><td>{o.company_name}</td><td>{OFFER_TYPES[o.offer_type]}</td>
              <td className="num">{o.offer_type === "I" ? `${inr(o.stipend_amount)}/mo` : lpa(o.ctc_lpa)}</td><td><Category value={o.category} /></td>
              <td><Chip value={o.acceptance} /></td>
              <td><select value={o.joining_status} onChange={(e) => update(o, "joining_status", e.target.value)} aria-label="Joining status">{["pending", "joined", "not_joined"].map((v) => <option key={v}>{v}</option>)}</select></td>
              <td className="small">{when(o.acceptance_deadline)}</td>
              <td><select value={o.noc_status} onChange={(e) => update(o, "noc_status", e.target.value)} aria-label="NOC status">{["na", "required", "submitted", "approved"].map((v) => <option key={v}>{v}</option>)}</select></td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </Section>
  );
}

function Drives() {
  const { me } = useAuth();
  const { data, err, load } = useLoad<any[]>("/staff/drives", []);
  const [companies, setCompanies] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => { setCompanies(Array.from(new Map(data.map((d) => [d.company, { id: d.company, name: d.company_name }])).values())); }, [data]);
  const [f, setF] = useState({ company: "", title: "", offer_type: "F", ctc_lpa: "", stipend_amount: "", min_cgpa: "6.5", max_backlogs: "0", application_deadline: "", company_acceptance_hours: "" });
  const [courses, setCourses] = useState<string[]>([]);
  const a = useAction(load);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { ...f, company: Number(f.company), eligible_courses: courses, application_deadline: new Date(f.application_deadline).toISOString() };
    for (const k of ["ctc_lpa", "stipend_amount", "company_acceptance_hours"]) if (!body[k]) body[k] = null;
    if (body.stipend_amount) body.stipend_period = "month";
    a.run(() => api("/staff/drives", { body }), "Drive created.");
  };
  return (
    <div className="split">
      <Section title="Drives">
        <Errors lines={err} />
        <div className="table-wrap"><table>
          <thead><tr><th>Company</th><th>Role</th><th>Type</th><th className="num">Package</th><th>Category</th><th>Programmes</th><th>Closes</th><th>Status</th></tr></thead>
          <tbody>{data.map((d) => (
            <tr key={d.id}><td>{d.company_name}</td><td>{d.title}</td><td>{OFFER_TYPES[d.offer_type]}</td>
              <td className="num">{d.ctc_lpa ? lpa(d.ctc_lpa) : `${inr(d.stipend_amount)}/mo`}</td><td><Category value={d.category} /></td>
              <td className="small">{d.eligible_courses.map((c: string) => COURSES[c]).join(", ")}</td><td className="small">{when(d.application_deadline)}</td><td><Chip value={d.status} /></td></tr>
          ))}</tbody>
        </table></div>
      </Section>
      {me?.role !== "coordinator" && (
        <Section title="Create a drive">
          <form className="form" onSubmit={submit}>
            <label>Company<select value={f.company} onChange={set("company")} required><option value="">Choose a verified company</option>{companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <label>Role title<input value={f.title} onChange={set("title")} required maxLength={150} /></label>
            <label>Offer type<select value={f.offer_type} onChange={set("offer_type")}>{Object.entries(OFFER_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            {f.offer_type !== "I" && <label>Annual CTC (LPA)<input type="number" step="0.01" value={f.ctc_lpa} onChange={set("ctc_lpa")} required /></label>}
            {f.offer_type !== "F" && <label>Monthly stipend (₹)<input type="number" value={f.stipend_amount} onChange={set("stipend_amount")} /></label>}
            <fieldset><legend>Open to</legend>{Object.entries(COURSES).map(([k, v]) => (
              <label key={k} className="check"><input type="checkbox" checked={courses.includes(k)} onChange={() => setCourses(courses.includes(k) ? courses.filter((x) => x !== k) : [...courses, k])} />{v}</label>))}</fieldset>
            <div className="row"><label>Min CGPA<input type="number" step="0.1" value={f.min_cgpa} onChange={set("min_cgpa")} /></label><label>Max backlogs<input type="number" value={f.max_backlogs} onChange={set("max_backlogs")} /></label></div>
            <label>Applications close<input type="datetime-local" value={f.application_deadline} onChange={set("application_deadline")} required /></label>
            <label>Company's acceptance window in hours (if shorter than 24)<input type="number" value={f.company_acceptance_hours} onChange={set("company_acceptance_hours")} /></label>
            {a.feedback}<button className="btn">Create drive</button>
          </form>
        </Section>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- recruiters, bulletin, flags */
function Recruiters() {
  const { data, err, load } = useLoad<any[]>("/staff/recruiter-requests?status=new", []);
  const a = useAction(load);
  const [f, setF] = useState({ company_name: "", website: "", contact_name: "", contact_email: "" });
  const [reason, setReason] = useState("");
  return (
    <div className="split">
      <Section title="Interest from the public form">
        <Errors lines={err} />{a.feedback}
        {data.length === 0 ? <Empty>No new requests.</Empty> : <ul className="cards">{data.map((r) => (
          <li key={r.id} className="change">
            <h3>{r.company_name}</h3>
            <p className="small">{r.contact_name} · {r.contact_email} {r.contact_phone && `· ${r.contact_phone}`} {r.website && <>· <a href={r.website} target="_blank" rel="noopener noreferrer">{r.website}</a></>}</p>
            <p>Roles: {r.roles_offered} · {r.offer_types} · CTC {r.ctc_range || "—"} · stipend {r.stipend_range || "—"}</p>
            <p className="small muted">{r.eligible_courses.map((c: string) => COURSES[c]).join(", ")} · {r.expected_dates}</p>
            {r.notes && <p className="small">{r.notes}</p>}
            <div className="row">
              <button className="btn" onClick={() => a.run(() => api(`/staff/recruiter-requests/${r.id}/verify`, { method: "POST" }), "Verified. The Recruiter ID and activation link were emailed.")}>Verify and send Recruiter ID</button>
              <button className="btn-quiet" onClick={() => a.run(() => api(`/staff/recruiter-requests/${r.id}/reject`, { method: "POST" }), "Rejected.")}>Reject</button>
            </div>
          </li>))}</ul>}
      </Section>
      <Section title="Add a recruiter directly">
        <p className="muted small">Goes through approval. The recruiter receives an ID and a single-use link to set a password; no password is ever emailed.</p>
        <form className="form" onSubmit={(e) => { e.preventDefault(); a.run(() => propose("recruiter", "create", null, f, reason), "Sent for approval."); }}>
          <label>Company<input value={f.company_name} onChange={(e) => setF({ ...f, company_name: e.target.value })} required /></label>
          <label>Website<input type="url" value={f.website} onChange={(e) => setF({ ...f, website: e.target.value })} /></label>
          <label>Contact name<input value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} required /></label>
          <label>Contact email<input type="email" value={f.contact_email} onChange={(e) => setF({ ...f, contact_email: e.target.value })} required /></label>
          <label>Reason<input value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} /></label>
          <button className="btn">Send for approval</button>
        </form>
      </Section>
    </div>
  );
}

function BulletinQueue() {
  const { data, err, load } = useLoad<any[]>("/staff/bulletin/pending", []);
  const a = useAction(load);
  return (
    <Section title="Recruiter posts waiting for approval">
      <Errors lines={err} />{a.feedback}
      {data.length === 0 ? <Empty>Nothing to review.</Empty> : <ul className="cards">{data.map((p) => (
        <li key={p.id} className="change">
          <h3>{p.title}</h3>
          <p className="small muted">{p.author_name} · {when(p.starts_at)} to {when(p.ends_at)} · {p.has_meeting_link ? "has a meeting link" : "no meeting link"}</p>
          {p.body && <p>{p.body.replace(/<[^>]+>/g, " ")}</p>}
          <div className="row">
            <button className="btn" onClick={() => a.run(() => api(`/staff/bulletin/${p.id}/approve`, { method: "POST" }), "Published to the bulletin.")}>Publish</button>
            <button className="btn-quiet" onClick={() => a.run(() => api(`/staff/bulletin/${p.id}/reject`, { method: "POST" }), "Rejected.")}>Reject</button>
          </div>
        </li>))}</ul>}
    </Section>
  );
}

function Flags() {
  const { data, err, load } = useLoad<any[]>("/staff/flags?status=open", []);
  const a = useAction(load);
  return (
    <Section title="Open policy flags">
      <p className="muted small">Raised automatically (for example, absence from a talk the student applied for). Waiving one needs a second person's approval.</p>
      <Errors lines={err} />{a.feedback}
      {data.length === 0 ? <Empty>No open flags.</Empty> : <div className="table-wrap"><table>
        <thead><tr><th>Student</th><th>Programme</th><th>Rule</th><th>Explanation</th><th className="num">Drives left</th><th /></tr></thead>
        <tbody>{data.map((f) => (
          <tr key={f.id}><td>{f.name}<br /><span className="small muted">{f.placement_id}</span></td><td>{COURSES[f.course]}</td><td className="small">{f.rule_code}</td><td>{f.explanation}</td><td className="num">{f.drives_remaining}</td>
            <td><button className="btn-quiet" onClick={() => { const r = prompt("Reason for waiving (e.g. medical emergency, documented)?"); if (r) a.run(() => propose("flag", "waive", f.id, {}, r), "Waiver sent for approval."); }}>Propose waiver</button></td></tr>
        ))}</tbody>
      </table></div>}
    </Section>
  );
}

/* ---------------------------------------------------------------- reports, audit, policy */
const ACCEPT_TONE = ["var(--c1)", "var(--c2)", "var(--c3)"];
const rate = (placed: number, of: number) => (of ? Math.round((100 * placed) / of) : 0);

function Reports() {
  const [course, setCourse] = useState("");
  const { data: r, err } = useLoad<any>(`/staff/reports${course ? `?course=${course}` : ""}`, null);
  if (!r) return <Errors lines={err} />;
  const t = r.totals;
  const progs = Object.entries(r.by_course) as [string, any][];
  const batches = Object.entries(r.by_batch) as [string, any][];
  const stip = r.internship_stipend_monthly_inr;
  return (
    <div className="stack">
      <div className="row wrap" style={{ justifyContent: "space-between" }}>
        <label className="inline">Programme<select value={course} onChange={(e) => setCourse(e.target.value)}><option value="">University-wide</option>{Object.entries(COURSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <span className="muted small">Internal figures, not suppressed. Viewing this report is logged.</span>
      </div>
      <dl className="kpis">
        <Kpi icon="users" label="Students" value={t.students} tone={1} />
        <Kpi icon="checkCircle" label="Placed (unique students)" value={t.placed_unique_students} tone={3} />
        <Kpi icon="target" label="Unplaced" value={t.unplaced} tone={5} />
        <Kpi icon="briefcase" label="Total offers" value={t.total_offers} tone={2} />
        <Kpi icon="trophy" label="Accepted offers" value={t.accepted_offers} tone={4} />
      </dl>

      <div className="dash-grid">
        <Card title="Placement funnel" icon="layers" sub="From the whole roll down to accepted offers" className="col-7">
          <Funnel title="Placement funnel" steps={[
            { label: "Students", value: t.students }, { label: "Registered", value: t.registered }, { label: "Eligible", value: t.eligible },
            { label: "Placed", value: t.placed_unique_students }, { label: "Accepted offers", value: t.accepted_offers },
          ]} />
        </Card>
        <Card title="Placement status" icon="pie" className="col-5">
          <Donut title="Students by placement status" centerLabel="students"
            slices={Object.entries(r.placement_status_counts).map(([k, v], i) => ({ label: STATUS[k] ?? k, value: Number(v), color: SERIES[i % SERIES.length] }))} />
        </Card>
        <Card title="By programme" icon="chart" className="col-8">
          <BarChart title="Students, registered and placed by programme" categories={progs.map(([k]) => COURSES[k] ?? k)}
            series={[
              { name: "Students", color: "var(--c1)", values: progs.map(([, v]) => v.students) },
              { name: "Registered", color: "var(--c3)", values: progs.map(([, v]) => v.registered) },
              { name: "Placed", color: "var(--c2)", values: progs.map(([, v]) => v.placed) },
            ]} />
        </Card>
        <Card title="Accepted offers by type" icon="briefcase" className="col-4">
          {Object.keys(r.offer_type_counts).length
            ? <Donut title="Accepted offers by type" centerLabel="accepted" slices={Object.entries(r.offer_type_counts).map(([k, v], i) => ({ label: OFFER_TYPES[k] ?? k, value: Number(v), color: ACCEPT_TONE[i % 3] }))} />
            : <Empty>No accepted offers yet.</Empty>}
        </Card>
        <Card title="FTE packages (annual CTC, ₹ LPA)" icon="rupee" sub={`${r.fte_ctc_lpa.count} accepted full-time offers`} className="col-6">
          {r.fte_ctc_lpa.count ? <PackageRange title="FTE packages" highest={r.fte_ctc_lpa.highest} average={r.fte_ctc_lpa.average} median={r.fte_ctc_lpa.median} /> : <Empty>No accepted FTE offers yet.</Empty>}
        </Card>
        <Card title="Internship stipends (monthly)" icon="briefcase" sub="Reported separately from FTE packages" className="col-6">
          {stip.count ? (
            <HBars title="Internship stipends" rows={(["highest", "average", "median"] as const).map((k, i) => ({ label: k[0].toUpperCase() + k.slice(1), value: stip[k], display: inr(stip[k]), color: SERIES[i + 2] }))} />
          ) : <Empty>No accepted internships yet.</Empty>}
        </Card>
        <Card title="Offers by company" icon="building" className="col-7">
          <HBars title="Offers by company" rows={r.by_company.map((c: any, i: number) => ({ label: c.company, value: c.offers, display: `${c.accepted}/${c.offers} accepted`, color: SERIES[i % SERIES.length] }))} />
        </Card>
        <Card title="Needs follow-up" icon="bell" className="col-5">
          <HBars title="Items needing follow-up" rows={[
            { label: "Offers awaiting the student", value: r.pending.offer_acceptance, color: "var(--c2)" },
            { label: "Accepted, joining pending", value: r.pending.joining, color: "var(--c1)" },
            { label: "NOC required", value: r.pending.noc_required, color: "var(--c4)" },
            { label: "Open policy flags", value: r.pending.open_policy_flags, color: "var(--c5)" },
            { label: "Eligible for further drives", value: r.eligible_for_further_drives, color: "var(--c3)" },
          ]} />
        </Card>
      </div>

      <div className="pair">
        <Section title="By batch"><div className="table-wrap"><table><thead><tr><th>Batch</th><th className="num">Students</th><th className="num">Placed</th><th className="num">Rate</th></tr></thead>
          <tbody>{batches.map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{v.students}</td><td className="num">{v.placed}</td><td className="num">{rate(v.placed, v.students)}%</td></tr>)}</tbody></table></div></Section>
        <Section title="By company"><div className="table-wrap"><table><thead><tr><th>Company</th><th className="num">Offers</th><th className="num">Accepted</th><th>Categories</th><th className="num">Highest CTC</th></tr></thead>
          <tbody>{r.by_company.map((c: any) => <tr key={c.company}><td>{c.company}</td><td className="num">{c.offers}</td><td className="num">{c.accepted}</td><td><div className="row tight">{c.categories.length ? c.categories.map((x: string) => <Category key={x} value={x} />) : "—"}</div></td><td className="num">{lpa(c.highest_ctc_lpa)}</td></tr>)}</tbody></table></div></Section>
      </div>
    </div>
  );
}

function Audit() {
  const [entity, setEntity] = useState("");
  const { data, err } = useLoad<any[]>(`/staff/audit${entity ? `?entity=${entity}` : ""}`, []);
  const [chain, setChain] = useState<any>(null);
  return (
    <Section title="Audit log" aside={<div className="row">
      <select value={entity} onChange={(e) => setEntity(e.target.value)} aria-label="Filter by record type"><option value="">All records</option>{["student", "offer", "user", "drive", "application", "post", "recruiter", "recruiter_request", "policy_config"].map((x) => <option key={x}>{x}</option>)}</select>
      <button className="btn" onClick={() => api("/staff/audit/verify").then(setChain)}>Verify the hash chain</button></div>}>
      {chain && (chain.intact
        ? <Done text={`Chain intact: ${chain.verified_records} records verified. No entry has been edited or deleted.`} />
        : <Errors lines={[`Chain broken at record ${chain.first_broken_id}. Someone changed the log outside the application.`]} />)}
      <Errors lines={err} />
      <div className="table-wrap"><table className="audit">
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Record</th><th>Before</th><th>After</th><th>IP</th></tr></thead>
        <tbody>{data.map((r) => (
          <tr key={r.id}><td className="small">{when(r.ts)}</td><td>{r.actor_label}<br /><span className="small muted">{r.role}</span></td><td>{r.action}</td>
            <td className="small">{r.entity} {r.entity_id}</td><td className="small code">{r.before ? JSON.stringify(r.before) : ""}</td>
            <td className="small code">{r.after ? JSON.stringify(r.after) : ""}</td><td className="small">{r.ip}</td></tr>
        ))}</tbody>
      </table></div>
    </Section>
  );
}

function PolicySettings() {
  const { data, err, load } = useLoad<any>("/staff/policy", null);
  const a = useAction(load);
  const [f, setF] = useState<any>(null);
  useEffect(() => { if (data) setF(data); }, [data]);
  if (!f) return <Errors lines={err} />;
  const num = (k: string, label: string) => <label>{label}<input type="number" step="0.01" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>;
  return (
    <Section title="Policy settings">
      <form className="form two-col" onSubmit={(e) => { e.preventDefault(); a.run(() => api("/staff/policy", { method: "PUT", body: f }), "Settings saved and logged."); }}>
        {num("a_plus_min_lpa", "A+ starts at (LPA)")}{num("a_min_lpa", "A starts at (LPA)")}{num("b_min_lpa", "B starts at (LPA)")}
        {num("b_switch_multiplier", "B switch multiplier")}{num("acceptance_hours", "Acceptance window (hours)")}{num("absence_exclusion_drives", "Drives excluded after an absence")}
        <label className="check span"><input type="checkbox" checked={f.enforce_switching} onChange={(e) => setF({ ...f, enforce_switching: e.target.checked })} />
          Enforce category switching rules (off = advisory: recruiters see them as review notes and decide)</label>
        <div className="span">{a.feedback}<button className="btn">Save settings</button></div>
      </form>
    </Section>
  );
}
