import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import BulletinList, { Post } from "../components/BulletinList";
import { BarChart, Donut, Gauge, HBars, PackageRange, SERIES } from "../components/charts";
import { Icon, IconName } from "../components/icons";
import { Card, Empty, Verdict } from "../components/ui";
import { api } from "../lib/api";
import { inr, lpa } from "../lib/format";

interface PublicStats {
  session: string;
  min_cell_size: number;
  registered_students: number | null;
  students_placed: number | null;
  offers_made: number | null;
  recruiters: number;
  fte_ctc_lpa: { highest: number; average: number; median: number } | null;
  internship_stipend_monthly_inr: { average: number; median: number } | null;
  by_course: { course: string; registered: number | null; placed: number | null; placement_rate: number | null }[];
  past_recruiters: string[];
  top_packages: { student: string; course: string; company: string; ctc_lpa: number }[];
}

const few = (n: number | null | undefined, k: number) => (n === undefined ? "—" : n === null ? `<${k}` : n.toLocaleString("en-IN"));
const short = (c: string) => c.replace("Computer Science and Engineering", "CSE").replace("Artificial Intelligence and Data Science", "AI & DS")
  .replace("Digital Forensics and Information Security", "Digital Forensics").replace("Computer Science", "CS");

/** Counts up to a number once, for the headline figures. */
function CountUp({ to, prefix = "", suffix = "" }: { to: number; prefix?: string; suffix?: string }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setV(to); return; }
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 1200);
      setV(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <>{prefix}{Number.isInteger(to) ? Math.round(v).toLocaleString("en-IN") : v.toFixed(1)}{suffix}</>;
}

const PROGRAMMES: { name: string; code: string; icon: IconName; blurb: string }[] = [
  { name: "M.Tech. Computer Science", code: "MTECH_CS", icon: "cpu", blurb: "Systems, algorithms and secure software engineering." },
  { name: "M.Tech. Artificial Intelligence and Data Science", code: "MTECH_AIDS", icon: "network", blurb: "Machine learning, analytics and applied AI." },
  { name: "B.Tech.–M.Tech. Computer Science and Engineering", code: "BTECH_MTECH_CSE", icon: "layers", blurb: "Five-year integrated computing programme." },
  { name: "M.Sc. Computer Science", code: "MSC_CS", icon: "graduation", blurb: "Core computer science with research depth." },
  { name: "M.Sc. Digital Forensics and Information Security", code: "MSC_DFIS", icon: "fingerprint", blurb: "Cyber forensics, incident response and security." },
];

const WHY: { icon: IconName; title: string; text: string; tone: 1 | 2 | 3 | 4 }[] = [
  { icon: "fingerprint", title: "Forensic-grade rigour", text: "Students train at the world's first university dedicated to forensic science, where evidence and accuracy come first.", tone: 1 },
  { icon: "shield", title: "Security by habit", text: "Digital forensics, information security and secure coding run through every computing programme.", tone: 2 },
  { icon: "scale", title: "Fair, rule-based process", text: "Eligibility and category rules are checked automatically, so every recruiter sees the same consistent picture.", tone: 3 },
  { icon: "handshake", title: "One verified contact", text: "The Placement Cell verifies each organisation, schedules drives and handles offers through one channel.", tone: 4 },
];

const FLOW: { icon: IconName; title: string; text: string }[] = [
  { icon: "user", title: "Register", text: "Student profile verified by the Cell" },
  { icon: "building", title: "Drive opens", text: "Verified recruiter, eligibility set" },
  { icon: "scale", title: "Policy check", text: "Engine gives a verdict before applying" },
  { icon: "file", title: "Apply", text: "One click, resume shared with consent" },
  { icon: "video", title: "Talks and tests", text: "Joined through the platform" },
  { icon: "approve", title: "Offer approved", text: "Recorded by one, approved by another" },
  { icon: "trophy", title: "Accept and join", text: "Within the acceptance window" },
];

const FAQ = [
  ["How do students register for placement?", "The Placement Cell creates your record from the university roll and emails a single-use activation link. Set your password, add your skills and resume, and choose what recruiters may see."],
  ["Why can't I apply to some drives?", "Each drive shows a verdict from the placement policy before you apply: Clear, Review or Blocked, with the reason in plain words. For example, a student who already holds a higher-category offer cannot apply to a lower-category drive."],
  ["How can an organisation recruit at NFSU?", "Fill in the Recruit at NFSU form. Once the Placement Cell verifies your organisation you receive a Recruiter ID and a link to set your password. You can then view applicants, shortlist and announce talks."],
  ["Who can see student data?", "Recruiters see academic statistics for applicants, and contact details only after shortlisting. The talent pool lists only students who agreed to it. Every view of a resume or candidate list is recorded in the audit log."],
  ["Why are some figures shown as \"<5\"?", "Any public figure computed from fewer than five students is withheld, so no individual student can be identified from the statistics."],
];

export default function Home() {
  const [s, setS] = useState<PublicStats | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  useEffect(() => {
    api<PublicStats>("/public/stats").then(setS).catch(() => setS(null));
    api<Post[]>("/public/bulletin").then(setPosts).catch(() => setPosts([]));
  }, []);
  const k = s?.min_cell_size ?? 5;
  const courses = s?.by_course ?? [];
  const reg = s?.registered_students, placed = s?.students_placed;
  const recruiters = s?.past_recruiters ?? [];

  return (
    <div className="home">
      {/* ---------------------------------------------------------------- hero */}
      <section className="hero">
        <div className="hero-bg" style={{ backgroundImage: "url(/images/campus-panorama.jpg)" }} role="img" aria-label="NFSU Gandhinagar campus" />
        <div className="hero-inner">
          <div>
            <p className="eyebrow">Training and Placement Cell</p>
            <h1>Where forensic precision meets <em>industry ready</em> talent</h1>
            <p className="lede">
              Placement outcomes for the five computing programmes at National Forensic Sciences University, Gandhinagar,
              published from approved figures for session {s?.session ?? "2026–27"}.
            </p>
            <div className="hero-cta">
              <a className="btn-gold btn-lg" href="#glance"><Icon name="chart" />Explore placements</a>
              <Link className="btn-ghost btn-lg" to="/recruit"><Icon name="handshake" />Recruit at NFSU</Link>
            </div>
          </div>
          <div className="hero-card">
            <h2>Placement rate by programme</h2>
            <HBars title="Placement rate by programme" max={100}
              rows={courses.map((c, i) => ({ label: short(c.course), value: c.placement_rate, display: c.placement_rate === null ? "—" : `${c.placement_rate}%`, color: SERIES[i % SERIES.length] }))} />
            <p className="fine">A dash means fewer than {k} students, so the figure is not published.</p>
          </div>
        </div>
      </section>

      <div className="statband">
        <dl>
          <div><span className="kpi-icon tone-1"><Icon name="users" /></span><div><dt>Students placed</dt><dd>{placed != null ? <CountUp to={placed} /> : few(placed, k)}</dd></div></div>
          <div><span className="kpi-icon tone-2"><Icon name="briefcase" /></span><div><dt>Offers made</dt><dd>{s?.offers_made != null ? <CountUp to={s.offers_made} /> : few(s?.offers_made, k)}</dd></div></div>
          <div><span className="kpi-icon tone-3"><Icon name="building" /></span><div><dt>Recruiting organisations</dt><dd>{s ? <CountUp to={s.recruiters} /> : "—"}</dd></div></div>
          <div><span className="kpi-icon tone-4"><Icon name="rupee" /></span><div><dt>Median FTE package</dt><dd>{s?.fte_ctc_lpa ? <CountUp to={s.fte_ctc_lpa.median} prefix="₹" suffix=" LPA" /> : "—"}</dd></div></div>
        </dl>
      </div>

      {/* ---------------------------------------------------------------- about */}
      <section className="band">
        <div className="band-inner about">
          <figure className="about-photo" style={{ margin: 0 }}>
            <img src="/images/campus-ibs.jpg" alt="Academic block on the NFSU Gandhinagar campus" loading="lazy" />
            <figcaption><strong>5</strong>computing programmes placing together this session</figcaption>
          </figure>
          <div>
            <p className="eyebrow">About the Cell</p>
            <h2>Bridging NFSU talent and the organisations that need it</h2>
            <p>
              National Forensic Sciences University is an Institution of National Importance and the world's first university dedicated to
              forensic and allied sciences. Its Training and Placement Cell prepares students for careers in technology, cyber security and
              forensics, and works with recruiters from the first conversation to the joining date.
            </p>
            <p>
              Every placement decision on this portal follows the published policy. Changes to student records and offers need a second
              person's approval, and every action is written to a tamper-evident audit log.
            </p>
            <ul className="ticks">
              <li><Icon name="checkCircle" />Verified recruiters only</li>
              <li><Icon name="checkCircle" />Policy checked before every application</li>
              <li><Icon name="checkCircle" />Two-person approval for records</li>
              <li><Icon name="checkCircle" />Students control what is shared</li>
            </ul>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- statistics */}
      <section className="band alt" id="glance">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">Placement statistics</p>
            <h2>Session {s?.session ?? "2026–27"} at a glance</h2>
            <p>Students placed counts each person once; offers made counts every offer, so the two differ. Groups smaller than {k} are withheld.</p>
          </div>
          <div className="dash-grid">
            <Card title="Registered and placed, by programme" icon="chart" className="col-7">
              <BarChart title="Registered and placed students by programme" categories={courses.map((c) => short(c.course))}
                series={[
                  { name: "Registered", color: "var(--c1)", values: courses.map((c) => c.registered) },
                  { name: "Placed", color: "var(--c2)", values: courses.map((c) => c.placed) },
                ]} />
            </Card>
            <Card title="Overall placement" icon="pie" sub="Registered students who hold at least one offer" className="col-5">
              {reg != null && placed != null ? (
                <Donut title="Placed and not yet placed" center={`${Math.round((100 * placed) / reg)}%`} centerLabel="placed"
                  slices={[{ label: "Placed", value: placed, color: "var(--c2)" }, { label: "Not yet placed", value: Math.max(0, reg - placed), color: "var(--c1)" }]} />
              ) : <Empty>Not enough students yet to publish.</Empty>}
            </Card>
            <Card title="Placement rate by programme" icon="target" className="col-12">
              <div className="gauges">
                {courses.map((c, i) => <Gauge key={c.course} label={short(c.course)} percent={c.placement_rate} color={SERIES[i % SERIES.length]} />)}
              </div>
            </Card>
            <Card title="FTE packages (annual CTC, ₹ LPA)" icon="rupee" sub="From accepted full-time offers" className="col-7">
              {s?.fte_ctc_lpa ? <PackageRange title="FTE packages" {...s.fte_ctc_lpa} /> : <Empty>Not enough accepted offers yet to publish.</Empty>}
            </Card>
            <Card title="Internship stipends (monthly)" icon="briefcase" sub="Reported separately from FTE packages" className="col-5">
              {s?.internship_stipend_monthly_inr ? (
                <HBars title="Internship stipends" rows={[
                  { label: "Average", value: s.internship_stipend_monthly_inr.average, display: inr(s.internship_stipend_monthly_inr.average), color: "var(--c3)" },
                  { label: "Median", value: s.internship_stipend_monthly_inr.median, display: inr(s.internship_stipend_monthly_inr.median), color: "var(--c4)" },
                ]} />
              ) : <Empty>Not enough internships yet to publish.</Empty>}
            </Card>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- process diagram */}
      <section className="band dark">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">How placement works</p>
            <h2>From registration to joining, every step is checked</h2>
            <p>The policy engine reviews each application, offer and acceptance, and two people sign off every change to a record.</p>
          </div>
          <ol className="flow">
            {FLOW.map((f) => (
              <li key={f.title}><span className="kpi-icon"><Icon name={f.icon} /></span><strong>{f.title}</strong><span>{f.text}</span></li>
            ))}
          </ol>
          <p className="flow-note">Each check returns one of three verdicts: <Verdict decision="ALLOW" /> <Verdict decision="FLAG" /> <Verdict decision="BLOCK" /> with the reason written out.</p>
        </div>
      </section>

      {/* ---------------------------------------------------------------- why recruit */}
      <section className="band">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">Why recruit at NFSU</p>
            <h2>Graduates shaped by science, security and ethics</h2>
          </div>
          <div className="about">
            <svg className="venn" viewBox="0 0 400 360" role="img" aria-label="Diagram: NFSU graduates combine technical depth, forensic thinking and professional ethics">
              <defs>
                <linearGradient id="v1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#2e56a8" /><stop offset="1" stopColor="#0f2350" /></linearGradient>
                <linearGradient id="v2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f0b73a" /><stop offset="1" stopColor="#c8861a" /></linearGradient>
                <linearGradient id="v3" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3fb3a3" /><stop offset="1" stopColor="#1f7a6e" /></linearGradient>
              </defs>
              <circle cx="200" cy="125" r="105" fill="url(#v1)" opacity="0.88" />
              <circle cx="135" cy="235" r="105" fill="url(#v2)" opacity="0.85" />
              <circle cx="265" cy="235" r="105" fill="url(#v3)" opacity="0.85" />
              <text x="200" y="82" textAnchor="middle">Technical depth</text>
              <text x="200" y="100" textAnchor="middle" style={{ fontSize: 11, fontWeight: 500 }}>AI, systems, data</text>
              <text x="122" y="275" textAnchor="middle">Forensic thinking</text>
              <text x="122" y="293" textAnchor="middle" style={{ fontSize: 11, fontWeight: 500 }}>evidence first</text>
              <text x="278" y="275" textAnchor="middle">Ethics and law</text>
              <text x="278" y="293" textAnchor="middle" style={{ fontSize: 11, fontWeight: 500 }}>trusted conduct</text>
              <circle cx="200" cy="200" r="34" fill="#fff" />
              <text x="200" y="197" textAnchor="middle" style={{ fill: "#0f2350", fontSize: 12 }}>NFSU</text>
              <text x="200" y="212" textAnchor="middle" style={{ fill: "#0f2350", fontSize: 10 }}>graduate</text>
            </svg>
            <div className="features" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
              {WHY.map((w) => (
                <article className="feature" key={w.title}>
                  <span className={`kpi-icon tone-${w.tone}`}><Icon name={w.icon} /></span>
                  <h3>{w.title}</h3>
                  <p>{w.text}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- programmes */}
      <section className="band alt">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">Programmes</p>
            <h2>Five computing programmes, one placement process</h2>
          </div>
          <div className="programmes">
            {PROGRAMMES.map((p, i) => {
              const c = courses.find((x) => x.course === p.name);
              return (
                <article className="programme" key={p.code} style={{ borderTopColor: SERIES[i % SERIES.length] }}>
                  <span className={`kpi-icon tone-${(i % 5) + 1}`} style={{ marginBottom: "0.75rem" }}><Icon name={p.icon} /></span>
                  <h3>{p.name}</h3>
                  <p>{p.blurb}</p>
                  <HBars title={`${p.name} placement rate`} max={100} rows={[{ label: "Placed", value: c?.placement_rate ?? null, display: c?.placement_rate == null ? "—" : `${c.placement_rate}%`, color: SERIES[i % SERIES.length] }]} />
                </article>
              );
            })}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- bulletin and top packages */}
      <section className="band">
        <div className="band-inner dash-grid">
          <div className="col-7">
            <div className="section-head"><h2>Placement bulletin</h2><Link to="/login">Sign in for talk links</Link></div>
            <BulletinList posts={posts} />
          </div>
          <div className="col-5">
            <div className="section-head"><h2>Top packages</h2></div>
            <p className="muted small">Only students who chose to be listed appear here.</p>
            {s?.top_packages.length ? (
              <ol className="podium">
                {s.top_packages.map((t, i) => (
                  <li key={i}>
                    <span className="rank">{i + 1}</span>
                    <span><strong>{t.student}</strong><br /><span className="muted small">{t.course} · {t.company}</span></span>
                    <span className="cat">{lpa(t.ctc_lpa)}</span>
                  </li>
                ))}
              </ol>
            ) : <Empty>No one has opted in yet.</Empty>}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- recruiters */}
      <section className="band alt">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">Our recruiters</p>
            <h2>Organisations that recruited this session</h2>
          </div>
          {recruiters.length ? (
            <div className="marquee" aria-label="Recruiting organisations">
              <div className="marquee-track">
                {[...recruiters, ...recruiters].map((r, i) => (
                  <div className="logo-tile" key={i} aria-hidden={i >= recruiters.length}>
                    <span className="drive-logo" style={{ background: SERIES[(i % recruiters.length) % SERIES.length], color: (i % recruiters.length) % 5 === 1 ? "#1d1400" : "#fff" }}>{r.slice(0, 2).toUpperCase()}</span>
                    {r}
                  </div>
                ))}
              </div>
            </div>
          ) : <Empty>The first drives of the session are under way.</Empty>}
        </div>
      </section>

      {/* ---------------------------------------------------------------- gallery */}
      <section className="band">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">Campus</p>
            <h2>Life at NFSU Gandhinagar</h2>
          </div>
          <div className="gallery">
            <figure><img src="/images/campus-panorama.jpg" alt="Panorama of the NFSU campus with lawns and academic buildings" loading="lazy" /><figcaption>Main academic campus, Sector 9</figcaption></figure>
            <figure><img src="/images/campus-ibs.jpg" alt="Academic block beside the central lawn" loading="lazy" /><figcaption>Academic block and central lawn</figcaption></figure>
            <figure><img src="/images/campus-main.jpg" alt="The campus lit up at night from the main road" loading="lazy" /><figcaption>Campus at night</figcaption></figure>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- FAQ */}
      <section className="band alt" id="faq">
        <div className="band-inner">
          <div className="band-head">
            <p className="eyebrow">FAQs</p>
            <h2>Frequently asked questions</h2>
          </div>
          <div className="faq">
            {FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- call to action */}
      <section className="band">
        <div className="band-inner cta">
          <div>
            <h2>Ready to meet NFSU's next graduates?</h2>
            <p>Tell the Placement Cell about your roles. Once your organisation is verified you receive a Recruiter ID to sign in, see applicants and announce talks.</p>
          </div>
          <div className="cta-actions">
            <Link className="btn-gold btn-lg" to="/recruit"><Icon name="handshake" />Register your interest</Link>
            <a className="btn-ghost btn-lg" href="mailto:placement-cell@nfsu.local"><Icon name="mail" />Email the Cell</a>
          </div>
        </div>
      </section>
    </div>
  );
}
