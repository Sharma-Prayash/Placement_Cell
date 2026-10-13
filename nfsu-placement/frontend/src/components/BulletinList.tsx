import { useState } from "react";
import { api, errorLines } from "../lib/api";
import { KIND, when } from "../lib/format";
import { Icon, IconName } from "./icons";
import { Empty, Errors } from "./ui";

const KIND_ICON: Record<string, IconName> = { update: "megaphone", cell_event: "calendar", ppt: "video", test: "file", interview: "users" };

export interface Post {
  id: number;
  kind: string;
  title: string;
  body: string;
  starts_at?: string | null;
  ends_at?: string | null;
  pinned: boolean;
  author_name?: string;
  company_name?: string | null;
  status?: string;
  has_meeting_link?: boolean;
  my_attendance?: string | null;
  expected_to_attend?: boolean;
}

/** Shared list used on the public overview and the signed-in bulletin.
 *  `body` is sanitised server-side and still rendered as plain text here. */
export default function BulletinList({ posts, canJoin }: { posts: Post[]; canJoin?: boolean }) {
  const [err, setErr] = useState<string[]>([]);
  const join = async (id: number) => {
    setErr([]);
    try {
      const r = await api<{ meeting_url: string }>(`/bulletin/${id}/join`, { method: "POST" });
      if (r.meeting_url.startsWith("https://")) window.open(r.meeting_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setErr(errorLines(e));
    }
  };
  if (!posts.length) return <Empty>No announcements right now.</Empty>;
  return (
    <>
      <Errors lines={err} />
      <ol className="bulletin">
        {posts.map((p) => (
          <li key={p.id} className={`bulletin-item kind-${p.kind}${p.pinned ? " pinned" : ""}`}>
            <div className="bulletin-when">
              {p.starts_at ? (
                <>
                  <strong>{new Date(p.starts_at).toLocaleDateString("en-IN", { day: "numeric" })}</strong>
                  <span>{new Date(p.starts_at).toLocaleDateString("en-IN", { month: "short" })}</span>
                </>
              ) : (
                <span className="bulletin-notice">Notice</span>
              )}
            </div>
            <div className="bulletin-body">
              <p className="bulletin-kind">
                <Icon name={KIND_ICON[p.kind] ?? "bell"} />
                {KIND[p.kind] ?? p.kind}
                {p.author_name && ` from ${p.author_name}`}
                {p.status && p.status !== "approved" && <em className="pending"> waiting for Placement Cell approval</em>}
              </p>
              <h3>{p.title}</h3>
              {p.body && <p className="bulletin-text">{p.body.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").trim()}</p>}
              {p.starts_at && <p className="muted small"><Icon name="clock" /> {when(p.starts_at)}{p.ends_at && ` to ${when(p.ends_at)}`}</p>}
              {canJoin && p.has_meeting_link && p.status === "approved" && (
                <div className="row">
                  <button className="btn btn-sm" onClick={() => join(p.id)}><Icon name="video" />Join through the platform</button>
                  {p.my_attendance === "present" && <span className="ok-text"><Icon name="checkCircle" />Your attendance is recorded</span>}
                  {p.expected_to_attend && !p.my_attendance && <span className="muted">You applied to this drive, so attendance counts</span>}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}
