import { defaultConfig } from '../nodeTypes';

export const toFlowNode = (n) => {
  // Backend stores React Flow nodes as:
  // { id, type, position, data: { kind, label, config } }
  // Older payloads may contain flattened label/config fields, so support both.
  const data = n.data || {};
  const kind = data.kind || n.type;
  return {
    id: n.id,
    type: 'step',
    position: n.position || { x: 0, y: 0 },
    data: {
      kind,
      label: data.label ?? n.label ?? '',
      config: { ...defaultConfig(kind), ...(data.config || n.config || {}) },
    },
  };
};

export const toFlowEdge = (e) => ({
  id: e.id || `e_${e.source}_${e.sourceHandle || e.source_handle || 'out'}_${e.target}`,
  source: e.source,
  target: e.target,
  sourceHandle: e.sourceHandle ?? e.source_handle ?? null,
});

export const toPayload = ({ name, nodes, edges }) => ({
  name,
  graph: {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.data.kind,
      position: { x: Math.round(n.position?.x || 0), y: Math.round(n.position?.y || 0) },
      data: {
        kind: n.data.kind,
        label: n.data.label || '',
        config: n.data.config || {},
      },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? null,
    })),
  },
});
