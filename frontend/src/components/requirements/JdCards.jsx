import { useState } from 'react';
import { Check, Copy, Pencil, Search, Trash2, X, MapPin, Users, Clock, ArrowRight, Building2 } from 'lucide-react';
import { filterDemands, formatDate, formatExperience, formatLocations, formatPositions, showRole } from '../../lib/requirements';
import JdStatusBadge from './JdStatusBadge';
import StatusNote from './StatusNote';
import './requirements.css';

const Fact = ({ label, children, wide }) => (
  <div className={wide ? 'info-card-fact-wide' : undefined}>
    <dt>{label}</dt>
    <dd>{children}</dd>
  </div>
);

// The free-text "where the demand stands" note on a card: pencil swaps it for a text field, check saves,
// cross cancels. Saves through onUpdateField(jd, { current_status }) and only leaves edit mode on success.
// onEditingChange tells the card wrap so it can hide the copy/delete actions while editing.
function CardStatus({ jd, onUpdateField, onEditingChange }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const setMode = (next) => { setEditing(next); onEditingChange?.(next ? jd.id : null); };
  const save = async () => {
    setBusy(true);
    const ok = await onUpdateField(jd, { current_status: value.trim() || null });
    setBusy(false);
    if (ok) setMode(false);
  };
  if (!editing) {
    return (
      <span className="cluster cluster-tight">
        <span className="jd-card-status-text">{jd.current_status || '—'}</span>
        <button
          type="button"
          className="icon-btn"
          onClick={(e) => { e.stopPropagation(); setValue(jd.current_status || ''); setMode(true); }}
          aria-label={`Edit current status of ${jd.title}`}
          title="Edit current status"
        >
          <Pencil size={12} />
        </button>
      </span>
    );
  }
  return (
    <span className="cluster cluster-tight" onClick={(e) => e.stopPropagation()}>
      <input
        className="input-field jd-card-status-input"
        value={value}
        maxLength={500}
        autoFocus
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setMode(false); }}
        aria-label={`Current status of ${jd.title}`}
      />
      <button type="button" className="icon-btn" disabled={busy} onClick={save} aria-label="Save current status"><Check size={14} /></button>
      <button type="button" className="icon-btn" disabled={busy} onClick={() => setMode(false)} aria-label="Cancel"><X size={14} /></button>
    </span>
  );
}

// One card per demand of the chosen practice (or client, with `scope="client"`), already in status order.
export default function JdCards({ jds, loading, scope = 'practice', practiceName, onOpen, onDelete, onDuplicate, onCreate, onUpdateField }) {
  const [query, setQuery] = useState('');
  const [statusEditingId, setStatusEditingId] = useState(null);
  const shown = filterDemands(jds, query);

  if (jds.length === 0) {
    return (
      <p className="req-empty">
        {loading ? 'Loading demands…' : `No demands in this ${scope} yet.`}
        {!loading && <button type="button" className="link-btn" onClick={onCreate}>Create one</button>}
      </p>
    );
  }

  return (
    <div className="stack">
      <div className="folder-search">
        <Search size={16} aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search this ${scope} by demand ID or title`}
          aria-label={`Search demands in this ${scope} by ID or title`}
        />
        {query && <span className="slug" role="status">{shown.length} of {jds.length}</span>}
      </div>
      {shown.length === 0 ? (
        <p className="req-empty">No demands match “{query.trim()}”.</p>
      ) : (
        <ul className="card-grid card-grid-wide" aria-label="Demands">
          {shown.map((jd) => (
            <li
              key={jd.id}
              className={`info-card-wrap${['Non-Active', 'On Hold', 'Filled', 'Cancelled', 'Mapped', 'Fulfilled'].includes(jd.status) ? ' has-note' : ''}${statusEditingId === jd.id ? ' is-editing' : ''}`}
            >
              <div
                className="card card-hover info-card"
                role="button"
                tabIndex={0}
                onClick={() => onOpen(jd)}
                onKeyDown={(e) => {
                  if (e.target !== e.currentTarget) return;
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(jd); }
                }}
              >
                {/* Header: ID + Client Tag + Status */}
                <div className="req-card-head">
                  <div className="req-card-tags">
                    <span className="req-id-badge">{jd.display_id || 'DM-????'}</span>
                    {jd.client_name && (
                      <span className="req-client-chip">
                        <Building2 size={11} /> {jd.client_name}
                      </span>
                    )}
                  </div>
                  <JdStatusBadge status={jd.status} />
                </div>

                {/* Title */}
                <span className="info-card-title">{jd.title}</span>

                {/* Structured Metadata */}
                <dl className="info-card-rows">
                  <div className="info-card-row">
                    <Fact label="Positions">
                      <span className="fact-inline">
                        <Users size={12} className="fact-icon-primary" /> {formatPositions(jd.no_of_positions)}
                      </span>
                    </Fact>
                    <Fact label="Experience">
                      <span className="fact-inline">
                        <Clock size={12} className="fact-icon-muted" /> {formatExperience(jd.experience_years, jd.relevant_experience_years)}
                      </span>
                    </Fact>
                  </div>

                  <div className="info-card-row">
                    <Fact label="Locations">
                      <span className="fact-inline">
                        <MapPin size={12} className="fact-icon-muted" /> {formatLocations(jd)}
                      </span>
                    </Fact>
                    {practiceName && <Fact label="Practice">{practiceName(jd.demand_id) || '—'}</Fact>}
                  </div>

                  {showRole(jd) && (
                    <div className="info-card-row">
                      <Fact label="Role">{jd.role}</Fact>
                    </div>
                  )}

                  <div className="info-card-row">
                    <Fact label="Demand Owner">{jd.demand_owner || '—'}</Fact>
                    <Fact label="Created On">{formatDate(jd.created_at)}</Fact>
                  </div>

                  <div className="info-card-row">
                    <Fact label="Current Status" wide>
                      <CardStatus jd={jd} onUpdateField={onUpdateField} onEditingChange={setStatusEditingId} />
                    </Fact>
                  </div>

                  {jd.requirement_received_date && (
                    <div className="info-card-row">
                      <Fact label="Requirement Received Date">{formatDate(jd.requirement_received_date)}</Fact>
                    </div>
                  )}

                  {(jd.start_date || jd.end_date) && (
                    <div className="info-card-row">
                      <Fact label="Project Start Date">{formatDate(jd.start_date)}</Fact>
                      <Fact label="Project End Date">{formatDate(jd.end_date)}</Fact>
                    </div>
                  )}
                </dl>

                {/* Footer link */}
                <div className="req-card-footer">
                  <span className="req-view-link">
                    View matches & details <ArrowRight size={13} />
                  </span>
                </div>
              </div>

              <span className="info-card-note"><StatusNote jd={jd} /></span>
              <button type="button" className="icon-btn info-card-copy" onClick={() => onDuplicate(jd)} aria-label={`Duplicate ${jd.title}`} title="Duplicate this demand">
                <Copy size={14} />
              </button>
              <button type="button" className="icon-btn info-card-remove" onClick={() => onDelete(jd)} aria-label={`Remove ${jd.title}`}>
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
