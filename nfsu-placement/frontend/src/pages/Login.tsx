import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "../components/icons";
import { Errors } from "../components/ui";
import { api, ApiError, errorLines } from "../lib/api";
import { homeFor, Me, useAuth } from "../lib/auth";

interface Challenge { mfa_required: true; channel: "email" | "totp"; sent_to?: string; expires_in: number; attempts_left: number; resend_after?: number }

/** Two-step sign-in. Step 1 checks the password; if the role needs a second factor the server emails a
 *  6-digit code to the official address and only step 2 signs the session in. Nothing here is trusted:
 *  every rule (expiry, attempts, lockout, resend limits) is enforced by the server. */
export default function Login() {
  const { setMe } = useAuth();
  const nav = useNavigate();
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [err, setErr] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);
  useEffect(() => { if (challenge) codeRef.current?.focus(); }, [challenge]);

  const done = (me: Me) => { setMe(me); nav(homeFor(me.role)); };
  const restart = () => { setChallenge(null); setCode(""); setP(""); setNote(""); };

  const submitPassword = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr([]); setNote("");
    try {
      const r = await api<Me | Challenge>("/auth/login", { body: { username, password } });
      if ("mfa_required" in r) {
        setChallenge(r);
        setCooldown(r.resend_after ?? 0);
        setP("");  // not needed for step 2; do not keep it around
      } else done(r);
    } catch (ex) {
      setErr(errorLines(ex));
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr([]); setNote("");
    try {
      done(await api<Me>("/auth/login/verify", { body: { code } }));
    } catch (ex) {
      setErr(errorLines(ex));
      setCode("");
      if (ex instanceof ApiError && ex.data.restart) setChallenge(null);
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setErr([]); setNote("");
    try {
      const r = await api<Challenge>("/auth/login/resend", { method: "POST" });
      setChallenge(r);
      setCooldown(r.resend_after ?? 60);
      setNote(`A new code was sent to ${r.sent_to}. The previous code no longer works.`);
    } catch (ex) {
      setErr(errorLines(ex));
      if (ex instanceof ApiError && ex.data.restart) setChallenge(null);
    }
  };

  return (
    <div className="auth">
      <aside className="auth-art">
        <p className="eyebrow">Placement portal</p>
        <h2>One secure sign-in for students, recruiters and the Placement Cell</h2>
        <p>After your password we email a one-time code to your official address. Your session ends after 15 minutes without activity.</p>
        <ul className="ticks">
          <li><Icon name="mail" />Code sent to your official email</li>
          <li><Icon name="lock" />Encrypted personal details</li>
          <li><Icon name="approve" />Two-person approvals</li>
          <li><Icon name="scroll" />Tamper-evident audit log</li>
        </ul>
      </aside>
      <div className="auth-form">
        {!challenge ? (
          <div>
            <h1>Sign in</h1>
            <p className="muted">Students use their Placement ID. Recruiters use the Recruiter ID from their activation email.</p>
            <form onSubmit={submitPassword} className="form">
              <label>
                Placement ID, Recruiter ID or staff ID
                <span className="input-icon"><Icon name="user" /><input value={username} onChange={(e) => setU(e.target.value)} autoComplete="username" required maxLength={150} /></span>
              </label>
              <label>
                Password
                <span className="input-icon"><Icon name="key" /><input type="password" value={password} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required /></span>
              </label>
              <Errors lines={err} />
              <button className="btn btn-lg" disabled={busy}><Icon name="login" />{busy ? "Checking…" : "Continue"}</button>
            </form>
            <p className="small muted" style={{ marginTop: "1.25rem" }}>
              New recruiter? <Link to="/recruit">Register your organisation</Link>. Forgotten password? Contact the Placement Cell.
            </p>
          </div>
        ) : (
          <div>
            <span className="kpi-icon tone-2" style={{ marginBottom: "1rem" }}><Icon name={challenge.channel === "email" ? "mail" : "fingerprint"} /></span>
            <h1>{challenge.channel === "email" ? "Check your email" : "Enter your app code"}</h1>
            <p className="muted">
              {challenge.channel === "email"
                ? <>We sent a 6-digit code to <strong>{challenge.sent_to}</strong>, your official email on record. It expires in {Math.round(challenge.expires_in / 60)} minutes and works once.</>
                : "Open your authenticator app and enter the 6-digit code it shows for NFSU Placement."}
            </p>
            <form onSubmit={submitCode} className="form">
              <label>
                Sign-in code
                <input ref={codeRef} className="otp-input" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required placeholder="••••••" aria-describedby="otp-help" />
              </label>
              <p id="otp-help" className="fine">Never share this code. The Placement Cell will never ask you for it.</p>
              {note && <div className="notice notice-ok" role="status">{note}</div>}
              <Errors lines={err} />
              <button className="btn btn-lg" disabled={busy || code.length !== 6}><Icon name="shield" />{busy ? "Verifying…" : "Verify and sign in"}</button>
            </form>
            <div className="row wrap" style={{ marginTop: "1rem", justifyContent: "space-between" }}>
              {challenge.channel === "email" && (
                <button type="button" className="btn-quiet btn-sm" onClick={resend} disabled={cooldown > 0}>
                  {cooldown > 0 ? `Send a new code in ${cooldown}s` : "Send a new code"}
                </button>
              )}
              <button type="button" className="btn-quiet btn-sm" onClick={restart}>Use a different account</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
