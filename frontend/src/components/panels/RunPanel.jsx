import { useState } from 'react';
import { useStore } from '../../store/useWorkflowStore';
import { getDef } from '../../nodeTypes';
import StatusBadge from '../common/StatusBadge';
import LogList from './LogList.jsx';

export default function RunPanel() {
  const run = useStore((s) => s.run);
  const nodes = useStore((s) => s.nodes);
  const selectedId = useStore((s) => s.selectedId);
  const select = useStore((s) => s.select);
  const [onlySelected, setOnlySelected] = useState(false);

  if (run.status === 'idle') {
    return (
      <div className="panel-body">
        <p className="muted">Run the workflow to watch each step's status and logs here.</p>
      </div>
    );
  }
  const logs = onlySelected && selectedId ? run.logs.filter((l) => l.node_id === selectedId) : run.logs;

  return (
    <div className="panel-body">
      <div className="panel-title">
        <h2>Run</h2>
        <StatusBadge status={run.status} />
      </div>
      <ul className="steps-status">
        {nodes.map((n) => {
          const st = run.nodeStatus[n.id] || {};
          return (
            <li key={n.id} className={n.id === selectedId ? 'is-selected' : ''}>
              <button onClick={() => select(n.id)}>
                <span>{n.data.label || getDef(n.data.kind).label} <small>{n.id}</small></span>
                {st.attempts > 1 && <small>attempt {st.attempts}</small>}
                <StatusBadge status={st.status || 'idle'} />
              </button>
            </li>
          );
        })}
      </ul>
      <div className="logs-head">
        <h3>Logs</h3>
        {selectedId && (
          <label className="check">
            <input type="checkbox" checked={onlySelected} onChange={(e) => setOnlySelected(e.target.checked)} />
            Selected step only
          </label>
        )}
      </div>
      <LogList logs={logs} follow />
    </div>
  );
}
