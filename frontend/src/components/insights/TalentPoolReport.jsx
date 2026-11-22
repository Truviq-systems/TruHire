import { AreaChart, BarList } from './charts';
import './insights.css';

// Every bucket the server reports is drawn, in the order it sends them, labelled with its own name; the
// names and thresholds (80%+, 0-2 years, Shortlisted...) are the server's, so nothing here retypes them.
const share = (counts, tone = 'primary') => {
  const entries = Object.entries(counts || {});
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  return entries.map(([name, value]) => ({ name, tone, value, display: `${value} · ${total ? Math.round((value / total) * 100) : 0}%` }));
};

// The Talent pool view: who is in the pool, how well they match, and how fast resumes are arriving.
export default function TalentPoolReport({ data, jds, jdId, onJdChange }) {
  const summary = data.summary || {};
  const skills = (data.top_skills || []).map((s) => ({ name: s.skill, value: s.count, display: `${s.count} ${s.count === 1 ? 'candidate' : 'candidates'}` }));
  const timeline = (data.ingestion_timeline || []).map((d) => ({ label: (d.date || '').slice(5), added: d.resumes_added }));
  const evaluated = summary.evaluated_matches_count || 0;
  const status = share(data.status_funnel);
  const match = share(data.match_score_distribution);
  const experience = share(data.experience_distribution);

  return (
    <div className="report">
      <div className="filters" role="group" aria-label="Filter the report">
        <label className="filter">
          <span>Requirement</span>
          <select className="input-field" value={jdId} onChange={(e) => onJdChange(e.target.value)}>
            <option value="">All requirements</option>
            {jds.map((jd) => <option key={jd.id} value={jd.id}>{jd.display_id ? `${jd.display_id} · ` : ''}{jd.title}</option>)}
          </select>
        </label>
        <span className="filter-note">Applies to match quality only.</span>
      </div>

      <section className="overview" aria-label="Talent pool summary">
        <p className="headline"><strong>{(summary.total_candidates || 0).toLocaleString()}</strong> candidates in the pool</p>
        <p className="subline">
          {summary.average_match_score ? `Average match ${summary.average_match_score}% across ${evaluated} evaluated pairings` : 'No candidate has been matched to a requirement yet'}
          {' · '}{summary.total_batches || 0} upload batches · {summary.total_duplicate_files || 0} duplicate files filtered
        </p>
      </section>

      <div className="grid-2">
        <section className="panel" aria-labelledby="tp-skills">
          <div className="panel-head"><h2 id="tp-skills">Top skills</h2><span className="panel-meta">{skills.length} shown</span></div>
          <p className="panel-dek">Skills found most often in parsed resumes.</p>
          {skills.length ? <BarList rows={skills} scroll /> : <p className="panel-empty">No skills yet. Ingest resumes and they appear here.</p>}
        </section>
        <section className="panel" aria-labelledby="tp-status">
          <h2 id="tp-status">Candidate status</h2>
          <p className="panel-dek">Where candidates are in the recruitment flow, and who is available.</p>
          {status.length ? <BarList rows={status} /> : <p className="panel-empty">No candidates yet.</p>}
        </section>
      </div>

      <div className="grid-2">
        <section className="panel" aria-labelledby="tp-match">
          <h2 id="tp-match">Match quality</h2>
          <p className="panel-dek">How well candidates fit the requirements they were scored against.</p>
          {evaluated ? <BarList rows={match} /> : <p className="panel-empty">Open a requirement to score candidates against it, and the results show here.</p>}
        </section>
        <section className="panel" aria-labelledby="tp-exp">
          <h2 id="tp-exp">Experience</h2>
          <p className="panel-dek">Years of experience across the pool.</p>
          {experience.length ? <BarList rows={experience} /> : <p className="panel-empty">No candidates yet.</p>}
        </section>
      </div>

      <section className="panel" aria-labelledby="tp-timeline">
        <h2 id="tp-timeline">Resumes added</h2>
        <p className="panel-dek">Per day, for the most recent days with uploads.</p>
        {timeline.length ? <AreaChart points={timeline} series={[{ key: 'added', label: 'Resumes added', tone: 'primary' }]} /> : <p className="panel-empty">No uploads yet. Upload resumes under Ingestion.</p>}
      </section>
    </div>
  );
}
