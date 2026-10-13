import { FormEvent, useState } from "react";
import { Icon, IconName } from "../components/icons";
import { Done, Errors } from "../components/ui";
import { api, errorLines } from "../lib/api";
import { COURSES } from "../lib/format";

const BLANK = { company_name: "", website: "", contact_name: "", contact_email: "", contact_phone: "", roles_offered: "",
  ctc_range: "", stipend_range: "", expected_dates: "", notes: "", website_confirm: "" };

const STEPS: { icon: IconName; title: string; text: string }[] = [
  { icon: "file", title: "Tell us about your roles", text: "Send this form. It takes about five minutes." },
  { icon: "shield", title: "The Cell verifies you", text: "We confirm the organisation and the HR contact." },
  { icon: "key", title: "Receive your Recruiter ID", text: "A single-use link lets you set your own password." },
  { icon: "calendar", title: "Schedule the drive", text: "Dates, eligibility and the package are agreed with the Cell." },
  { icon: "users", title: "Meet the candidates", text: "See applicants, shortlist, announce talks and select." },
];

function Banner() {
  return (
    <section className="page-banner">
      <div>
        <p className="eyebrow">Recruit at NFSU</p>
        <h1>Hire from India's forensic science university</h1>
        <p>Five computing programmes, one verified point of contact, and a placement process recruiters can trust.</p>
      </div>
    </section>
  );
}

export default function Recruit() {
  const [f, setF] = useState(BLANK);
  const [types, setTypes] = useState<string[]>([]);
  const [courses, setCourses] = useState<string[]>([]);
  const [err, setErr] = useState<string[]>([]);
  const [done, setDone] = useState("");
  const set = (k: keyof typeof BLANK) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const toggle = (list: string[], setList: (v: string[]) => void, v: string) =>
    setList(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr([]);
    try {
      const r = await api<{ detail: string }>("/public/recruit", { body: { ...f, offer_types: types.join(","), eligible_courses: courses } });
      setDone(r.detail);
      setF(BLANK);
    } catch (ex) {
      setErr(errorLines(ex));
    }
  };

  if (done) return (
    <>
      <Banner />
      <div className="narrow card" style={{ marginTop: "-2rem", position: "relative" }}>
        <h2><Icon name="checkCircle" /> Request sent</h2>
        <Done text={done} />
      </div>
    </>
  );
  return (
    <>
    <Banner />
    <div className="recruit-layout">
      <aside className="card">
        <h3><Icon name="layers" />How it works</h3>
        <p className="card-sub">The Placement Cell verifies every organisation before it can see candidates.</p>
        <ol className="vsteps">
          {STEPS.map((s, i) => (
            <li key={s.title}><span className={`kpi-icon tone-${(i % 5) + 1}`}><Icon name={s.icon} /></span><div><strong>{s.title}</strong><span>{s.text}</span></div></li>
          ))}
        </ol>
      </aside>
      <div className="card">
      <h2>Register your interest</h2>
      <p className="muted small">Organisation name, HR contact, official email and roles are required. You will receive a Recruiter ID by email once verified.</p>
      <form className="form two-col" onSubmit={submit}>
        <label>Organisation name<input value={f.company_name} onChange={set("company_name")} required maxLength={150} /></label>
        <label>Website<input type="url" value={f.website} onChange={set("website")} placeholder="https://" /></label>
        <label>HR contact name<input value={f.contact_name} onChange={set("contact_name")} required maxLength={120} /></label>
        <label>Official email<input type="email" value={f.contact_email} onChange={set("contact_email")} required /></label>
        <label>Phone<input value={f.contact_phone} onChange={set("contact_phone")} maxLength={20} inputMode="tel" /></label>
        <label>Roles you are hiring for<input value={f.roles_offered} onChange={set("roles_offered")} required maxLength={300} /></label>
        <fieldset>
          <legend>Offer types</legend>
          {[["I", "Internship"], ["F", "Full-time"], ["IF", "Internship + PPO/FTE"]].map(([v, l]) => (
            <label key={v} className="check"><input type="checkbox" checked={types.includes(v)} onChange={() => toggle(types, setTypes, v)} />{l}</label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Programmes you want to hire from</legend>
          {Object.entries(COURSES).map(([v, l]) => (
            <label key={v} className="check"><input type="checkbox" checked={courses.includes(v)} onChange={() => toggle(courses, setCourses, v)} />{l}</label>
          ))}
        </fieldset>
        <label>CTC range (LPA)<input value={f.ctc_range} onChange={set("ctc_range")} placeholder="e.g. 8–12" maxLength={60} /></label>
        <label>Stipend range (per month)<input value={f.stipend_range} onChange={set("stipend_range")} maxLength={60} /></label>
        <label>Expected dates<input value={f.expected_dates} onChange={set("expected_dates")} maxLength={120} /></label>
        <label className="span">Anything else the Placement Cell should know<textarea value={f.notes} onChange={set("notes")} maxLength={2000} rows={4} /></label>
        <label className="hp" aria-hidden="true">Leave this empty<input tabIndex={-1} autoComplete="off" value={f.website_confirm} onChange={set("website_confirm")} /></label>
        <div className="span"><Errors lines={err} /><button className="btn btn-lg"><Icon name="arrowRight" />Send to the Placement Cell</button></div>
      </form>
      </div>
    </div>
    </>
  );
}
