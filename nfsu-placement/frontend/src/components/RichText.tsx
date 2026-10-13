import { ReactNode } from "react";

/** Renders the assistant's light markup (**bold**, _italic_, `code`, "- " lists) as React elements.
 *  Nothing is ever parsed as HTML and links in the text are not made clickable, so a crafted
 *  answer cannot inject markup or a javascript: link. */
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`|(?<![\w])_([^_]+)_(?![\w])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] !== undefined) out.push(<strong key={`${key}-${i++}`}>{m[1]}</strong>);
    else if (m[2] !== undefined) out.push(<code key={`${key}-${i++}`}>{m[2]}</code>);
    else out.push(<em key={`${key}-${i++}`}>{m[3]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = (k: number) => {
    if (list.length) blocks.push(<ul key={`ul-${k}`}>{list.map((l, i) => <li key={i}>{inline(l, `li-${k}-${i}`)}</li>)}</ul>);
    list = [];
  };
  text.split("\n").forEach((raw, k) => {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*(?:[-•*]|\d+\.)\s+(.*)$/);
    if (bullet && !line.startsWith("**")) {
      list.push(bullet[1]);
      return;
    }
    flush(k);
    if (!line.trim()) return;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push(heading ? <p key={k} className="rt-h">{inline(heading[1], `h-${k}`)}</p> : <p key={k}>{inline(line, `p-${k}`)}</p>);
  });
  flush(-1);
  return <div className="richtext">{blocks}</div>;
}
