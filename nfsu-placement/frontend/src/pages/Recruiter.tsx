import { useCallback, useEffect, useState } from "react";
import { BarChart, Donut, HBars, SERIES } from "../components/charts";
import { Icon } from "../components/icons";
import { Card, Category, Chip, Done, Empty, Errors, Kpi, Reasons, Section, Verdict } from "../components/ui";
import { api, errorLines } from "../lib/api";
import { COURSES, inr, lpa, OFFER_TYPES, STATUS } from "../lib/format";

const BANDS: [string, number, number][] = [["Below 6", 0, 6], ["6 to 7", 6, 7], ["7 to 8", 7, 8], ["8 to 9", 8, 9], ["9 and above", 9, 10.01]];

/** Charts summarise only the rows the server already returned for this view. */
function Summary({ rows, talent }: { rows: any[]; talent: boolean }) {
  const cg = rows.map((r) => Number(r.cgpa)).filter(Number.isFinite);
  const avg = cg.length ? (cg.reduce((a, b) => a + b, 0) / cg.length).toFixed(2) : "—";
  const byCourse = Object.entries(COURSES).map(([k, v], i) => ({ label: v, value: rows.filter((r) => r.course === k).length, color: SERIES[i] })).filter((x) => x.value);
  const verdicts = [["ALLOW", "Clear", "var(--clear)"], ["FLAG", "Review", "#c78a12"], ["BLOCK", "Blocked", "var(--block)"]] as const;
  return (
    <>
      <dl className="kpis">
        <Kpi icon="users" label={talent ? "Students in pool" : "Candidates"} value={rows.length} tone={1} />
        <Kpi icon="graduation" label="Average CGPA" value={avg} tone={2} />
        <Kpi icon="file" label="With a resume" value={rows.filter((r) => r.has_resume).length} tone={3} />
        {talent
          ? <Kpi icon="target" label="Not yet placed" value={rows.filter((r) => r.placement_status === "unplaced").length} tone={4} />
          : <Kpi icon="checkCircle" label="Shortlisted or selected" value={rows.filter((r) => ["shortlisted", "selected"].includes(r.application_status)).length} tone={4} />}
      </dl>
      {rows.length > 0 && (
        <div className="dash-grid">
          <Card title="CGPA distribution" icon="chart" className="col-4">
            <BarChart title="Candidates by CGPA band" height={210} categories={BANDS.map((b) => b[0])}
              series={[{ name: "Candidates", color: "var(--c1)", values: BANDS.map(([, lo, hi]) => cg.filter((c) => c >= lo && c < hi).length) }]} />
          </Card>
          <Card title="By programme" icon="pie" className="col-4">
            <Donut title="Candidates by programme" slices={byCourse} centerLabel={talent ? "students" : "candidates"} />
          </Card>
          <Card title={talent ? "Placement status" : "Policy notes"} icon={talent ? "target" : "scale"} className="col-4">
            {talent
              ? <HBars title="Placement status" rows={Object.entries(STATUS).map(([k, v], i) => ({ label: v, value: rows.filter((r) => r.placement_status === k).length, color: SERIES[i] }))} />
              : <HBars title="Policy notes" rows={verdicts.map(([k, l, c]) => ({ label: l, value: rows.filter((r) => r.verdict === k).length, color: c }))} />}
          </Card>
        </div>
      )}
    </>
  );
}

const NO_FILTERS = { course: "", batch: "", min_cgpa: "", max_cgpa: "", max_backlogs: "", skill: "", placement_status: "", category: "", verdict: "" };

export default function Recruiter() {
  const [drives, setDrives] = useState<any[]>([]);
  const [driveId, setDriveId] = useState<string>("talent");
  const [filters, setFilters] = useState(NO_FILTERS);
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState<string[]>([]);
  const [done, setDone] = useState("");

  useEffect(() => {
    api("/recruiter/drives").then((d) => { setDrives(d); if (d.length) { setRows([]); setDriveId(String(d[0].id)); } }).catch((e) => setErr(errorLines(e)));
  }, []);

  // `isLive` drops responses for a view the recruiter has already left, so a slow
  // talent-pool response can never be shown under a drive's heading (or the reverse).
  const load = useCallback(async (isLive: () => boolean = () => true) => {
    setErr([]);
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    try {
      const next = driveId === "talent" ? await api(`/recruiter/talent?${qs}`) : (await api(`/recruiter/drives/${driveId}/candidates?${qs}`)).candidates;
      if (isLive()) setRows(next);
    } catch (e) { if (isLive()) setErr(errorLines(e)); }
  }, [driveId, filters]);
  useEffect(() => {
    let live = true;
    load(() => live);
    return () => { live = false; };
  }, [load]);

  const decide = async (appId: number, status: string) => {
    setDone("");
    try { await api(`/recruiter/applications/${appId}`, { body: { status } }); setDone(`Candidate marked ${status}.`); load(); }
    catch (e) { setErr(errorLines(e)); }
  };
  const set = (k: keyof typeof NO_FILTERS) => (e: { target: { value: string } }) => setFilters({ ...filters, [k]: e.target.value });
  const drive = drives.find((d) => String(d.id) === driveId);
  const talent = driveId === "talent";

  return (
    <div className="stack">
      <header className="banner">
        <span className="kpi-icon" style={{ background: "rgba(255,255,255,0.14)", color: "var(--gold)" }}><Icon name="users" /></span>
        <div className="grow">
          <h1>Candidates</h1>
          <p>Academic statistics and policy notes are here to help you decide. Contact details appear once you shortlist a candidate.</p>
        </div>
        <span className="chip"><Icon name="lock" />Views are recorded in the audit log</span>
      </header>

      <div className="row wrap">
        <label className="inline">Show
          <select value={driveId} onChange={(e) => { setRows([]); setDriveId(e.target.value); }}>
            {drives.map((d) => <option key={d.id} value={d.id}>Applicants: {d.title} ({d.applicant_count})</option>)}
            <option value="talent">Talent pool (all consenting students)</option>
          </select>
        </label>
        {drive && <span className="muted">{OFFER_TYPES[drive.offer_type]} · {drive.ctc_lpa ? lpa(drive.ctc_lpa) : `${inr(drive.stipend_amount)} / month`} · category <Category value={drive.category} /></span>}
      </div>

      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter candidates">
        <label>Programme<select value={filters.course} onChange={set("course")}><option value="">Any</option>{Object.entries(COURSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>Batch<input value={filters.batch} onChange={set("batch")} placeholder="2025-27" maxLength={7} /></label>
        <label>CGPA from<input type="number" step="0.1" min="0" max="10" value={filters.min_cgpa} onChange={set("min_cgpa")} /></label>
        <label>CGPA to<input type="number" step="0.1" min="0" max="10" value={filters.max_cgpa} onChange={set("max_cgpa")} /></label>
        <label>Max backlogs<input type="number" min="0" value={filters.max_backlogs} onChange={set("max_backlogs")} /></label>
        <label>Skill<input value={filters.skill} onChange={set("skill")} maxLength={40} /></label>
        <label>Placement status<select value={filters.placement_status} onChange={set("placement_status")}><option value="">Any</option>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>Current category<select value={filters.category} onChange={set("category")}><option value="">Any</option><option value="none">No FTE offer</option>{["A+", "A", "B", "C"].map((c) => <option key={c}>{c}</option>)}</select></label>
        {!talent && <label>Policy note<select value={filters.verdict} onChange={set("verdict")}><option value="">Any</option><option value="ALLOW">Clear</option><option value="FLAG">Review</option><option value="BLOCK">Blocked</option></select></label>}
        <button type="button" className="btn-quiet" onClick={() => setFilters(NO_FILTERS)}><Icon name="sliders" />Clear filters</button>
      </form>

      <Errors lines={err} />
      <Done text={done} />
      <Summary rows={rows} talent={talent} />
      <Section title={`${rows.length} ${talent ? "students" : "candidates"}`}>
        {rows.length === 0 ? <Empty>No one matches these filters. Widen the CGPA range or clear a filter.</Empty> : (
          <div className="table-wrap"><table className="candidates">
            <thead><tr>
              <th>Candidate</th><th>Programme</th><th className="num">CGPA</th><th className="num">Backlogs</th><th className="num">10th / 12th</th>
              <th>Skills</th><th>Status</th><th>Category</th>{!talent && <><th>Policy</th><th>Contact</th><th>Decision</th></>}
            </tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.placement_id}>
                <td><strong>{r.name}</strong><br /><span className="muted small">{r.placement_id}</span>
                  {r.has_resume && <><br /><a href={`/api/resumes/${encodeURIComponent(r.placement_id)}`} target="_blank" rel="noopener noreferrer">Resume</a></>}</td>
                <td>{COURSES[r.course]}<br /><span className="muted small">{r.batch}</span></td>
                <td className="num">{r.cgpa}</td>
                <td className="num">{r.backlogs}</td>
                <td className="num">{r.tenth_percent ?? "—"} / {r.twelfth_percent ?? "—"}</td>
                <td className="small">{r.skills.join(", ")}</td>
                <td><Chip value={r.placement_status} label={STATUS[r.placement_status]} /></td>
                <td><Category value={r.current_category} /></td>
                {!talent && <>
                  <td><Verdict decision={r.verdict} /><Reasons reasons={r.reasons} /></td>
                  <td className="small">{r.contact_masked ? <span className="muted">Shortlist to see</span> : <>{r.email}<br />{r.mobile}</>}</td>
                  <td>
                    <p className="small"><Chip value={r.application_status} /></p>
                    <div className="row tight">
                      {r.application_status === "applied" && <button className="btn btn-sm" onClick={() => decide(r.application_id, "shortlisted")}>Shortlist</button>}
                      {r.application_status === "shortlisted" && <button className="btn btn-sm" onClick={() => decide(r.application_id, "selected")}>Select</button>}
                      {["applied", "shortlisted"].includes(r.application_status) && <button className="btn-quiet btn-sm" onClick={() => decide(r.application_id, "rejected")}>Not selected</button>}
                    </div>
                  </td>
                </>}
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Section>
      {drives.length === 0 && <Empty>Your organisation has no drives yet. The Placement Cell creates drives once dates are agreed.</Empty>}
    </div>
  );
}
