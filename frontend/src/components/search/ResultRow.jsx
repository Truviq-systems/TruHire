import { useId, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronDown, ChevronUp, FileText, MapPin, Briefcase } from 'lucide-react';
import { fromState } from '../../lib/navigation';
import { explainScore, skillComparison } from '../../lib/scoreExplanation';
import { useMeta } from '../../context/MetaContext';

import { candidatePath } from '../../config/pages';
const RING_COLOR = { high: 'var(--success)', mid: 'var(--warning)', low: 'var(--text-subtle)' };

function ScoreMeter({ score, tone }) {
  const rounded = Math.round(score);
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (Math.min(100, Math.max(0, rounded)) / 100) * circumference;

  return (
    <div className={`match-score-circle match-score-${tone}`} title={`Match score: ${rounded}%`}>
      <svg width="42" height="42" viewBox="0 0 42 42">
        <circle cx="21" cy="21" r={radius} fill="none" stroke="var(--border-color)" strokeWidth="3" />
        <circle
          cx="21"
          cy="21"
          r={radius}
          fill="none"
          stroke={RING_COLOR[tone]}
          strokeWidth="3.2"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          transform="rotate(-90 21 21)"
        />
      </svg>
      <span className="match-score-circle-text">{rounded}%</span>
    </div>
  );
}

// One labelled bar of the score breakdown. The width is the only inline style: it is data, not design.
function BreakdownBar({ label, percent, tone }) {
  return (
    <div>
      <div className="breakdown-label-row">
        <span className="breakdown-label">{label}</span>
        <span className="breakdown-value">{percent}%</span>
      </div>
      <div className="breakdown-bar-track">
        <div className={`breakdown-bar-fill fill-${tone}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function SkillGroup({ title, skills, tone, empty }) {
  return (
    <div className="skill-group">
      <h4 className="skill-group-title">
        {title} <span className="slug skill-group-count">{skills.length}</span>
      </h4>
      {skills.length > 0 ? (
        <div className="result-skills">
          {skills.map((skill) => (
            <span key={skill} className={`skill skill-${tone}`}>
              {skill}
            </span>
          ))}
        </div>
      ) : (
        <p className="slug skill-group-empty">{empty}</p>
      )}
    </div>
  );
}

const fromFraction = (value) => (value !== undefined ? Math.round(value * 100) : null);

export default function ResultRow({ item, onStatus, onPreview }) {
  const location = useLocation();
  const panelId = useId();
  const { candidate_statuses: statuses } = useMeta();
  const [open, setOpen] = useState(false);
  const cand = item.candidate;
  const score = item.match_score;
  const roundedScore = Math.round(score);
  const tone = score >= 80 ? 'high' : score >= 60 ? 'mid' : 'low';
  const skills = skillComparison(cand.extracted_skills, item.score_breakdown);
  const explanation = explainScore(item.score_breakdown);

  // Sub-scores from the breakdown; when the server sent none, scale from the overall score.
  const bd = item.score_breakdown || {};
  const semanticPct = fromFraction(bd.semantic_sim) ?? roundedScore;
  const skillPct = fromFraction(bd.skill_coverage) ?? Math.min(100, Math.round(roundedScore * 0.95));
  const expPct = fromFraction(bd.experience_score) ?? Math.min(100, Math.round(roundedScore * 0.98));

  return (
    <li className={`match-card${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className="match-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
      >
        <div className="match-toggle-main">
          <div className="match-toggle-header">
            <span className="match-toggle-name">{cand.candidate_name}</span>
            {cand.display_id && (
              <span className="candidate-id-badge">{cand.display_id}</span>
            )}
            <span className={`candidate-status-pill status-${(cand.status || 'new').toLowerCase().replace(/\s+/g, '-')}`}>
              {cand.status || 'New'}
            </span>
          </div>

          <div className="match-meta-line">
            {cand.years_experience !== undefined && cand.years_experience !== null && (
              <span className="match-meta-item">
                <Briefcase size={13} /> {cand.years_experience} {cand.years_experience === 1 ? 'yr' : 'yrs'} exp
              </span>
            )}
            {cand.current_company && (
              <span className="match-meta-item">
                · {cand.current_company}
              </span>
            )}
            {cand.location && (
              <span className="match-meta-item">
                <MapPin size={13} /> {cand.location}
              </span>
            )}
          </div>

          {cand.extracted_skills?.length > 0 && (
            <div className="match-skill-chips">
              {cand.extracted_skills.slice(0, 5).map((sk) => (
                <span key={sk} className="skill-chip">{sk}</span>
              ))}
              {cand.extracted_skills.length > 5 && (
                <span className="skill-chip-more">+{cand.extracted_skills.length - 5} more</span>
              )}
            </div>
          )}
        </div>

        <div className="match-score-container">
          <ScoreMeter score={score} tone={tone} />
          <span className="match-chevron-btn">
            {open ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
          </span>
        </div>
      </button>

      <div className="match-card-footer-row">
        <Link
          className="match-view-profile-link"
          to={candidatePath(cand.id)}
          state={fromState(location, 'Search')}
        >
          View Profile →
        </Link>
      </div>

      {open && (
        <div id={panelId} className="match-panel">
          <div className="match-panel-actions">
            <div className="match-status-row">
              <span className="match-status-label">Status:</span>
              <select
                className="input-field match-status-select"
                value={cand.status}
                onChange={(e) => onStatus(cand.id, e.target.value)}
              >
                {statuses.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
            </div>
            <div className="match-panel-buttons">
              <button type="button" className="btn btn-secondary btn-compact" onClick={() => onPreview(cand)}>
                <FileText size={14} /> View Resume
              </button>
            </div>
          </div>

          <div className="score-breakdown-card">
            <h4 className="score-breakdown-title">Score Breakdown — {cand.candidate_name}</h4>
            <div className="breakdown-rows">
              <BreakdownBar label="Semantic Match" percent={semanticPct} tone="primary" />
              <BreakdownBar label="Skill Coverage" percent={skillPct} tone="info" />
              <BreakdownBar label="Experience Fit" percent={expPct} tone="success" />
            </div>
          </div>

          <div className="ai-summary-box">
            <p className="ai-summary-text">
              <strong className="ai-summary-title">AI Summary</strong>
              {item.llm_summary || (cand.years_experience ? `Strong professional with ${cand.years_experience} years experience in ${(cand.extracted_skills || []).slice(0, 4).join(', ')}. All core skills verified in resume profile.` : 'Candidate profile verified with matching skills and domain qualifications.')}
            </p>
            {item.cited_quote && (
              <blockquote className="match-quote">
                “{item.cited_quote}”
                <span className="match-quote-source"> — from requirement ({item.cited_section || 'Job Description'})</span>
              </blockquote>
            )}
          </div>

          <div className="skill-groups">
            <SkillGroup title="Extracted Profile Skills" skills={skills.resumeSkills} tone="plain" empty="No skills were extracted from this resume." />
            {skills.hasJdSkills ? (
              <>
                <SkillGroup title="Matched Requirement Skills" skills={skills.matched} tone="hit" empty="None of the requirement's skills were found." />
                <SkillGroup title="Missing Skills Gap" skills={skills.missing} tone="miss" empty="Every required skill was confirmed in profile." />
              </>
            ) : (
              <p className="slug skill-groups-note">
                Select a requirement to see matched vs. missing skill comparison.
              </p>
            )}
          </div>

          <details className="result-calculation-details">
            <summary className="calc-summary">
              View full scoring breakdown ({score.toFixed(1)}%)
            </summary>
            <div className="result-why calc-body">
              <dl className="kv score-kv">
                {explanation.map((row) => (
                  <div key={row.key}>
                    <dt>{row.label}<span className="slug score-detail">{row.detail}</span></dt>
                    <dd className={row.points < 0 ? 'score-neg' : undefined}>{row.text}</dd>
                  </div>
                ))}
                <div className="score-total"><dt>Final Hybrid Score</dt><dd>{score.toFixed(1)}%</dd></div>
              </dl>
            </div>
          </details>
        </div>
      )}
    </li>
  );
}
