import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Download, Loader2, Pencil, Plus, Trash2 } from 'lucide-react';
import { trackerApi } from '../../lib/api';
import { errorText } from '../../lib/errors';
import { useMeta } from '../../context/MetaContext';
import Modal from '../ui/Modal';
import Notice from '../ui/Notice';
import RowEditor from './RowEditor';
import '../requirements/tracker.css';
import './tracker-sheet.css';

const ALL = { value: '', label: 'All' };

function exportCsv(name, columns, rows) {
  const quote = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [columns.map((c) => quote(c.label)).join(',')];
  rows.forEach((r) => lines.push(columns.map((c) => quote(r.data[c.key])).join(',')));
  const url = URL.createObjectURL(new Blob([`﻿${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' }));
  Object.assign(document.createElement('a'), { href: url, download: `${name}.csv` }).click();
  URL.revokeObjectURL(url);
}

function StageTable({ stage, columns, statuses, rows, stages, editing, saving, defaultAvailability, onAdd, onEdit, onSave, onCancel, onDelete, onMove }) {
  const [open, setOpen] = useState(true);
  const bodyId = `stage-${stage.key}`;
  return (
    <section className="stage" aria-labelledby={`${bodyId}-title`}>
      <header className="stage-head">
        <button type="button" className="stage-toggle" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
          <h2 id={`${bodyId}-title`}>{stage.label}</h2>
          <span className="stage-count">({stage.count})</span>
        </button>
        <button type="button" className="btn btn-secondary btn-compact" onClick={() => onAdd(stage.key)}><Plus size={14} /> Add row</button>
      </header>
      {open && (
        <div id={bodyId} className="tracker-scroll">
          <table className="tracker-table">
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">Actions</span></th>
                {columns.map((c) => <th key={c.key} scope="col">{c.label}</th>)}
                <th scope="col">Availability</th>
              </tr>
            </thead>
            <tbody>
              {editing?.stage === stage.key && !editing.row && (
                <RowEditor columns={columns} statuses={statuses} busy={saving} onSave={onSave} onCancel={onCancel} />
              )}
              {rows.length === 0 && editing?.stage !== stage.key && (
                <tr>
                  <td className="empty-cell" colSpan={columns.length + 2}>
                    <span className="empty-note">No rows in {stage.label} yet. Use Add row to create one.</span>
                  </td>
                </tr>
              )}
              {rows.map((row) => (editing?.row?.id === row.id ? (
                <RowEditor key={row.id} columns={columns} statuses={statuses} row={row} busy={saving} onSave={onSave} onCancel={onCancel} />
              ) : (
                <tr key={row.id}>
                  <td className="row-actions">
                    <button type="button" className="icon-btn" onClick={() => onEdit(row)} aria-label={`Edit ${row.data.candidate_name || 'row'}`}><Pencil size={15} /></button>
                    <button type="button" className="icon-btn" onClick={() => onDelete(row)} aria-label={`Delete ${row.data.candidate_name || 'row'}`}><Trash2 size={15} /></button>
                    {stages.length > 1 && (
                      <select className="input-field move-select" value={row.stage} aria-label="Move to table" onChange={(e) => onMove(row, e.target.value)}>
                        {stages.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                      </select>
                    )}
                  </td>
                  {columns.map((c) => (
                    <td key={c.key} className={c.kind === 'long' ? 'cell-long' : undefined}>
                      {c.kind === 'link' && row.data[c.key]
                        ? <a href={row.data[c.key]} target="_blank" rel="noopener noreferrer" className="tracker-link">Profile</a>
                        : row.data[c.key] || ''}
                    </td>
                  ))}
                  <td>{row.availability
                    ? <span className={`badge ${row.availability === defaultAvailability ? 'badge-success' : 'badge-neutral'}`}>{row.availability}</span>
                    : <span className="text-subtle">—</span>}</td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// One editable tracker: its stage tables (top to bottom), availability filter, add / edit / move / delete.
export default function TrackerSheet({ kind, exportName }) {
  const { availability_statuses: availabilityStatuses, default_availability: defaultAvailability } = useMeta();
  const availabilityOptions = [ALL, ...availabilityStatuses.map((value) => ({ value, label: value }))];
  const [availability, setAvailability] = useState('');
  const [data, setData] = useState({ columns: [], stages: [], statuses: [], rows: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null);   // { stage } adding into that table, { row } editing that row
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await trackerApi.sheet(kind, availability ? { availability } : {});
      setData(res.data);
      setError('');
    } catch (err) {
      setError(errorText(err, 'Could not load the tracker. Please try again.'));
    } finally {
      setLoading(false);
    }
  }, [kind, availability]);

  useEffect(() => { setLoading(true); load(); }, [load]);

  const move = async (row, stage) => {
    try { await trackerApi.update(row.id, { stage }); await load(); } catch (err) { setError(errorText(err, 'Could not move the row.')); }
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      await trackerApi.remove(removing.id);
      setRemoving(null);
      await load();
    } catch (err) {
      setError(errorText(err, 'Could not delete the row.'));
      setRemoving(null);
    } finally {
      setBusy(false);
    }
  };

  const save = async (values, candidateId) => {
    setSaving(true);
    try {
      if (editing.row) {
        // Cleared fields go as '' so the server drops them.
        await trackerApi.update(editing.row.id, { data: Object.fromEntries(data.columns.map((c) => [c.key, values[c.key] || ''])) });
      } else {
        await trackerApi.create(kind, {
          stage: editing.stage, candidate_id: candidateId,
          data: Object.fromEntries(Object.entries(values).filter(([, v]) => v)),
        });
      }
      setEditing(null);
      setError('');
      await load();
    } catch (err) {
      setError(errorText(err, 'Could not save this row.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack stack-loose">
      <div className="cluster cluster-between">
        <div className="segmented" role="group" aria-label="Candidate availability">
          {availabilityOptions.map((a) => (
            <button key={a.label} type="button" aria-pressed={availability === a.value} className="segmented-btn" onClick={() => setAvailability(a.value)}>{a.label}</button>
          ))}
        </div>
        <button type="button" className="btn btn-secondary btn-compact" disabled={!data.rows.length} onClick={() => exportCsv(exportName, data.columns, data.rows)}>
          <Download size={14} /> Export CSV
        </button>
      </div>
      {error && <Notice type="error" onDismiss={() => setError('')}>{error}</Notice>}
      {loading ? <p className="stage-empty"><Loader2 size={18} className="animate-spin" /> Loading tracker…</p>
        : data.stages.map((stage) => (
          <StageTable key={stage.key} stage={stage} columns={data.columns} statuses={data.statuses} stages={data.stages}
            rows={data.rows.filter((r) => r.stage === stage.key)} editing={editing} saving={saving} defaultAvailability={defaultAvailability}
            onAdd={(key) => { setError(''); setEditing({ stage: key }); }} onEdit={(row) => { setError(''); setEditing({ row }); }}
            onSave={save} onCancel={() => setEditing(null)} onDelete={setRemoving} onMove={move} />
        ))}
      {removing && (
        <Modal title="Delete row" size="sm" busy={busy} onClose={() => setRemoving(null)}
          footer={(
            <>
              <button type="button" className="btn btn-secondary" onClick={() => setRemoving(null)} disabled={busy}>Cancel</button>
              <button type="button" className="btn btn-primary" onClick={confirmDelete} disabled={busy}>{busy ? 'Deleting…' : 'Delete'}</button>
            </>
          )}>
          <p>Delete the row for <strong>{removing.data.candidate_name || 'this candidate'}</strong>? This cannot be undone.</p>
        </Modal>
      )}
    </div>
  );
}
