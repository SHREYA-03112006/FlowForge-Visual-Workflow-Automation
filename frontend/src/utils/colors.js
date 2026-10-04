// Hex values for places where CSS variables don't work (SVG marker fills).
export const COLORS = { ok: '#1E9E5A', accent: '#3B4BDB', line: '#B8C0D6', warn: '#D9822B' };

export const STATUS_LABEL = {
  idle: 'Not run', pending: 'Waiting', running: 'Running', retrying: 'Retrying',
  success: 'Done', failed: 'Failed', skipped: 'Skipped',
};

export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString() : '');
export const fmtClock = (iso) => (iso ? new Date(iso).toLocaleTimeString() : '');
export const fmtDuration = (a, b) => {
  if (!a || !b) return '';
  const s = (new Date(b) - new Date(a)) / 1000;
  return s < 1 ? `${Math.round(s * 1000)} ms` : `${s.toFixed(1)} s`;
};
