import { useCallback, useEffect, useState } from "react";
import { Donut, Gauge, SERIES } from "../components/charts";
import { Icon } from "../components/icons";
import { Card, Category, Chip, Done, Empty, Errors, initials, Kpi, Reasons, Section, Verdict } from "../components/ui";
import { api, errorLines } from "../lib/api";
import { COURSES, inr, lpa, OFFER_TYPES, STATUS, when } from "../lib/format";

const RUNGS = ["None", "C", "B", "A", "A+"];
const APP_STATUSES = ["applied", "shortlisted", "selected", "rejected"];

/** Display-only summary of where the student is. The server decides everything; this just reads the records. */
function journey(me: any, apps: any[], offers: any[]) {
  const steps = [
    { label: "Registered", done: me.registration_status === "registered" },
    { label: "Eligible", done: me.eligibility_status === "eligible" },
    { label: "Applied", done: apps.length > 0 },
    { label: "Shortlisted", done: apps.some((a) => ["shortlisted", "selected"].includes(a.status)) || offers.length > 0 },
    { label: "Offer received", done: offers.length > 0 },
    { label: "Offer accepted", done: offers.some((o) => o.acceptance === "accepted") },
    { label: "Joined", done: offers.some((o) => o.joining_status === "joined") },
  ];
  const now = steps.findIndex((s) => !s.done);
  return steps.map((s, i) => ({ ...s, now: i === now }));
}

export default function Student() {
  const [me, setMe] = useState<any>(null);
  const [drives, setDrives] = useState<any[]>([]);
  const [data, setData] = useState<{ offers: any[]; applications: any[] }>({ offers: [], applications: [] });
  const [err, setErr] = useState<string[]>([]);
  const [done, setDone] = useState("");

  const load = useCallback(async () => {
    try {
      const [m, d, o] = await Promise.all([api("/student/me"), api("/student/drives"), api("/student/offers")]);
      setMe(m); setDrives(d); setData(o);
    } catch (e) { setErr(errorLines(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    setErr([]); setDone("");
    try { await fn(); setDone(msg); await load(); } catch (e) { setErr(errorLines(e)); }
  };
  const upload = (file?: File) => {
    if (!file) return;
    const form = new FormData();
    form.append("resume", file);
    act(() => api("/student/resume", { form }), "Resume uploaded.");
  };

  if (!me) return <Errors lines={err} />;
  const steps = journey(me, data.applications, data.offers);
  const rung = me.current_category ?? "None";
  const appCounts = APP_STATUSES.map((s, i) => ({ label: s[0].toUpperCase() + s.slice(1), value: data.applications.filter((a) => a.status === s).length, color: SERIES[i] }))
    .filter((s) => s.value > 0);
  const cgpa = Number(me.cgpa);

  return (
    <div className="stack">
      <header className="banner">
        <span className="avatar lg" aria-hidden="true">{initials(me.name)}</span>
        <div className="grow">
          <h1>{me.name}</h1>
          <p>{me.placement_id} · {COURSES[me.course]} · batch {me.batch}</p>
        </div>
        <div className="row tight" style={{ position: "relative", zIndex: 1 }}>
          <span className="chip"><Icon name="briefcase" />{data.applications.length} applications</span>
          <span className="chip"><Icon name="trophy" />{data.offers.length} offers</span>
        </div>
      </header>
      <Errors lines={err} />
      <Done text={done} />

      <dl className="kpis">
        <Kpi icon="target" label="Placement status" value={STATUS[me.placement_status]} tone={1} />
        <Kpi icon="layers" label="Current category" value={<Category value={me.current_category} />} tone={2} />
        <Kpi icon="checkCircle" label="Registration" value={me.registration_status.replace("_", " ")} tone={3} />
        <Kpi icon="shield" label="Eligibility" value={me.eligibility_status} tone={4} />
        <Kpi icon="graduation" label="CGPA" value={me.cgpa} tone={5} />
      </dl>
      <p className="fine">Your status, package and eligibility are maintained by the Placement Cell. If something is wrong, contact them; you cannot change these fields yourself.</p>

      <div className="dash-grid">
        <Card title="Your placement journey" icon="flag" className="col-8">
          <ol className="stepper">
            {steps.map((s) => <li key={s.label} className={s.done ? "done" : s.now ? "now" : ""}>{s.label}</li>)}
          </ol>
        </Card>
        <Card title="Academic standing" icon="graduation" className="col-4">
          <Gauge label={`CGPA ${me.cgpa} out of 10`} percent={Number.isFinite(cgpa) ? Math.round(cgpa * 10) : null} color="var(--c3)" />
        </Card>
        <Card title="Category ladder" icon="layers" sub="Your highest full-time offer sets your category. Drives in a lower category may be closed to you." className="col-6">
          <div className="ladder" role="img" aria-label={`Current category: ${rung}`}>
            {RUNGS.map((r, i) => (
              <div key={r} className={`rung${r === rung ? " on" : ""}`} style={{ height: `${3 + i * 1.1}rem` }}>
                {r}{r === rung && <small>you</small>}
              </div>
            ))}
          </div>
        </Card>
        <Card title="Applications by stage" icon="pie" className="col-6">
          {appCounts.length ? <Donut title="Applications by stage" slices={appCounts} centerLabel="applications" /> : <Empty>You have not applied yet.</Empty>}
        </Card>
      </div>

      <Section title="Offers">
        {data.offers.length === 0 ? <Empty>No offers yet. Apply to open drives below.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Company</th><th>Type</th><th className="num">Package</th><th>Status</th><th>Respond by</th><th /></tr></thead>
            <tbody>{data.offers.map((o) => (
              <tr key={o.id}>
                <td><strong>{o.company_name}</strong></td>
                <td>{OFFER_TYPES[o.offer_type]}</td>
                <td className="num">{o.offer_type === "I" ? `${inr(o.stipend_amount)} / ${o.stipend_period || "month"}` : lpa(o.ctc_lpa)}</td>
                <td><Chip value={o.acceptance} />{o.acceptance === "accepted" && <> <Chip value={o.joining_status} label={`joining ${o.joining_status.replace("_", " ")}`} /></>}</td>
                <td>{o.acceptance === "pending" ? when(o.acceptance_deadline) : "—"}</td>
                <td>{o.acceptance === "pending" && (
                  <div className="row">
                    <button className="btn btn-sm" onClick={() => act(() => api(`/student/offers/${o.id}/respond`, { body: { decision: "accept" } }), "Offer accepted.")}><Icon name="check" />Accept</button>
                    <button className="btn-quiet btn-sm" onClick={() => act(() => api(`/student/offers/${o.id}/respond`, { body: { decision: "decline" } }), "Offer declined.")}>Decline</button>
                  </div>
                )}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Section>

      <Section title="Open drives for your programme" aside={<span className="chip chip-info">{drives.length} open</span>}>
        {drives.length === 0 ? <Empty>No drives are open for {COURSES[me.course]} right now.</Empty> : (
          <ul className="cards grid">
            {drives.map((d, i) => (
              <li key={d.id} className="drive">
                <div className="drive-head">
                  <div className="row" style={{ alignItems: "flex-start" }}>
                    <span className="drive-logo" style={{ background: SERIES[i % SERIES.length], color: i % 5 === 1 ? "#1d1400" : "#fff" }}>{d.company_name.slice(0, 2).toUpperCase()}</span>
                    <div>
                      <h3 style={{ margin: 0 }}>{d.title}</h3>
                      <p className="muted small">{d.company_name}</p>
                    </div>
                  </div>
                  <Verdict decision={d.verdict.decision} />
                </div>
                <div className="drive-meta">
                  <span className="chip chip-info"><Icon name="briefcase" />{OFFER_TYPES[d.offer_type]}</span>
                  <span className="chip"><Icon name="rupee" />{d.ctc_lpa ? lpa(d.ctc_lpa) : `${inr(d.stipend_amount)} / month`}</span>
                  <span className="chip"><Icon name="clock" />closes {when(d.application_deadline)}</span>
                </div>
                <Reasons reasons={d.verdict.reasons} />
                {d.application_status ? <p className="ok-text"><Icon name="checkCircle" />Applied: {d.application_status}</p> : d.verdict.decision !== "BLOCK" && (
                  <button className="btn" onClick={() => act(() => api(`/student/drives/${d.id}/apply`, { method: "POST" }), `Applied to ${d.company_name}.`)}><Icon name="arrowRight" />Apply</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Profile and consent">
        <div className="card form">
          <label>Skills (comma-separated)
            <input defaultValue={me.skills} maxLength={300} onBlur={(e) => e.target.value !== me.skills && act(() => api("/student/me", { method: "PATCH", body: { skills: e.target.value } }), "Skills saved.")} />
          </label>
          <label className="check"><input type="checkbox" checked={me.consent_share_with_recruiters}
            onChange={(e) => act(() => api("/student/me", { method: "PATCH", body: { consent_share_with_recruiters: e.target.checked } }), "Preference saved.")} />
            Let verified recruiters see my academic profile and resume</label>
          <label className="check"><input type="checkbox" checked={me.consent_public_listing}
            onChange={(e) => act(() => api("/student/me", { method: "PATCH", body: { consent_public_listing: e.target.checked } }), "Preference saved.")} />
            List my first name and package on the public top-packages list</label>
          <label><span><Icon name="upload" /> Resume (PDF, up to 2 MB){me.has_resume && " — uploaded"}</span>
            <input type="file" accept="application/pdf" onChange={(e) => upload(e.target.files?.[0])} />
          </label>
        </div>
      </Section>
    </div>
  );
}
