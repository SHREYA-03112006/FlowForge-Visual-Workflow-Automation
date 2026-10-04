import { memo, useEffect } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { CATEGORIES, getDef, getOutputs, isTrigger } from '../../nodeTypes';
import { useStore } from '../../store/useWorkflowStore';
import StatusBadge from '../common/StatusBadge';

function StepNode({ id, data, selected }) {
  const def = getDef(data.kind);
  const status = useStore((s) => s.run.nodeStatus[id]?.status) || 'idle';
  const outputs = getOutputs(data.kind, data.config);
  const updateInternals = useUpdateNodeInternals();
  const signature = outputs.join('|');

  // Outputs of If/else and Switch can change; tell React Flow to re-measure handles.
  useEffect(() => { updateInternals(id); }, [signature, id, updateInternals]);

  const Icon = def.icon;
  const rows = Math.max(outputs.length, 1);
  return (
    <div
      className={`step status-${status}${selected ? ' is-selected' : ''}`}
      style={{ '--cat': CATEGORIES[def.category].color, minHeight: 58 + Math.max(0, rows - 2) * 24 }}
    >
      {!isTrigger(data.kind) && <Handle type="target" position={Position.Left} />}
      <div className="step-icon"><Icon size={16} /></div>
      <div className="step-text">
        <div className="step-title">{data.label || def.label}</div>
        <div className="step-sub">{id}</div>
      </div>
      {status !== 'idle' && <StatusBadge status={status} compact />}
      {outputs.map((o, i) => {
        const top = `${((i + 1) * 100) / (outputs.length + 1)}%`;
        return o === null ? (
          <Handle key="out" type="source" position={Position.Right} />
        ) : (
          <span key={o}>
            <Handle id={o} type="source" position={Position.Right} style={{ top }} />
            <span className="out-label" style={{ top }}>{o}</span>
          </span>
        );
      })}
    </div>
  );
}

export default memo(StepNode);
