import { FormEvent, useCallback, useEffect, useState } from "react";
import BulletinList, { Post } from "../components/BulletinList";
import { Icon } from "../components/icons";
import { Done, Errors, Section } from "../components/ui";
import { api, errorLines } from "../lib/api";
import { useAuth } from "../lib/auth";
import { KIND } from "../lib/format";

export default function Bulletin() {
  const { me } = useAuth();
  const [posts, setPosts] = useState<Post[]>([]);
  const load = useCallback(() => api<Post[]>("/bulletin").then(setPosts).catch(() => setPosts([])), []);
  useEffect(() => { load(); }, [load]);
  const canPost = me && ["admin", "officer", "recruiter"].includes(me.role);
  return (
    <div className="stack">
    <div className="banner">
      <span className="kpi-icon" style={{ background: "rgba(255,255,255,0.14)", color: "var(--gold)" }}><Icon name="megaphone" /></span>
      <div className="grow">
        <h1>Placement bulletin</h1>
        <p>Updates, pre-placement talks, tests and interviews. Students join talks through the platform so attendance is recorded.</p>
      </div>
      <span className="chip">{posts.length} posts</span>
    </div>
    <div className="split">
      <Section title="Latest">
        <BulletinList posts={posts} canJoin={me?.role === "student"} />
      </Section>
      {canPost && <div className="card"><PostForm onPosted={load} recruiter={me!.role === "recruiter"} /></div>}
    </div>
    </div>
  );
}

function PostForm({ onPosted, recruiter }: { onPosted: () => void; recruiter: boolean }) {
  const [f, setF] = useState({ kind: recruiter ? "ppt" : "update", title: "", body: "", drive: "", starts_at: "", ends_at: "", meeting_url: "", visibility: "members" });
  const [drives, setDrives] = useState<{ id: number; title: string; company_name: string }[]>([]);
  const [err, setErr] = useState<string[]>([]);
  const [done, setDone] = useState("");
  useEffect(() => {
    api(recruiter ? "/recruiter/drives" : "/staff/drives").then(setDrives).catch(() => setDrives([]));
  }, [recruiter]);
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const timed = ["ppt", "test", "interview"].includes(f.kind);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr([]);
    setDone("");
    try {
      const body: Record<string, unknown> = { kind: f.kind, title: f.title, body: f.body, visibility: f.visibility };
      if (f.drive) body.drive = Number(f.drive);
      if (f.starts_at) body.starts_at = new Date(f.starts_at).toISOString();
      if (f.ends_at) body.ends_at = new Date(f.ends_at).toISOString();
      if (f.meeting_url) body.meeting_url = f.meeting_url;
      const p = await api<Post>("/bulletin", { body });
      setDone(p.status === "approved" ? "Published." : "Sent to the Placement Cell for approval.");
      setF({ ...f, title: "", body: "", meeting_url: "" });
      onPosted();
    } catch (ex) {
      setErr(errorLines(ex));
    }
  };
  return (
    <Section title={recruiter ? "Announce a talk, test or interview" : "Post to the bulletin"}>
      <form className="form" onSubmit={submit}>
        <label>Type
          <select value={f.kind} onChange={set("kind")}>
            {Object.entries(KIND).filter(([k]) => !recruiter || ["ppt", "test", "interview"].includes(k)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Title<input value={f.title} onChange={set("title")} required maxLength={150} /></label>
        <label>Details<textarea value={f.body} onChange={set("body")} rows={3} maxLength={5000} /></label>
        {(timed || drives.length > 0) && (
          <label>Drive{timed && " (attendance is tracked for its applicants)"}
            <select value={f.drive} onChange={set("drive")} required={recruiter}>
              <option value="">{recruiter ? "Choose a drive" : "Not linked to a drive"}</option>
              {drives.map((d) => <option key={d.id} value={d.id}>{d.company_name}: {d.title}</option>)}
            </select>
          </label>
        )}
        <div className="row">
          <label>Starts<input type="datetime-local" value={f.starts_at} onChange={set("starts_at")} required={timed} /></label>
          <label>Ends<input type="datetime-local" value={f.ends_at} onChange={set("ends_at")} required={timed} /></label>
        </div>
        {timed && <label>Meeting link (students only get it through the Join button)<input type="url" value={f.meeting_url} onChange={set("meeting_url")} placeholder="https://" /></label>}
        {!recruiter && (
          <label>Who can see it
            <select value={f.visibility} onChange={set("visibility")}>
              <option value="members">Signed-in users only</option>
              <option value="public">Everyone, including the public overview</option>
            </select>
          </label>
        )}
        <Errors lines={err} />
        <Done text={done} />
        <button className="btn"><Icon name={recruiter ? "approve" : "megaphone"} />{recruiter ? "Send for approval" : "Publish"}</button>
      </form>
    </Section>
  );
}
