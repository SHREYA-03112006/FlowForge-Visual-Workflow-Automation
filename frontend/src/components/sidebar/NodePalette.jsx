import { CATEGORIES, NODE_DEFS } from '../../nodeTypes';
import { useStore } from '../../store/useWorkflowStore';

export default function NodePalette() {
  const addNode = useStore((s) => s.addNode);
  const count = useStore((s) => s.nodes.length);

  return (
    <aside className="palette" aria-label="Steps">
      <p className="palette-hint">Drag a step onto the canvas, or click to add it.</p>
      {Object.entries(CATEGORIES).map(([key, cat]) => (
        <section key={key} style={{ '--cat': cat.color }}>
          <h3>{cat.label}</h3>
          {NODE_DEFS.filter((d) => d.category === key).map((d) => {
            const Icon = d.icon;
            return (
              <button
                key={d.kind}
                className="palette-item"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/x-node-kind', d.kind);
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onClick={() => addNode(d.kind, { x: 120 + (count % 6) * 36, y: 80 + (count % 8) * 60 })}
              >
                <span className="palette-icon"><Icon size={15} /></span>
                <span className="palette-text">
                  <strong>{d.label}</strong>
                  <small>{d.description}</small>
                </span>
              </button>
            );
          })}
        </section>
      ))}
    </aside>
  );
}
