// REST client. Endpoint contract this UI expects from the FastAPI backend:
//   GET    /api/workflows                 -> [{id, name, updated_at}]
//   POST   /api/workflows                 -> {id, name, nodes, edges}
//   GET    /api/workflows/:id             -> {id, name, nodes, edges}
//   PUT    /api/workflows/:id             -> {id, name, nodes, edges}
//   DELETE /api/workflows/:id
//   POST   /api/workflows/:id/run         -> {execution_id}   body: {input: {...}}
//   GET    /api/executions?workflow_id=   -> [{id, workflow_id, workflow_name, status, started_at, finished_at}]
//   GET    /api/executions/:id            -> {id, status, node_runs, logs, ...}
// If your routes differ, change them here. Nothing else calls fetch.
const BASE = import.meta.env.VITE_API_URL || '';

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...options });
  } catch {
    throw new Error("Can't reach the API. Check that the backend is running on port 8000.");
  }
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* body wasn't JSON */ }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

const STATUS_ALIASES = { completed: 'success', succeeded: 'success', error: 'failed', queued: 'pending' };
export const normalizeStatus = (s) => STATUS_ALIASES[s] || s || 'pending';
export const isFinal = (s) => s === 'success' || s === 'failed';

// Accepts node_runs as an object keyed by node id or as an array.
export function normalizeExecution(ex) {
  const runs = Array.isArray(ex.node_runs)
    ? Object.fromEntries(ex.node_runs.map((r) => [r.node_id, r]))
    : ex.node_runs || {};
  const nodeStatus = {};
  Object.entries(runs).forEach(([id, r]) => {
    nodeStatus[id] = { status: normalizeStatus(r.status), output: r.output, error: r.error, attempts: r.attempts };
  });
  return { ...ex, status: normalizeStatus(ex.status), nodeStatus, logs: ex.logs || [] };
}

export const api = {
  listWorkflows: () => request('/api/workflows'),
  getWorkflow: (id) => request(`/api/workflows/${id}`),
  createWorkflow: (payload) => request('/api/workflows', { method: 'POST', body: JSON.stringify(payload) }),
  updateWorkflow: (id, payload) => request(`/api/workflows/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteWorkflow: (id) => request(`/api/workflows/${id}`, { method: 'DELETE' }),
  runWorkflow: (id, input = {}) => request(`/api/workflows/${id}/run`, { method: 'POST', body: JSON.stringify({ input }) }),
  listExecutions: (workflowId) =>
    request(`/api/executions${workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : ''}`),
  getExecution: async (id) => normalizeExecution(await request(`/api/executions/${id}`)),
};
