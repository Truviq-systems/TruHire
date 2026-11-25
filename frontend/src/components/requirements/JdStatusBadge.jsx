const TONE = {
  Active: 'badge-primary',
  'Non-Active': 'badge-danger',
  'On Hold': 'badge-warning',
  Filled: 'badge-success',
  Open: 'badge-primary',
  Cancelled: 'badge-danger',
  Fulfilled: 'badge-success',
  Mapped: 'badge-warning',
  Map: 'badge-warning',
};

// JD status (Active, Non-Active, On Hold, Filled); distinct from a candidate's review status.
export default function JdStatusBadge({ status }) {
  return <span className={`badge ${TONE[status] || 'badge-neutral'}`}><span className="sr-only">Demand status: </span>{status === 'Map' ? 'Filled' : status || 'Active'}</span>;
}
