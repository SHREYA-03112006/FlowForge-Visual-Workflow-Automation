import { useCallback, useEffect, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import { ArrowLeft, Play, Save } from 'lucide-react';
import WorkflowCanvas from '../components/canvas/WorkflowCanvas.jsx';
import NodePalette from '../components/sidebar/NodePalette.jsx';
import ConfigPanel from '../components/panels/ConfigPanel.jsx';
import RunPanel from '../components/panels/RunPanel.jsx';
import { useStore } from '../store/useWorkflowStore';
import { api } from '../services/api';
import { streamExecution } from '../services/ws';
import { toPayload } from '../utils/serialize';
import { validateWorkflow } from '../utils/validate';

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const closeStream = useRef(null);

  const workflowId = useStore((s) => s.workflowId);
  const name = useStore((s) => s.name);
  const nodes = useStore((s) => s.nodes);
  const edges = useStore((s) => s.edges);
  const dirty = useStore((s) => s.dirty);
  const runStatus = useStore((s) => s.run.status);
  const panelTab = useStore((s) => s.panelTab);
  const { setName, setPanelTab, load, reset, markSaved, notify, startRun, applyEvent, applySnapshot } =
    useStore.getState();

  // Load the workflow from the URL. After the first save the URL gains an id,
  // but the store already holds that workflow, so we skip the reload.
  useEffect(() => {
    if (!id) { reset(); return; }
    if (String(useStore.getState().workflowId) === id) return;
    api.getWorkflow(id).then(load).catch((e) => notify(e.message, 'error'));
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => closeStream.current?.(), []);

  const save = useCallback(async () => {
    const { name: n, nodes: ns, edges: es, workflowId: wid } = useStore.getState();
    const payload = toPayload({ name: n, nodes: ns, edges: es });
    if (wid) {
      await api.updateWorkflow(wid, payload);
      markSaved(wid);
      return wid;
    }
    const wf = await api.createWorkflow(payload);
    markSaved(wf.id);
    navigate(`/editor/${wf.id}`, { replace: true });
    return wf.id;
  }, [markSaved, navigate]);

  const onSave = useCallback(async () => {
    try { await save(); notify('Workflow saved', 'success'); } catch (e) { notify(e.message, 'error'); }
  }, [save, notify]);

  const onRun = async () => {
    const { errors, warnings } = validateWorkflow(nodes, edges);
    if (errors.length) { notify(errors[0], 'error'); return; }
    if (warnings.length) notify(warnings[0], 'warn');

    let input = {};
    const manual = nodes.find((n) => n.data.kind === 'manual');
    try { input = manual?.data.config.input ? JSON.parse(manual.data.config.input) : {}; } catch {
      notify('The sample input on the manual trigger is not valid JSON.', 'error');
      return;
    }
    try {
      const wid = await save(); // always run what's on screen
      const { execution_id } = await api.runWorkflow(wid, input);
      startRun(execution_id);
      closeStream.current?.();
      closeStream.current = streamExecution(execution_id, { onEvent: applyEvent, onSnapshot: applySnapshot });
    } catch (e) { notify(e.message, 'error'); }
  };

  // Ctrl/Cmd+S saves; warn before leaving with unsaved changes.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); onSave(); }
    };
    const onLeave = (e) => { if (useStore.getState().dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('keydown', onKey);
    window.addEventListener('beforeunload', onLeave);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('beforeunload', onLeave); };
  }, [onSave]);

  const running = runStatus === 'running';

  return (
    <div className="editor">
      <header className="editor-bar">
        <Link to="/" className="icon-link" aria-label="Back to workflows"><ArrowLeft size={18} /></Link>
        <input className="name-input" value={name} aria-label="Workflow name" onChange={(e) => setName(e.target.value)} />
        <span className="save-state">{dirty ? 'Unsaved changes' : workflowId ? 'Saved' : 'Not saved yet'}</span>
        <div className="spacer" />
        <button className="btn" onClick={onSave}><Save size={15} /> Save workflow</button>
        <button className="btn btn-primary" onClick={onRun} disabled={running}>
          <Play size={15} /> {running ? 'Running…' : 'Run workflow'}
        </button>
      </header>
      <NodePalette />
      <ReactFlowProvider>
        <WorkflowCanvas />
      </ReactFlowProvider>
      <aside className="side-panel">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={panelTab === 'configure'} onClick={() => setPanelTab('configure')}>Configure</button>
          <button role="tab" aria-selected={panelTab === 'run'} onClick={() => setPanelTab('run')}>Run</button>
        </div>
        {panelTab === 'configure' ? <ConfigPanel /> : <RunPanel />}
      </aside>
    </div>
  );
}
