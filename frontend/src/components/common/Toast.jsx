import { useEffect } from 'react';
import { useStore } from '../../store/useWorkflowStore';

export default function Toast() {
  const toast = useStore((s) => s.toast);
  const clear = useStore((s) => s.clearToast);
  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(clear, 5000);
    return () => clearTimeout(t);
  }, [toast, clear]);
  if (!toast) return null;
  return (
    <div className={`toast toast-${toast.type}`} role="status" onClick={clear}>
      {toast.text}
    </div>
  );
}
