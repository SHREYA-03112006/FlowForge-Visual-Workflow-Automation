// Converts between React Flow's in-memory shape and the JSON the backend stores.
//   node: { id, type (kind), label, position:{x,y}, config:{...} }
//   edge: { id, source, target, source_handle }
import { defaultConfig } from '../nodeTypes';

export const toFlowNode = (n) => ({
  id: n.id,
  type: 'step',
  position: n.position || { x: 0, y: 0 },
  data: { kind: n.type, label: n.label || '', config: { ...defaultConfig(n.type), ...(n.config || {}) } },
});

export const toFlowEdge = (e) => ({
  id: e.id || `e_${e.source}_${e.source_handle || 'out'}_${e.target}`,
  source: e.source,
  target: e.target,
  sourceHandle: e.source_handle ?? null,
});

export const toPayload = ({ name, nodes, edges }) => ({
  name,
  nodes: nodes.map((n) => ({
    id: n.id,
    type: n.data.kind,
    label: n.data.label,
    position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    config: n.data.config,
  })),
  edges: edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    source_handle: e.sourceHandle ?? null,
  })),
});
