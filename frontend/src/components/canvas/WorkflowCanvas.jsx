import { useCallback, useMemo } from 'react';
import { Background, Controls, MarkerType, MiniMap, ReactFlow, useReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import StepNode from './StepNode.jsx';
import { CATEGORIES, getDef } from '../../nodeTypes';
import { useStore } from '../../store/useWorkflowStore';
import { COLORS } from '../../utils/colors';

const nodeTypes = { step: StepNode };

export default function WorkflowCanvas() {
  const nodes = useStore((s) => s.nodes);
  const edges = useStore((s) => s.edges);
  const nodeStatus = useStore((s) => s.run.nodeStatus);
  const onNodesChange = useStore((s) => s.onNodesChange);
  const onEdgesChange = useStore((s) => s.onEdgesChange);
  const onConnect = useStore((s) => s.onConnect);
  const addNode = useStore((s) => s.addNode);
  const select = useStore((s) => s.select);
  const { screenToFlowPosition } = useReactFlow();

  // Edges show what happened: green = data flowed, dashed = branch not taken.
  const styledEdges = useMemo(() => edges.map((e) => {
    const src = nodeStatus[e.source]?.status;
    const tgt = nodeStatus[e.target]?.status;
    let stroke = COLORS.line;
    let animated = false;
    let strokeDasharray;
    if (tgt === 'skipped') strokeDasharray = '5 5';
    else if (src === 'success' && ['success', 'failed', 'retrying'].includes(tgt)) stroke = COLORS.ok;
    if (tgt === 'running' || tgt === 'retrying') { stroke = COLORS.accent; animated = true; }
    return {
      ...e, animated,
      style: { stroke, strokeWidth: 2, strokeDasharray, opacity: tgt === 'skipped' ? 0.55 : 1 },
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
    };
  }), [edges, nodeStatus]);

  const onDrop = useCallback((ev) => {
    ev.preventDefault();
    const kind = ev.dataTransfer.getData('application/x-node-kind');
    if (!kind) return;
    addNode(kind, screenToFlowPosition({ x: ev.clientX, y: ev.clientY }));
  }, [addNode, screenToFlowPosition]);

  const onDragOver = useCallback((ev) => {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = 'move';
  }, []);

  return (
    <div className="canvas">
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, node) => select(node.id)}
        onPaneClick={() => select(null)}
        onDrop={onDrop}
        onDragOver={onDragOver}
        deleteKeyCode={['Backspace', 'Delete']}
        defaultEdgeOptions={{ type: 'smoothstep' }}
        fitView
        fitViewOptions={{ maxZoom: 1 }}
      >
        <Background gap={22} size={1.4} color="#C5CDE0" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={(n) => CATEGORIES[getDef(n.data.kind)?.category]?.color || '#999'} />
      </ReactFlow>
      {nodes.length === 0 && (
        <div className="canvas-empty">
          <strong>Start with a trigger</strong>
          <span>Drag one from the left onto the canvas, then connect steps to it.</span>
        </div>
      )}
    </div>
  );
}
