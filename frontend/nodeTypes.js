// One entry per node type. `kind` must match the handler key in the backend's
// node registry (backend/app/nodes/...). Fields drive the config panel.
import {
  Play, Webhook, Clock, Globe, Mail, FileText, Code, GitBranch, Split,
  Shuffle, Filter, Braces, Brain,
} from 'lucide-react';

export const CATEGORIES = {
  trigger: { label: 'Triggers', color: 'var(--c-trigger)' },
  action: { label: 'Actions', color: 'var(--c-action)' },
  logic: { label: 'Conditions', color: 'var(--c-logic)' },
  transform: { label: 'Data', color: 'var(--c-transform)' },
  ml: { label: 'Machine learning', color: 'var(--c-ml)' },
};

const OPERATORS = ['==', '!=', '>', '<', '>=', '<=', 'contains', 'exists'];
const field = (key, label, type = 'text', extra = {}) => ({ key, label, type, ...extra });

const switchCases = (cfg) =>
  (cfg.cases || '').split(',').map((s) => s.trim()).filter(Boolean);

export const NODE_DEFS = [
  {
    kind: 'manual', category: 'trigger', label: 'Manual run', icon: Play,
    description: 'Start the workflow with a button.',
    fields: [field('input', 'Sample input (JSON)', 'json', { placeholder: '{"text": "My invoice is wrong"}' })],
    defaults: { input: '{}' },
  },
  {
    kind: 'webhook', category: 'trigger', label: 'Webhook', icon: Webhook,
    description: 'Start when an HTTP request arrives.',
    fields: [
      field('path', 'Path', 'text', { required: true, placeholder: 'support-ticket', hint: 'Served at /api/webhooks/<path>' }),
      field('method', 'Method', 'select', { options: ['POST', 'GET'] }),
    ],
    defaults: { path: '', method: 'POST' },
  },
  {
    kind: 'schedule', category: 'trigger', label: 'Schedule', icon: Clock,
    description: 'Start on a cron schedule.',
    fields: [field('cron', 'Cron expression', 'text', { required: true, placeholder: '*/5 * * * *', hint: 'minute hour day month weekday' })],
    defaults: { cron: '*/5 * * * *' },
  },
  {
    kind: 'http_request', category: 'action', label: 'HTTP request', icon: Globe, retryable: true,
    description: 'Call a REST API.',
    fields: [
      field('method', 'Method', 'select', { options: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] }),
      field('url', 'URL', 'text', { required: true, placeholder: 'https://api.example.com/items' }),
      field('headers', 'Headers (JSON)', 'json', { placeholder: '{"Authorization": "Bearer ..."}' }),
      field('body', 'Body (JSON)', 'json'),
      field('timeout', 'Timeout (seconds)', 'number'),
    ],
    defaults: { method: 'GET', url: '', headers: '', body: '', timeout: 15, retries: 2, retry_delay: 2 },
  },
  {
    kind: 'send_email', category: 'action', label: 'Send email', icon: Mail, retryable: true,
    description: 'Email a person or team.',
    fields: [
      field('to', 'To', 'text', { required: true, placeholder: 'billing@example.com' }),
      field('subject', 'Subject', 'text', { required: true }),
      field('body', 'Message', 'textarea'),
    ],
    defaults: { to: '', subject: '', body: '', retries: 2, retry_delay: 2 },
  },
  {
    kind: 'write_file', category: 'action', label: 'Write file', icon: FileText, retryable: true,
    description: 'Save text to a file.',
    fields: [
      field('path', 'File path', 'text', { required: true, placeholder: 'output/result.txt' }),
      field('content', 'Content', 'textarea'),
      field('mode', 'If the file exists', 'select', { options: ['overwrite', 'append'] }),
    ],
    defaults: { path: '', content: '', mode: 'overwrite', retries: 0, retry_delay: 2 },
  },
  {
    kind: 'python_snippet', category: 'action', label: 'Run Python', icon: Code, retryable: true,
    description: 'Run a short, restricted script.',
    fields: [
      field('code', 'Code', 'code', { required: true, rows: 8, hint: 'Read upstream data from `inputs`. Assign your output to `result`.' }),
      field('timeout', 'Timeout (seconds)', 'number'),
    ],
    defaults: { code: 'result = {"ok": True}', timeout: 5, retries: 0, retry_delay: 2 },
  },
  {
    kind: 'condition', category: 'logic', label: 'If / else', icon: GitBranch,
    description: 'Follow one path or the other.',
    fields: [
      field('left', 'Value', 'text', { required: true, placeholder: '{{classify.output.label}}' }),
      field('operator', 'Operator', 'select', { options: OPERATORS }),
      field('right', 'Compare to', 'text', { placeholder: 'billing' }),
    ],
    defaults: { left: '', operator: '==', right: '' },
    outputs: () => ['true', 'false'],
  },
  {
    kind: 'switch', category: 'logic', label: 'Switch', icon: Split,
    description: 'Pick a path by matching a value.',
    fields: [
      field('value', 'Value', 'text', { required: true, placeholder: '{{classify.output.label}}' }),
      field('cases', 'Cases (comma separated)', 'text', { required: true, placeholder: 'billing, technical, account' }),
    ],
    defaults: { value: '', cases: 'a, b' },
    outputs: (cfg) => [...switchCases(cfg), 'default'],
  },
  {
    kind: 'map', category: 'transform', label: 'Map', icon: Shuffle,
    description: 'Reshape each item in a list.',
    fields: [
      field('source', 'List', 'text', { required: true, placeholder: '{{http_request_1.output.items}}' }),
      field('mapping', 'New shape (JSON)', 'json', { required: true, placeholder: '{"name": "{{item.title}}"}' }),
    ],
    defaults: { source: '', mapping: '' },
  },
  {
    kind: 'filter', category: 'transform', label: 'Filter', icon: Filter,
    description: 'Keep only matching items.',
    fields: [
      field('source', 'List', 'text', { required: true }),
      field('field', 'Item field', 'text', { required: true, placeholder: 'status' }),
      field('operator', 'Operator', 'select', { options: OPERATORS }),
      field('value', 'Compare to', 'text'),
    ],
    defaults: { source: '', field: '', operator: '==', value: '' },
  },
  {
    kind: 'json_extract', category: 'transform', label: 'Extract field', icon: Braces,
    description: 'Pull one value out of JSON.',
    fields: [
      field('source', 'JSON', 'text', { required: true, placeholder: '{{http_request_1.output}}' }),
      field('path', 'Path', 'text', { required: true, placeholder: 'user.email' }),
    ],
    defaults: { source: '', path: '' },
  },
  {
    kind: 'ml_classifier', category: 'ml', label: 'Classify text', icon: Brain, retryable: true,
    description: 'Label text: billing, technical, account or general.',
    fields: [
      field('text', 'Text', 'textarea', { required: true, placeholder: '{{webhook_1.output.body.text}}' }),
      field('threshold', 'Low-confidence below', 'number'),
    ],
    defaults: { text: '', threshold: 0.45, retries: 0, retry_delay: 1 },
    hint: 'Outputs label, confidence, scores and low_confidence.',
  },
];

export const DEFS = Object.fromEntries(NODE_DEFS.map((d) => [d.kind, d]));
export const getDef = (kind) => DEFS[kind];
export const defaultConfig = (kind) => ({ ...(DEFS[kind]?.defaults || {}) });
export const getOutputs = (kind, config = {}) => {
  const d = DEFS[kind];
  return d?.outputs ? d.outputs(config) : [null];
};
export const isTrigger = (kind) => DEFS[kind]?.category === 'trigger';
