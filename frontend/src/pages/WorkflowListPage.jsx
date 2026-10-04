import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Play, Plus, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { useStore } from '../store/useWorkflowStore';
import { fmtTime } from '../utils/colors';

export default function WorkflowListPage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const notify = useStore((s) => s.notify);

  const refresh = () => api.listWorkflows().then((r) => { setItems(r); setError(''); })
    .catch((e) => { setError(e.message); setItems([]); });
  useEffect(() => { refresh(); }, []);

  const remove = async (w) => {
    if (!window.confirm(`Delete "${w.name}"? This can't be undone.`)) return;
    try { await api.deleteWorkflow(w.id); notify('Workflow deleted', 'success'); refresh(); } catch (e) { notify(e.message, 'error'); }
  };

  const runNow = async (w) => {
    try {
      const wf = await api.getWorkflow(w.id);
      const graph = wf.graph || { nodes: [], edges: [] };
      const manual = graph.nodes.find((n) => (n.data?.kind || n.type) === 'manual');
      let input = {};
      try { input = manual?.data?.config?.input ? JSON.parse(manual.data.config.input) : {}; } catch { /* use empty input */ }
      const { execution_id } = await api.runWorkflow(w.id, input);
      navigate(`/runs?open=${execution_id}`);
    } catch (e) { notify(e.message, 'error'); }
  };

  return (
    <section className="page">
      <div className="page-head">
        <h1>Workflows</h1>
        <Link to="/editor" className="btn btn-primary"><Plus size={15} /> New workflow</Link>
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      {items === null && <p className="muted">Loading workflows…</p>}
      {items?.length === 0 && !error && (
        <div className="empty">
          <h2>No workflows yet</h2>
          <p>Create one, drag a trigger onto the canvas, and connect the steps you want to automate.</p>
        </div>
      )}
      {items?.length > 0 && (
        <ul className="rows">
          {items.map((w) => (
            <li key={w.id}>
              <Link to={`/editor/${w.id}`} className="row-main">
                <strong>{w.name}</strong>
                <small>{w.updated_at ? `Updated ${fmtTime(w.updated_at)}` : `Workflow ${w.id}`}</small>
              </Link>
              <button className="btn" onClick={() => runNow(w)}><Play size={14} /> Run</button>
              <button className="btn btn-quiet" onClick={() => remove(w)} aria-label={`Delete ${w.name}`}><Trash2 size={15} /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
