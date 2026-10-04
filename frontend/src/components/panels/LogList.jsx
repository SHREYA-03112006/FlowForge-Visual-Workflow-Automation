import { useEffect, useRef } from 'react';
import { fmtClock } from '../../utils/colors';

export default function LogList({ logs, follow = false }) {
  const end = useRef(null);
  useEffect(() => { if (follow) end.current?.scrollIntoView({ block: 'end' }); }, [logs.length, follow]);
  if (!logs.length) return <p className="muted">No log lines yet.</p>;
  return (
    <ol className="logs">
      {logs.map((l, i) => (
        <li key={i} className={`log-${(l.level || 'info').toLowerCase()}`}>
          <time>{fmtClock(l.timestamp)}</time>
          {l.node_id && <b>{l.node_id}</b>}
          <span>{l.message}</span>
        </li>
      ))}
      <li ref={end} className="log-end" />
    </ol>
  );
}
