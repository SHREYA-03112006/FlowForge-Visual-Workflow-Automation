// Checks a workflow before saving or running so mistakes show up here,
// not as a failed run.
import { getDef, isTrigger } from '../nodeTypes';

export function validateWorkflow(nodes, edges) {
  const errors = [];
  const warnings = [];
  if (!nodes.length) return { errors: ['Add a trigger to the canvas to get started.'], warnings };

  if (!nodes.some((n) => isTrigger(n.data.kind))) {
    errors.push('Add a trigger (manual run, webhook or schedule). Every workflow needs one.');
  }

  // Cycle check (Kahn's algorithm).
  const indeg = Object.fromEntries(nodes.map((n) => [n.id, 0]));
  edges.forEach((e) => { indeg[e.target] = (indeg[e.target] || 0) + 1; });
  const queue = nodes.filter((n) => !indeg[n.id]).map((n) => n.id);
  let seen = 0;
  while (queue.length) {
    const id = queue.pop();
    seen += 1;
    edges.filter((e) => e.source === id).forEach((e) => {
      indeg[e.target] -= 1;
      if (!indeg[e.target]) queue.push(e.target);
    });
  }
  if (seen < nodes.length) errors.push('The workflow loops back on itself. Remove the connection that closes the loop.');

  nodes.forEach((n) => {
    const def = getDef(n.data.kind);
    const name = n.data.label || def.label;
    def.fields.filter((f) => f.required).forEach((f) => {
      const v = n.data.config[f.key];
      if (v === undefined || v === null || String(v).trim() === '') {
        errors.push(`${name} (${n.id}): fill in "${f.label}".`);
      }
    });
    def.fields.filter((f) => f.type === 'json').forEach((f) => {
      const v = n.data.config[f.key];
      if (v && !String(v).includes('{{')) {
        try { JSON.parse(v); } catch { errors.push(`${name} (${n.id}): "${f.label}" is not valid JSON.`); }
      }
    });
    if (isTrigger(n.data.kind) && edges.some((e) => e.target === n.id)) {
      errors.push(`${name} (${n.id}): triggers can't have incoming connections.`);
    }
    if (!isTrigger(n.data.kind) && !edges.some((e) => e.target === n.id)) {
      warnings.push(`${name} (${n.id}) isn't connected upstream, so it won't run.`);
    }
  });
  return { errors, warnings };
}
