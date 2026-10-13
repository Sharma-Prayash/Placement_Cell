import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "../components/icons";
import { Errors } from "../components/ui";
import { api, ApiError, errorLines } from "../lib/api";
import { homeFor, Me, useAuth } from "../lib/auth";

export default function Login() {
  const { setMe } = useAuth();
  const nav = useNavigate();
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [otp, setOtp] = useState("");
  const [needOtp, setNeedOtp] = useState(false);
  const [err, setErr] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr([]);
    try {
      const me = await api<Me>("/auth/login", { body: { username, password, otp } });
      setMe(me);
      nav(homeFor(me.role));
    } catch (ex) {
      if (ex instanceof ApiError && ex.data.otp_required) setNeedOtp(true);
      setErr(errorLines(ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <aside className="auth-art">
        <p className="eyebrow">Placement portal</p>
        <h2>One secure sign-in for students, recruiters and the Placement Cell</h2>
        <p>Your session ends after 15 minutes without activity. Staff accounts use a code from an authenticator app.</p>
        <ul className="ticks">
          <li><Icon name="shield" />Policy-checked applications</li>
          <li><Icon name="lock" />Encrypted personal details</li>
          <li><Icon name="approve" />Two-person approvals</li>
          <li><Icon name="scroll" />Tamper-evident audit log</li>
        </ul>
      </aside>
      <div className="auth-form">
        <div>
          <h1>Sign in</h1>
          <p className="muted">Students use their Placement ID. Recruiters use the Recruiter ID from their activation email.</p>
          <form onSubmit={submit} className="form">
            <label>
              Placement ID, Recruiter ID or staff ID
              <span className="input-icon"><Icon name="user" /><input value={username} onChange={(e) => setU(e.target.value)} autoComplete="username" required maxLength={150} /></span>
            </label>
            <label>
              Password
              <span className="input-icon"><Icon name="key" /><input type="password" value={password} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required /></span>
            </label>
            {needOtp && (
              <label>
                Code from your authenticator app
                <span className="input-icon"><Icon name="fingerprint" /><input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={6} /></span>
              </label>
            )}
            <Errors lines={err} />
            <button className="btn btn-lg" disabled={busy}><Icon name="login" />{busy ? "Signing in…" : "Sign in"}</button>
          </form>
          <p className="small muted" style={{ marginTop: "1.25rem" }}>
            New recruiter? <Link to="/recruit">Register your organisation</Link>. Forgotten password? Contact the Placement Cell.
          </p>
        </div>
      </div>
    </div>
  );
}
