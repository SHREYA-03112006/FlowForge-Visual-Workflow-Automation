import { create } from 'zustand';
import { addEdge, applyEdgeChanges, applyNodeChanges } from '@xyflow/react';
import { defaultConfig, getDef, getOutputs } from '../nodeTypes';
import { toFlowEdge, toFlowNode } from '../utils/serialize';

const emptyRun = () => ({ executionId: null, status: 'idle', nodeStatus: {}, logs: [] });

const nextId = (kind, nodes) => {
  let n = 1;
  while (nodes.some((x) => x.id === `${kind}_${n}`)) n += 1;
  return `${kind}_${n}`;
};

export const useStore = create((set, get) => ({
  workflowId: null,
  name: 'Untitled workflow',
  nodes: [],
  edges: [],
  selectedId: null,
  dirty: false,
  run: emptyRun(),
  panelTab: 'configure',
  toast: null,

  notify: (text, type = 'info') => set({ toast: { id: Date.now(), text, type } }),
  clearToast: () => set({ toast: null }),
  setPanelTab: (panelTab) => set({ panelTab }),

  reset: () => set({
    workflowId: null, name: 'Untitled workflow', nodes: [], edges: [],
    selectedId: null, dirty: false, run: emptyRun(), panelTab: 'configure',
  }),
  load: (wf) => set({
    workflowId: wf.id, name: wf.name, nodes: (wf.nodes || []).map(toFlowNode),
    edges: (wf.edges || []).map(toFlowEdge), selectedId: null, dirty: false,
    run: emptyRun(), panelTab: 'configure',
  }),
  markSaved: (id) => set({ workflowId: id, dirty: false }),
  setName: (name) => set({ name, dirty: true }),
  select: (selectedId) => set({ selectedId, ...(selectedId ? { panelTab: 'configure' } : {}) }),

  onNodesChange: (changes) => set((s) => {
    const removed = changes.filter((c) => c.type === 'remove').map((c) => c.id);
    return {
      nodes: applyNodeChanges(changes, s.nodes),
      dirty: s.dirty || changes.some((c) => c.type === 'remove' || c.type === 'position' && c.dragging === false),
      selectedId: removed.includes(s.selectedId) ? null : s.selectedId,
    };
  }),
  onEdgesChange: (changes) => set((s) => ({
    edges: applyEdgeChanges(changes, s.edges),
    dirty: s.dirty || changes.some((c) => c.type === 'remove'),
  })),
  onConnect: (conn) => set((s) => {
    if (conn.source === conn.target) return {};
    const id = `e_${conn.source}_${conn.sourceHandle || 'out'}_${conn.target}`;
    return { edges: addEdge({ ...conn, id }, s.edges), dirty: true };
  }),

  addNode: (kind, position) => set((s) => {
    const id = nextId(kind, s.nodes);
    const node = { id, type: 'step', position, data: { kind, label: '', config: defaultConfig(kind) } };
    return { nodes: [...s.nodes, node], selectedId: id, dirty: true, panelTab: 'configure' };
  }),
  updateConfig: (id, patch) => set((s) => {
    const nodes = s.nodes.map((n) => (n.id === id
      ? { ...n, data: { ...n.data, config: { ...n.data.config, ...patch } } } : n));
    // Drop connections from outputs that no longer exist (e.g. a removed switch case).
    const node = nodes.find((n) => n.id === id);
    const valid = getOutputs(node.data.kind, node.data.config).filter(Boolean);
    const edges = s.edges.filter((e) => e.source !== id || !e.sourceHandle || valid.includes(e.sourceHandle));
    return { nodes, edges, dirty: true };
  }),
  updateLabel: (id, label) => set((s) => ({
    nodes: s.nodes.map((n) => (n.id === id ? { ...n, data: { ...n.data, label } } : n)),
    dirty: true,
  })),
  deleteNode: (id) => set((s) => ({
    nodes: s.nodes.filter((n) => n.id !== id),
    edges: s.edges.filter((e) => e.source !== id && e.target !== id),
    selectedId: s.selectedId === id ? null : s.selectedId,
    dirty: true,
  })),

  // ----- live run state -----
  startRun: (executionId) => set((s) => ({
    run: {
      executionId, status: 'running', logs: [],
      nodeStatus: Object.fromEntries(s.nodes.map((n) => [n.id, { status: 'pending' }])),
    },
    panelTab: 'run',
  })),
  applyEvent: (ev) => set((s) => {
    const run = { ...s.run };
    if (ev.type === 'node_status') {
      run.nodeStatus = {
        ...run.nodeStatus,
        [ev.node_id]: { ...run.nodeStatus[ev.node_id], status: ev.status, output: ev.output ?? run.nodeStatus[ev.node_id]?.output, error: ev.error, attempts: ev.attempts },
      };
    } else if (ev.type === 'log') {
      run.logs = [...run.logs, ev];
    } else if (ev.type === 'execution_done') {
      run.status = ev.status;
    }
    return { run };
  }),
  applySnapshot: (ex) => set((s) => ({
    run: {
      executionId: ex.id ?? s.run.executionId, status: ex.status,
      nodeStatus: { ...s.run.nodeStatus, ...ex.nodeStatus },
      logs: ex.logs.length >= s.run.logs.length ? ex.logs : s.run.logs,
    },
  })),
  clearRun: () => set({ run: emptyRun() }),
}));

export { getDef };
