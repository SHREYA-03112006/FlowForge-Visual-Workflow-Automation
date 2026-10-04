const BASE = import.meta.env.VITE_API_URL || '';

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new Error("Can't reach the API. Check that the backend is running on port 8000.");
  }
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string'
        ? body.detail
        : JSON.stringify(body.detail ?? body);
    } catch {}
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

const STATUS_ALIASES = {
  completed: 'success',
  succeeded: 'success',
  error: 'failed',
  queued: 'pending',
};

export const normalizeStatus = (s) => STATUS_ALIASES[s] || s || 'pending';
export const isFinal = (s) => ['success', 'failed', 'cancelled'].includes(normalizeStatus(s));

export function normalizeExecution(ex) {
  const logs = Array.isArray(ex.logs) ? ex.logs : [];
  const nodeStatus = {};

  for (const r of logs) {
    nodeStatus[r.node_id] = {
      status: normalizeStatus(r.status),
      output: r.output_data,
      error: r.error,
      attempts: r.attempt,
      message: r.message,
    };
  }

  return {
    ...ex,
    status: normalizeStatus(ex.status),
    nodeStatus,
    logs,
  };
}

export const api = {
  listWorkflows: () => request('/api/workflows'),
  getWorkflow: (id) => request(`/api/workflows/${id}`),
  createWorkflow: (payload) =>
    request('/api/workflows', { method: 'POST', body: JSON.stringify(payload) }),
  updateWorkflow: (id, payload) =>
    request(`/api/workflows/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteWorkflow: (id) =>
    request(`/api/workflows/${id}`, { method: 'DELETE' }),
  runWorkflow: (id, input = {}) =>
    request(`/api/workflows/${id}/run`, {
      method: 'POST',
      body: JSON.stringify({ input }),
    }).then((result) => ({
      ...result,
      execution_id: result.execution_id ?? result.id,
    })),
  listExecutions: (workflowId) =>
    request(`/api/executions${workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : ''}`),
  getExecution: async (id) =>
    normalizeExecution(await request(`/api/executions/${id}`)),
};
