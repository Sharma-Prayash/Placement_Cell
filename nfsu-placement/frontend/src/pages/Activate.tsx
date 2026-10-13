import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Icon } from "../components/icons";
import { Done, Errors } from "../components/ui";
import { api, errorLines } from "../lib/api";

export default function Activate() {
  const [params] = useSearchParams();
  const [password, setP] = useState("");
  const [confirm, setC] = useState("");
  const [err, setErr] = useState<string[]>([]);
  const [done, setDone] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== confirm) return setErr(["The two passwords do not match."]);
    setErr([]);
    try {
      const r = await api<{ username: string }>("/auth/activate", { body: { uid: params.get("uid"), token: params.get("token"), password } });
      setDone(`Password set for ${r.username}. You can sign in now.`);
    } catch (ex) {
      setErr(errorLines(ex));
    }
  };
  return (
    <div className="auth">
      <aside className="auth-art">
        <p className="eyebrow">Activate your account</p>
        <h2>Welcome to the NFSU placement portal</h2>
        <p>Choose a password only you know. The Placement Cell never emails passwords and will never ask you for yours.</p>
      </aside>
      <div className="auth-form">
        <div>
          <h1>Set your password</h1>
          <p className="muted">Use at least 12 characters. This link works once and expires after 24 hours.</p>
          {done ? (
            <>
              <Done text={done} />
              <Link className="btn" to="/login"><Icon name="login" />Sign in</Link>
            </>
          ) : (
            <form className="form" onSubmit={submit}>
              <label>New password<span className="input-icon"><Icon name="key" /><input type="password" minLength={12} value={password} onChange={(e) => setP(e.target.value)} autoComplete="new-password" required /></span></label>
              <label>Repeat the password<span className="input-icon"><Icon name="key" /><input type="password" minLength={12} value={confirm} onChange={(e) => setC(e.target.value)} autoComplete="new-password" required /></span></label>
              <Errors lines={err} />
              <button className="btn btn-lg"><Icon name="lock" />Set password</button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
