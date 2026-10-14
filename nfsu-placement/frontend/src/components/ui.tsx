import { ReactNode } from "react";
import { Icon, IconName } from "./icons";

type Decision = "ALLOW" | "FLAG" | "BLOCK";
const DECISION_TEXT: Record<Decision, string> = { ALLOW: "Clear", FLAG: "Review", BLOCK: "Blocked" };

/** Evidence-tag style verdict marker: the one distinctive element of the interface. */
export function Verdict({ decision }: { decision?: Decision }) {
  if (!decision) return null;
  return <span className={`tag tag-${decision.toLowerCase()}`}>{DECISION_TEXT[decision] ?? decision}</span>;
}

export function Category({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">—</span>;
  return <span className="cat">{value}</span>;
}

export function Reasons({ reasons }: { reasons?: { severity: string; message: string }[] }) {
  const shown = (reasons ?? []).filter((r) => r.severity !== "info");
  if (!shown.length) return null;
  return (
    <ul className="reasons">
      {shown.map((r, i) => (
        <li key={i} className={`reason-${r.severity}`}>
          {r.message}
        </li>
      ))}
    </ul>
  );
}

export function Errors({ lines }: { lines: string[] }) {
  if (!lines.length) return null;
  return (
    <div className="notice notice-error" role="alert">
      {lines.map((l, i) => (
        <p key={i}>{l}</p>
      ))}
    </div>
  );
}

export function Done({ text }: { text: string }) {
  return text ? (
    <div className="notice notice-ok" role="status">
      {text}
    </div>
  ) : null;
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="section">
      <header className="section-head">
        <h2>{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

/** Stat card with an icon. `tone` picks one of five colour pairs. */
export function Kpi({ icon, label, value, tone = 1 }: { icon: IconName; label: string; value: ReactNode; tone?: 1 | 2 | 3 | 4 | 5 }) {
  return (
    <div className="kpi">
      <span className={`kpi-icon tone-${tone}`}><Icon name={icon} /></span>
      <div><dt>{label}</dt><dd>{value}</dd></div>
    </div>
  );
}

const CHIP_TONE: Record<string, string> = {
  accepted: "ok", selected: "ok", joined: "ok", approved: "ok", eligible: "ok", registered: "ok", open: "info", present: "ok",
  pending: "warn", applied: "info", shortlisted: "warn", required: "warn", submitted: "info",
  active: "ok", awaiting: "warn", declined: "bad", rejected: "bad", not_joined: "bad", ineligible: "bad", expired: "bad", closed: "bad", deregistered: "bad", unplaced: "warn", internship_only: "info", fte_only: "ok", internship_plus_fte: "ok",
};

/** Small coloured status label. Display only; never used to decide anything. */
export function Chip({ value, label }: { value?: string | null; label?: string }) {
  if (!value) return <span className="muted">—</span>;
  const tone = CHIP_TONE[value];
  const text = label ?? value.replace(/_/g, " ");
  return <span className={`chip${tone ? ` chip-${tone}` : ""}`}>{text.charAt(0).toUpperCase() + text.slice(1)}</span>;
}

/** Card with a heading, used to frame charts and summaries. */
export function Card({ title, icon, sub, children, className = "" }: { title: string; icon?: IconName; sub?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      <h3>{icon && <Icon name={icon} />}{title}</h3>
      {sub && <p className="card-sub">{sub}</p>}
      {children}
    </section>
  );
}

export const initials = (name?: string) => (name ?? "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
