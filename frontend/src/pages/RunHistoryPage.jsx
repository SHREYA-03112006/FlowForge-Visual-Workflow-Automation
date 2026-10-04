import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { api, normalizeStatus } from '../services/api';
import StatusBadge from '../components/common/StatusBadge';
import LogList from '../components/panels/LogList.jsx';
import { fmtDuration, fmtTime } from '../utils/colors';

function RunDetail({ id }) {
  const [ex, setEx] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let stop = false;
    let timer;
    const tick = async () => {
      try {
        const data = await api.getExecution(id);
        if (stop) return;
        setEx(data);
        if (data.status === 'running' || data.status === 'pending') timer = setTimeout(tick, 1500);
      } catch (e) { if (!stop) setError(e.message); }
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);

  if (error) return <p className="notice notice-error">{error}</p>;
  if (!ex) return <p className="muted">Loading run…</p>;
  return (
    <div className="run-detail">
      <ul className="steps-status">
        {Object.entries(ex.nodeStatus).map(([nodeId, st]) => (
          <li key={nodeId}>
            <div>
              <span>{nodeId}</span>
              {st.attempts > 1 && <small>{st.attempts} attempts</small>}
              <StatusBadge status={st.status} />
            </div>
            {st.error && <pre className="result-error">{String(st.error)}</pre>}
          </li>
        ))}
      </ul>
      <LogList logs={ex.logs} />
    </div>
  );
}

export default function RunHistoryPage() {
  const [params] = useSearchParams();
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(params.get('open'));
  const workflow = params.get('workflow');

  const refresh = useCallback(() => api.listExecutions(workflow)
    .then((r) => { setRuns(r); setError(''); })
    .catch((e) => { setError(e.message); setRuns([]); }), [workflow]);

  useEffect(() => { refresh(); }, [refresh]);
  // Keep the list fresh while anything is still running.
  useEffect(() => {
    if (!runs?.some((r) => ['running', 'pending'].includes(r.status))) return undefined;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [runs, refresh]);

  return (
    <section className="page">
      <div className="page-head">
        <h1>Run history</h1>
        <button className="btn" onClick={refresh}><RefreshCw size={14} /> Refresh</button>
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      {runs === null && <p className="muted">Loading runs…</p>}
      {runs?.length === 0 && !error && (
        <div className="empty">
          <h2>No runs yet</h2>
          <p>Run a workflow from the editor and it will show up here with its logs.</p>
        </div>
      )}
      {runs?.length > 0 && (
        <ul className="rows">
          {runs.map((r) => (
            <li key={r.id} className="row-stack">
              <button className="row-main" onClick={() => setOpen(open === String(r.id) ? null : String(r.id))}>
                <strong>{r.workflow_name || `Workflow ${r.workflow_id}`}</strong>
                <small>{fmtTime(r.started_at)} {fmtDuration(r.started_at, r.finished_at)}</small>
                <StatusBadge status={normalizeStatus(r.status)} />
              </button>
              {open === String(r.id) && <RunDetail id={r.id} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
