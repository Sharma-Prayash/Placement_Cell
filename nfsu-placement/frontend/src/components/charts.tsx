/* Small dependency-free SVG charts. Each chart has an accessible name and a hidden data table,
   so screen readers get the same numbers the picture shows. `null` means "suppressed" (a public
   figure computed from too few students) and is drawn as an empty, dashed slot. */
import { ReactNode } from "react";

export const SERIES = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)"];
const fmt = (v: number) => (Number.isInteger(v) ? v.toLocaleString("en-IN") : v.toLocaleString("en-IN", { maximumFractionDigits: 2 }));

function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

function DataTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number | null)[][] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c ?? "not published"}</td>)}</tr>)}</tbody>
    </table>
  );
}

export function Legend({ items }: { items: { label: string; color: string; value?: ReactNode }[] }) {
  return (
    <ul className="legend">
      {items.map((i) => <li key={i.label}><i style={{ background: i.color }} />{i.label}{i.value !== undefined && <b>{i.value}</b>}</li>)}
    </ul>
  );
}

/** Vertical grouped bar chart. */
export function BarChart({ title, categories, series, height = 240, unit = "" }: {
  title: string; categories: string[]; series: { name: string; color: string; values: (number | null)[] }[]; height?: number; unit?: string;
}) {
  const W = 560, H = height, padL = 34, padB = 46, padT = 18;
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values.map((v) => v ?? 0))));
  const plotW = W - padL - 8, plotH = H - padB - padT;
  const groupW = plotW / Math.max(1, categories.length);
  const barW = Math.min(30, (groupW * 0.72) / series.length);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const y = (v: number) => padT + plotH - (v / max) * plotH;
  return (
    <figure style={{ margin: 0 }}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={padL} x2={W - 8} y1={y(t)} y2={y(t)} />
            <text x={padL - 6} y={y(t) + 4} textAnchor="end">{fmt(t)}</text>
          </g>
        ))}
        {categories.map((c, ci) => {
          const gx = padL + ci * groupW + (groupW - barW * series.length) / 2;
          const words = c.split(" ");
          const mid = Math.ceil(words.length / 2);
          return (
            <g key={c}>
              {series.map((s, si) => {
                const v = s.values[ci];
                const x = gx + si * barW;
                if (v === null || v === undefined) {
                  return <rect key={s.name} x={x + 1} y={y(max * 0.12)} width={barW - 2} height={plotH * 0.12} fill="none" style={{ stroke: s.color }} strokeDasharray="3 3" rx="3"><title>{`${c}, ${s.name}: not published (too few students)`}</title></rect>;
                }
                const top = y(v);
                return (
                  <g key={s.name}>
                    <rect className="bar" x={x + 1} y={top} width={barW - 2} height={Math.max(0, padT + plotH - top)} style={{ fill: s.color }} rx="4">
                      <title>{`${c}, ${s.name}: ${fmt(v)}${unit}`}</title>
                      <animate attributeName="height" from="0" to={Math.max(0, padT + plotH - top)} dur="0.8s" fill="freeze" />
                      <animate attributeName="y" from={padT + plotH} to={top} dur="0.8s" fill="freeze" />
                    </rect>
                    <text className="val" x={x + barW / 2} y={top - 5} textAnchor="middle">{fmt(v)}{unit}</text>
                  </g>
                );
              })}
              <text x={padL + ci * groupW + groupW / 2} y={H - padB + 18} textAnchor="middle">{words.slice(0, mid).join(" ")}</text>
              <text x={padL + ci * groupW + groupW / 2} y={H - padB + 32} textAnchor="middle">{words.slice(mid).join(" ")}</text>
            </g>
          );
        })}
      </svg>
      <Legend items={series.map((s) => ({ label: s.name, color: s.color }))} />
      <DataTable caption={title} head={["", ...series.map((s) => s.name)]} rows={categories.map((c, i) => [c, ...series.map((s) => s.values[i])])} />
    </figure>
  );
}

/** Donut with a centre figure and a legend beside it. */
export function Donut({ title, slices, center, centerLabel }: {
  title: string; slices: { label: string; value: number; color: string }[]; center?: ReactNode; centerLabel?: string;
}) {
  const total = slices.reduce((a, s) => a + s.value, 0);
  const R = 52, C = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div className="donut-wrap">
      <svg className="chart" viewBox="0 0 140 140" role="img" aria-label={title}>
        <circle cx="70" cy="70" r={R} fill="none" style={{ stroke: "var(--c-track)" }} strokeWidth="18" />
        {total > 0 && slices.map((s) => {
          const len = (s.value / total) * C;
          const el = (
            <circle key={s.label} cx="70" cy="70" r={R} fill="none" style={{ stroke: s.color }} strokeWidth="18"
              strokeDasharray={`${Math.max(0, len - 1.5)} ${C}`} strokeDashoffset={-acc} transform="rotate(-90 70 70)">
              <title>{`${s.label}: ${fmt(s.value)} (${Math.round((100 * s.value) / total)}%)`}</title>
            </circle>
          );
          acc += len;
          return el;
        })}
        <text className="donut-center" x="70" y={centerLabel ? 72 : 78} textAnchor="middle">{center ?? fmt(total)}</text>
        {centerLabel && <text x="70" y="90" textAnchor="middle">{centerLabel}</text>}
      </svg>
      <Legend items={slices.map((s) => ({ label: s.label, color: s.color, value: total ? `${fmt(s.value)} · ${Math.round((100 * s.value) / total)}%` : 0 }))} />
      <DataTable caption={title} head={["Group", "Count"]} rows={slices.map((s) => [s.label, s.value])} />
    </div>
  );
}

/** Ring gauge for a percentage. */
export function Gauge({ label, percent, color = "var(--c1)" }: { label: string; percent: number | null; color?: string }) {
  const R = 40, C = 2 * Math.PI * R;
  const p = percent === null ? 0 : Math.max(0, Math.min(100, percent));
  return (
    <div className="gauge">
      <svg className="chart" viewBox="0 0 100 100" role="img" aria-label={`${label}: ${percent === null ? "not published" : `${percent}%`}`}>
        <circle cx="50" cy="50" r={R} fill="none" style={{ stroke: "var(--c-track)" }} strokeWidth="10" strokeDasharray={percent === null ? "4 4" : undefined} />
        {percent !== null && (
          <circle cx="50" cy="50" r={R} fill="none" style={{ stroke: color }} strokeWidth="10" strokeLinecap="round" strokeDasharray={`${(p / 100) * C} ${C}`} transform="rotate(-90 50 50)" />
        )}
        <text className="donut-center" x="50" y="56" textAnchor="middle" style={{ fontSize: 18 }}>{percent === null ? "—" : `${percent}%`}</text>
      </svg>
      <p>{label}</p>
    </div>
  );
}

/** Horizontal bars, one row each. */
export function HBars({ title, rows, max }: { title: string; rows: { label: string; value: number | null; display?: ReactNode; color?: string }[]; max?: number }) {
  const m = max ?? Math.max(1, ...rows.map((r) => r.value ?? 0));
  return (
    <div className="hbar" role="img" aria-label={title}>
      {rows.map((r, i) => (
        <div className="hbar-row" key={r.label}>
          <span>{r.label}</span>
          <div className="hbar-track">
            {r.value !== null && <div className="hbar-fill" style={{ width: `${(100 * r.value) / m}%`, background: r.color ?? SERIES[i % SERIES.length], animationDelay: `${i * 80}ms` }} />}
          </div>
          <b>{r.display ?? (r.value === null ? "—" : fmt(r.value))}</b>
        </div>
      ))}
    </div>
  );
}

/** Funnel: each step's bar is proportional to the first step. */
export function Funnel({ title, steps }: { title: string; steps: { label: string; value: number }[] }) {
  const top = Math.max(1, steps[0]?.value ?? 1);
  return (
    <div className="funnel" role="img" aria-label={`${title}: ${steps.map((s) => `${s.label} ${s.value}`).join(", ")}`}>
      {steps.map((s, i) => (
        <div className="funnel-step" key={s.label}>
          <span>{s.label}</span>
          <div className="funnel-bar" style={{ width: `${Math.max(8, (100 * s.value) / top)}%`, background: SERIES[i % SERIES.length], animationDelay: `${i * 100}ms`, color: i === 1 ? "#1d1400" : "#fff" }}>{fmt(s.value)}</div>
        </div>
      ))}
    </div>
  );
}

/** Range chart for packages: highest, average and median on one scale. */
export function PackageRange({ highest, average, median, unit = " LPA", title }: { highest: number; average: number; median: number; unit?: string; title: string }) {
  const max = Math.ceil((highest * 1.12) / 5) * 5;
  const W = 520, x = (v: number) => 12 + (v / max) * (W - 24);
  const marks = [
    { label: "Median", v: median, color: "var(--c3)" },
    { label: "Average", v: average, color: "var(--c2)" },
    { label: "Highest", v: highest, color: "var(--c1)" },
  ];
  return (
    <figure style={{ margin: 0 }}>
      <svg className="chart" viewBox={`0 0 ${W} 92`} role="img" aria-label={`${title}: median ${median}, average ${average}, highest ${highest}${unit}`}>
        <rect x="12" y="38" width={W - 24} height="12" rx="6" style={{ fill: "var(--c-track)" }} />
        <rect x="12" y="38" width={x(highest) - 12} height="12" rx="6" fill="url(#pkg)" />
        <defs><linearGradient id="pkg"><stop offset="0" stopColor="#2f9e8f" /><stop offset="0.6" stopColor="#e0a526" /><stop offset="1" stopColor="#1d3a78" /></linearGradient></defs>
        {marks.map((m, i) => (
          <g key={m.label}>
            <circle cx={x(m.v)} cy="44" r="8" fill="#fff" style={{ stroke: m.color }} strokeWidth="4"><title>{`${m.label}: ${fmt(m.v)}${unit}`}</title></circle>
            <text className="val" x={x(m.v)} y={i === 1 ? 78 : 22} textAnchor="middle">{fmt(m.v)}</text>
            <text x={x(m.v)} y={i === 1 ? 90 : 10} textAnchor="middle">{m.label}</text>
          </g>
        ))}
      </svg>
    </figure>
  );
}
