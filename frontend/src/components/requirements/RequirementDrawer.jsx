import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { X, ArrowRight, Mail, Briefcase, MapPin, Calendar, Users, Building2 } from 'lucide-react';
import JdStatusBadge from './JdStatusBadge';
import { formatDate, formatExperience, formatLocations, formatPositions } from '../../lib/requirements';
import { fromState } from '../../lib/navigation';
import './requirements.css';

import { candidatePath, searchPath } from '../../config/pages';
export default function RequirementDrawer({ jd, matches = [], loading = false, onClose, onEmail, onOpenFull }) {
  const location = useLocation();
  const [activeTab, setActiveTab] = useState('matches');

  if (!jd) return null;

  return (
    <aside className="req-slide-drawer" aria-label={`Details for ${jd.title}`}>
      {/* Drawer Header */}
      <div className="req-drawer-header">
        <div>
          <h2 className="req-drawer-title">{jd.display_id} - {jd.title}</h2>
          <div className="req-drawer-subtitle">
            <span>Client: {jd.client_name || 'No client assigned'}</span>
            <span className="slug">·</span>
            <JdStatusBadge status={jd.status} />
          </div>
        </div>
        <button
          type="button"
          className="icon-btn req-drawer-close"
          onClick={onClose}
          aria-label="Close details"
          title="Close details"
        >
          <X size={18} />
        </button>
      </div>

      {/* Drawer Underline Navigation Tabs */}
      <div className="req-drawer-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          className={`req-drawer-tab${activeTab === 'overview' ? ' active' : ''}`}
          aria-selected={activeTab === 'overview'}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          type="button"
          role="tab"
          className={`req-drawer-tab${activeTab === 'matches' ? ' active' : ''}`}
          aria-selected={activeTab === 'matches'}
          onClick={() => setActiveTab('matches')}
        >
          Matches ({matches.length})
        </button>
        <button
          type="button"
          role="tab"
          className={`req-drawer-tab${activeTab === 'history' ? ' active' : ''}`}
          aria-selected={activeTab === 'history'}
          onClick={() => setActiveTab('history')}
        >
          History
        </button>
      </div>

      {/* Drawer Content Area */}
      <div className="req-drawer-content">
        {activeTab === 'matches' && (
          <div className="drawer-matches-list">
            {loading ? (
              <p className="req-empty" style={{ padding: '2rem 0', justifyContent: 'center' }}>
                Finding matching candidates…
              </p>
            ) : matches.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-muted)' }}>
                <p>No candidates matched this requirement yet.</p>
                <Link to={searchPath({ jdId: jd.id })} className="btn btn-secondary btn-compact" style={{ marginTop: '0.75rem' }}>
                  Open Candidate Search
                </Link>
              </div>
            ) : (
              <>
                <ol className="drawer-candidates-ordered">
                  {matches.slice(0, 10).map((m, idx) => {
                    const cand = m.candidate;
                    const score = Math.round(m.match_score);
                    const tone = score >= 80 ? 'high' : score >= 60 ? 'mid' : 'low';
                    return (
                      <li key={cand.id} className="drawer-match-card">
                        <span className="drawer-rank-number">{idx + 1}</span>
                        <div className="drawer-candidate-body">
                          <div className="drawer-candidate-headline">
                            <Link
                              to={candidatePath(cand.id)}
                              state={fromState(location, 'Requirements')}
                              className="drawer-candidate-name"
                              style={{ textDecoration: 'none', color: 'inherit' }}
                            >
                              {cand.candidate_name}
                            </Link>
                            <span className={`drawer-score-pill score-${tone}`}>{score}%</span>
                          </div>
                          <div className="drawer-candidate-subline">
                            <span className="candidate-id-badge">{cand.display_id}</span>
                            <span className={`candidate-status-pill status-${(m.requirement_status || cand.status || 'new').toLowerCase().replace(/\s+/g, '-')}`}>
                              {m.requirement_status || cand.status || 'New'}
                            </span>
                            <button
                              type="button"
                              className="icon-btn drawer-mail-btn"
                              title={`Draft email for ${cand.candidate_name}`}
                              onClick={() => onEmail?.(cand)}
                            >
                              <Mail size={13} />
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <div className="drawer-footer-row">
                  <Link to={searchPath({ jdId: jd.id })} className="drawer-view-all-link">
                    View all {matches.length} matches <ArrowRight size={13} />
                  </Link>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="drawer-overview-panel">
            <dl className="drawer-fact-list">
              <div className="drawer-fact">
                <dt><Briefcase size={13} /> Role / Title</dt>
                <dd>{jd.role || jd.title}</dd>
              </div>
              <div className="drawer-fact">
                <dt><Building2 size={13} /> Client</dt>
                <dd>{jd.client_name || '—'}</dd>
              </div>
              <div className="drawer-fact">
                <dt><Users size={13} /> Positions</dt>
                <dd>{formatPositions(jd.no_of_positions)}</dd>
              </div>
              <div className="drawer-fact">
                <dt><MapPin size={13} /> Locations</dt>
                <dd>{formatLocations(jd)}</dd>
              </div>
              <div className="drawer-fact">
                <dt>Experience</dt>
                <dd>{formatExperience(jd.experience_years, jd.relevant_experience_years)}</dd>
              </div>
              {jd.requirement_received_date && (
                <div className="drawer-fact">
                  <dt><Calendar size={13} /> Requirement Received</dt>
                  <dd>{formatDate(jd.requirement_received_date)}</dd>
                </div>
              )}
              {(jd.start_date || jd.end_date) && (
                <div className="drawer-fact">
                  <dt><Calendar size={13} /> Project Timeline</dt>
                  <dd>
                    {jd.start_date ? formatDate(jd.start_date) : 'Start TBD'}
                    {jd.end_date ? ` to ${formatDate(jd.end_date)}` : ''}
                  </dd>
                </div>
              )}
            </dl>
            {jd.jd_text && (
              <div className="drawer-spec-preview">
                <h4>Demand Specification</h4>
                <p>{jd.jd_text.slice(0, 400)}…</p>
              </div>
            )}
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn btn-secondary btn-compact" onClick={() => onOpenFull?.(jd)}>
                Edit & Full Details →
              </button>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="drawer-history-panel">
            <div className="drawer-fact">
              <dt>Created on</dt>
              <dd>{formatDate(jd.created_at)}</dd>
            </div>
            <div className="drawer-fact">
              <dt>Demand Owner</dt>
              <dd>{jd.demand_owner || 'Unassigned'}</dd>
            </div>
            <div className="drawer-fact">
              <dt>Current Status</dt>
              <dd>{jd.current_status || '—'}</dd>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
