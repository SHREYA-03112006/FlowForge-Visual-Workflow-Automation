import { STATUS_LABEL } from '../../utils/colors';

export default function StatusBadge({ status = 'idle', compact = false }) {
  return (
    <span className={`badge badge-${status}`} title={STATUS_LABEL[status]}>
      <i className="dot" />
      {!compact && STATUS_LABEL[status]}
    </span>
  );
}
