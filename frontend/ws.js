// Live run updates. Connects to /ws/executions/:id and falls back to polling
// GET /api/executions/:id if the socket can't connect or drops mid-run.
//
// Events the backend should send (JSON, one per message):
//   {type: "node_status", node_id, status, output?, error?, attempts?}
//   {type: "log", node_id, level, message, timestamp}
//   {type: "execution_done", status}
import { api, isFinal, normalizeStatus } from './api';

function wsUrl(path) {
  const base = import.meta.env.VITE_API_URL;
  if (base) return base.replace(/^http/, 'ws') + path;
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`;
}

export function streamExecution(executionId, { onEvent, onSnapshot, onClose }) {
  let done = false;
  let ws = null;
  let pollTimer = null;
  let polling = false;

  const finish = () => {
    if (done) return;
    done = true;
    clearTimeout(pollTimer);
    if (ws && ws.readyState <= 1) ws.close();
    onClose?.();
  };

  const poll = async () => {
    if (done) return;
    polling = true;
    try {
      const ex = await api.getExecution(executionId);
      onSnapshot(ex);
      if (isFinal(ex.status)) return finish();
    } catch { /* keep polling */ }
    pollTimer = setTimeout(poll, 1000);
  };

  // Catch anything that happened before the socket connected.
  api.getExecution(executionId).then((ex) => {
    if (done) return;
    onSnapshot(ex);
    if (isFinal(ex.status)) finish();
  }).catch(() => {});

  try {
    ws = new WebSocket(wsUrl(`/ws/executions/${executionId}`));
    ws.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data);
        if (ev.status) ev.status = normalizeStatus(ev.status);
        onEvent(ev);
        if (ev.type === 'execution_done') finish();
      } catch { /* ignore malformed frames */ }
    };
    const fallback = () => { if (!done && !polling) poll(); };
    ws.onerror = fallback;
    ws.onclose = fallback;
  } catch {
    poll();
  }
  return finish;
}
