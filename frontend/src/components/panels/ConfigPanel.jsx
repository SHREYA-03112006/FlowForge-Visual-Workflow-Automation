import { Trash2 } from 'lucide-react';
import { CATEGORIES, getDef } from '../../nodeTypes';
import { useStore } from '../../store/useWorkflowStore';
import StatusBadge from '../common/StatusBadge';

const upstreamIds = (id, edges) => {
  const seen = new Set();
  const stack = [id];
  while (stack.length) {
    const cur = stack.pop();
    edges.filter((e) => e.target === cur).forEach((e) => {
      if (!seen.has(e.source)) { seen.add(e.source); stack.push(e.source); }
    });
  }
  return [...seen];
};

function Field({ def, value, onChange }) {
  const id = `f-${def.key}`;
  const common = { id, value: value ?? '', placeholder: def.placeholder };
  let input;
  if (def.type === 'select') {
    input = (
      <select {...common} onChange={(e) => onChange(e.target.value)}>
        {def.options.map((o) => <option key={o}>{o}</option>)}
      </select>
    );
  } else if (def.type === 'textarea' || def.type === 'code' || def.type === 'json') {
    input = (
      <textarea {...common} rows={def.rows || 4} spellCheck={false}
        className={def.type === 'textarea' ? '' : 'mono'} onChange={(e) => onChange(e.target.value)} />
    );
  } else if (def.type === 'number') {
    input = (
      <input {...common} type="number" step="any"
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
    );
  } else {
    input = <input {...common} type="text" spellCheck={false} onChange={(e) => onChange(e.target.value)} />;
  }
  return (
    <div className="field">
      <label htmlFor={id}>{def.label}</label>
      {input}
      {def.hint && <small>{def.hint}</small>}
    </div>
  );
}

export default function ConfigPanel() {
  const node = useStore((s) => s.nodes.find((n) => n.id === s.selectedId));
  const edges = useStore((s) => s.edges);
  const result = useStore((s) => (s.selectedId ? s.run.nodeStatus[s.selectedId] : null));
  const updateConfig = useStore((s) => s.updateConfig);
  const updateLabel = useStore((s) => s.updateLabel);
  const deleteNode = useStore((s) => s.deleteNode);
  const notify = useStore((s) => s.notify);

  if (!node) {
    return (
      <div className="panel-body">
        <p className="muted">Select a step on the canvas to edit it.</p>
        <p className="muted">
          Pass data between steps with <code>{'{{step_id.output.field}}'}</code>. Each step shows its
          id on the canvas, and its fields list what's available once you select it.
        </p>
      </div>
    );
  }

  const def = getDef(node.data.kind);
  const cfg = node.data.config;
  const upstream = upstreamIds(node.id, edges);
  const copy = (text) => navigator.clipboard?.writeText(text).then(() => notify(`Copied ${text}`, 'success'), () => {});

  return (
    <div className="panel-body">
      <div className="panel-title" style={{ '--cat': CATEGORIES[def.category].color }}>
        <span className="swatch" />
        <h2>{def.label}</h2>
        {result?.status && <StatusBadge status={result.status} />}
      </div>

      <div className="field">
        <label htmlFor="f-label">Name on canvas</label>
        <input id="f-label" value={node.data.label} placeholder={def.label}
          onChange={(e) => updateLabel(node.id, e.target.value)} />
      </div>

      <p className="ref">
        Reference this step as{' '}
        <button className="chip" onClick={() => copy(`{{${node.id}.output}}`)}>{`{{${node.id}.output}}`}</button>
      </p>
      {def.hint && <p className="muted">{def.hint}</p>}

      {def.fields.map((f) => (
        <Field key={f.key} def={f} value={cfg[f.key]} onChange={(v) => updateConfig(node.id, { [f.key]: v })} />
      ))}

      {def.retryable && (
        <fieldset>
          <legend>If this step fails</legend>
          <Field def={{ key: 'retries', label: 'Retry up to (times)', type: 'number' }}
            value={cfg.retries} onChange={(v) => updateConfig(node.id, { retries: v })} />
          <Field def={{ key: 'retry_delay', label: 'Wait between retries (seconds)', type: 'number' }}
            value={cfg.retry_delay} onChange={(v) => updateConfig(node.id, { retry_delay: v })} />
        </fieldset>
      )}

      {upstream.length > 0 && (
        <div className="field">
          <label>Data from earlier steps</label>
          <div className="chips">
            {upstream.map((u) => (
              <button key={u} className="chip" onClick={() => copy(`{{${u}.output.}}`)}>{`{{${u}.output.…}}`}</button>
            ))}
          </div>
          <small>Click to copy, then add the field name after "output.".</small>
        </div>
      )}

      {result?.error && <div className="result result-error"><b>Error</b><pre>{String(result.error)}</pre></div>}
      {result?.output !== undefined && result.output !== null && (
        <div className="result">
          <b>Last output</b>
          <pre>{JSON.stringify(result.output, null, 2).slice(0, 2000)}</pre>
        </div>
      )}

      <button className="btn btn-danger" onClick={() => deleteNode(node.id)}>
        <Trash2 size={15} /> Delete step
      </button>
    </div>
  );
}
