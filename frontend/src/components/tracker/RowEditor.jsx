import { useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { candidatesApi } from '../../lib/api';

const INPUT_TYPE = { date: 'date', time: 'time', link: 'url' };

// Candidate-name cell of a new row: typing offers ingested candidates; picking one links the row so the
// server fills the rest from the candidate record and resume when the row is saved.
function NameCell({ value, linked, onChange, onPick, onUnlink }) {
  const [results, setResults] = useState([]);

  useEffect(() => {
    const needle = (value || '').trim();
    if (linked || needle.length < 2) { setResults([]); return undefined; }
    let live = true;
    const timer = window.setTimeout(() => {
      candidatesApi.list({ q: needle, limit: 6 })
        .then((res) => { if (live) setResults(res.data.candidates || []); })
        .catch(() => { if (live) setResults([]); });
    }, 250);
    return () => { live = false; window.clearTimeout(timer); };
  }, [value, linked]);

  return (
    <div className="name-cell">
      <input className="cell-input" value={value || ''} aria-label="Candidate Name" autoComplete="off"
        onChange={(e) => { if (linked) onUnlink(); onChange(e.target.value); }} />
      {linked && <span className="linked-hint">Linked: fills from resume on save</span>}
      {results.length > 0 && (
        <ul className="name-suggestions">
          {results.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => { onPick(c); setResults([]); }}>
                <strong>{c.candidate_name}</strong> <span className="slug">{c.display_id}</span>
                <span className="text-subtle">{c.current_company || c.email || ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// A table row made of inputs, one per column: adds a row (no `row`) or edits one in place.
// Enter saves, Escape cancels. The row sits directly under the column headers it fills.
export default function RowEditor({ columns, statuses, row, busy, onSave, onCancel }) {
  const adding = !row;
  const [values, setValues] = useState(row?.data || {});
  const [candidate, setCandidate] = useState(null);
  const set = (key, value) => setValues((v) => ({ ...v, [key]: value }));

  const save = () => onSave(values, candidate?.id || null);
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && e.target.tagName !== 'BUTTON') { e.preventDefault(); save(); }
    if (e.key === 'Escape') onCancel();
  };

  const cell = (c) => {
    const value = values[c.key] || '';
    if (c.key === 'candidate_name' && adding) {
      return (
        <NameCell value={value} linked={Boolean(candidate)} onChange={(v) => set(c.key, v)}
          onPick={(picked) => { setCandidate(picked); set(c.key, picked.candidate_name); }} onUnlink={() => setCandidate(null)} />
      );
    }
    if (c.key === 'client_interview_status') {
      return (
        <select className="cell-input" value={value} aria-label={c.label} onChange={(e) => set(c.key, e.target.value)}>
          <option value="">Select</option>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      );
    }
    return <input className={`cell-input cell-input-${c.kind}`} type={INPUT_TYPE[c.kind] || 'text'} value={value} aria-label={c.label}
      onChange={(e) => set(c.key, e.target.value)} />;
  };

  return (
    <tr className="row-editor" onKeyDown={onKeyDown}>
      <td className="row-actions">
        <button type="button" className="icon-btn" onClick={save} disabled={busy} aria-label={adding ? 'Save new row' : 'Save changes'}><Check size={16} /></button>
        <button type="button" className="icon-btn" onClick={onCancel} disabled={busy} aria-label="Cancel"><X size={16} /></button>
      </td>
      {columns.map((c) => <td key={c.key}>{cell(c)}</td>)}
      <td><span className="text-subtle">{candidate ? 'Linked' : '—'}</span></td>
    </tr>
  );
}
