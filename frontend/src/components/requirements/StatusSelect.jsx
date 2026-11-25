import { useState } from 'react';
import { useMeta } from '../../context/MetaContext';
import { REASON_REQUIRED } from '../../lib/requirements';
import { CancelReasonModal, MapResumesModal } from './StatusModals';

// Demand status dropdown. Non-Active / On Hold ask for a reason and Filled asks for resume(s) in a popup;
// the choice only reaches onChange once that popup is confirmed, so a status is never saved half-filled.
//   value      the status currently shown
//   reason     the saved status reason (pre-fills the popup)
//   resumes    the saved resumes, [{ id, display_id, candidate_name }] (pre-selects them)
//   matches    this demand's ranked matches [{ candidate, match_score }]; when given, Filled offers only those
//   onChange   (status, extras, resumes) => Promise<string | null>; extras is { cancellation_reason } or { candidate_ids };
//              resolve to an error message to keep the popup open and show it
export default function StatusSelect({ id, value, reason = '', resumes = [], matches, onChange, className = 'input-field', ariaLabel }) {
  const { jd_statuses: statuses, resume_linked_jd_statuses: linked, reason_required_jd_statuses: rawReasonRequired } = useMeta();
  const reasonRequired = rawReasonRequired?.length ? rawReasonRequired : REASON_REQUIRED;
  const [asking, setAsking] = useState(null);  // the status whose popup is open

  const pick = (status) => {
    if (status === value) return;
    if (reasonRequired.includes(status) || linked.includes(status)) setAsking(status);
    else onChange(status, {}, []);
  };

  const askingReason = asking && reasonRequired.includes(asking);

  return (
    <>
      <select id={id} className={className} value={value} onChange={(e) => pick(e.target.value)} aria-label={ariaLabel}>
        {statuses.map((st) => <option key={st} value={st}>{st}</option>)}
        {!statuses.includes(value) && <option value={value}>{value}</option>}
      </select>
      {askingReason && (
        <CancelReasonModal status={asking} initial={value === asking ? reason : ''} onClose={() => setAsking(null)}
          onConfirm={(text) => onChange(asking, { cancellation_reason: text }, [])} />
      )}
      {asking && !askingReason && (
        <MapResumesModal status={asking} initial={resumes} matches={matches} onClose={() => setAsking(null)}
          onConfirm={(ids, picked) => onChange(asking, { candidate_ids: ids }, picked)} />
      )}
    </>
  );
}
