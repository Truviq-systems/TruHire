import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowUp, CheckCircle2, Clock, XCircle } from 'lucide-react';
import { PAGES } from '../../config/pages';
import {
  byClient, distinct, fulfilledPositions, isCounted, needsAttention, openDays, totals, weeklyTimeline,
} from '../../lib/insights';
import { formatDate } from '../../lib/requirements';
import { AreaChart, BarList, Legend, Progress, ProgressList } from './charts';
import './insights.css';

// Fields of a report row that can filter it. Which values exist, and what they mean, comes from the data and
// from `rules` (GET /api/meta); this file names no status and no review stage.
const FILTERS = [
  { field: 'client_name', label: 'Client' },
  { field: 'practice', label: 'Practice' },
  { field: 'status', label: 'Status' },
];
const NO_CLIENT = 'No client';

// A status reads as done, excluded or in progress by the server's rules, not by its name.
function statusView(status, rules) {
  if (rules.fulfilled.includes(status)) return { Icon: CheckCircle2, tone: 'success' };
  if (rules.inactive.includes(status)) return { Icon: XCircle, tone: 'danger' };
  return { Icon: Clock, tone: 'info' };
}

function StatusCell({ status, rules }) {
  const { Icon, tone } = statusView(status, rules);
  return <span className={`status-cell tone-text-${tone}`}><Icon size={15} aria-hidden="true" />{status}</span>;
}

const sumStages = (row) => Object.values(row.stages).reduce((a, b) => a + b, 0);

// The Requirements view, top to bottom: how we are doing, what needs attention, where candidates are, how
// demand moved, then every requirement in a table you can search and sort.
export default function RequirementsReport({ rows, stages, rules }) {
  const [filters, setFilters] = useState({ client_name: '', practice: '', status: '' });
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState({ key: 'days', dir: 'desc' });
  const now = useMemo(() => new Date(), []);
  const shown = useMemo(() => rows.filter((r) => FILTERS.every(({ field }) => !filters[field] || (r[field] || '') === filters[field])), [rows, filters]);
  const sum = useMemo(() => totals(shown, rules), [shown, rules]);
  const clients = useMemo(() => byClient(shown, rules, NO_CLIENT), [shown, rules]);
  const timeline = useMemo(() => weeklyTimeline(shown, rules, now), [shown, rules, now]);
  const attention = useMemo(() => needsAttention(shown, rules, now), [shown, rules, now]);

  const columns = useMemo(() => [
    { key: 'display_id', label: 'Demand', value: (r) => r.display_id || '' },
    { key: 'client_name', label: 'Client', value: (r) => r.client_name || '' },
    { key: 'days', label: 'Open days', numeric: true, desc: true, value: (r) => openDays(r, now) },
    { key: 'progress', label: 'Positions fulfilled', value: (r) => fulfilledPositions(r, rules) / r.no_of_positions },
    { key: 'considered', label: 'Candidates', numeric: true, desc: true, value: sumStages },
    ...rules.progressed.map((stage) => ({ key: `stage:${stage}`, label: stage, numeric: true, desc: true, value: (r) => r.stages[stage] || 0 })),
    { key: 'status', label: 'Status', value: (r) => r.status },
  ], [rules, now]);

  const listed = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const col = columns.find((c) => c.key === sort.key) || columns[0];
    return shown
      .filter((r) => !needle || `${r.display_id} ${r.title} ${r.client_name || ''}`.toLowerCase().includes(needle))
      .sort((a, b) => {
        const x = col.value(a);
        const y = col.value(b);
        const order = typeof x === 'number' ? x - y : String(x).localeCompare(String(y));
        return sort.dir === 'asc' ? order : -order;
      });
  }, [shown, query, sort, columns]);

  if (rows.length === 0) {
    return (
      <p className="report-empty">
        No requirements yet. Create one under <Link to={PAGES.requirements.path}>Requirements</Link> and its progress, candidates and age appear here.
      </p>
    );
  }

  const pipeline = stages.map((name) => ({ name, value: sum.stages[name] || 0, tone: rules.progressed.includes(name) ? 'primary' : 'muted' }));
  const progressedNames = rules.progressed.join(' or ').toLowerCase();
  const toggleSort = (col) => setSort((s) => (s.key === col.key ? { key: col.key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key: col.key, dir: col.desc ? 'desc' : 'asc' }));
  const excluded = rules.inactive.join(', ');

  return (
    <div className="report">
      <div className="filters" role="group" aria-label="Filter the report">
        {FILTERS.map(({ field, label }) => (
          <label key={field} className="filter">
            <span>{label}</span>
            <select className="input-field" value={filters[field]} onChange={(e) => setFilters((f) => ({ ...f, [field]: e.target.value }))}>
              <option value="">All</option>
              {distinct(rows, field).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
        ))}
      </div>

      <section className="overview" aria-label="Overall progress">
        <p className="headline"><strong>{sum.fulfilled} of {sum.positions}</strong> positions fulfilled <span className="headline-pct">({sum.percentFulfilled}%)</span></p>
        <Progress done={sum.fulfilled} total={sum.positions} label={`${sum.fulfilled} of ${sum.positions} positions fulfilled`} />
        <p className="subline">
          {sum.demands} {sum.demands === 1 ? 'requirement' : 'requirements'} · {sum.balance} {sum.balance === 1 ? 'position' : 'positions'} still to fill · {sum.considered} candidates considered
          {rules.progressed.map((stage) => ` · ${sum.stages[stage] || 0} ${stage.toLowerCase()}`).join('')}
        </p>
      </section>

      <div className="grid-2">
        <section className="panel" aria-labelledby="rp-attention">
          <h2 id="rp-attention">Needs attention</h2>
          <p className="panel-dek">Requirements still open where no candidate is {progressedNames} yet, oldest first.</p>
          {attention.length ? (
            <ul className="attention">
              {attention.map((r) => (
                <li key={r.id}>
                  <span className="attention-title"><span className="slug">{r.display_id}</span> {r.title}</span>
                  <span className="attention-meta">{r.client_name || NO_CLIENT} · open {r.days} {r.days === 1 ? 'day' : 'days'} · {r.considered ? `${r.considered} considered, none ${progressedNames}` : 'no candidates considered yet'}</span>
                </li>
              ))}
            </ul>
          ) : <p className="panel-empty">Nothing is waiting. Every open requirement has a candidate who is {progressedNames}.</p>}
          {attention.length > 0 && <Link className="panel-link" to={PAGES.requirements.path}>Open requirements</Link>}
        </section>

        <section className="panel" aria-labelledby="rp-clients">
          <h2 id="rp-clients">Progress by client</h2>
          <p className="panel-dek">Positions fulfilled out of positions opened.</p>
          {clients.length ? <ProgressList rows={clients.map((c) => ({ name: c.name, done: c.fulfilled, total: c.positions }))} noun="positions" />
            : <p className="panel-empty">No positions for these filters.</p>}
        </section>
      </div>

      <div className="grid-2">
        <section className="panel" aria-labelledby="rp-stages">
          <h2 id="rp-stages">Candidates by review stage</h2>
          <p className="panel-dek">Where candidates stand across the requirements shown.</p>
          {sum.considered ? <BarList rows={pipeline} /> : <p className="panel-empty">No candidate has been given a status on these requirements yet.</p>}
        </section>

        <section className="panel" aria-labelledby="rp-timeline">
          <h2 id="rp-timeline">Demand over time</h2>
          <p className="panel-dek">Running total of positions opened and fulfilled, by week.</p>
          <Legend items={[{ label: 'Positions opened', tone: 'muted' }, { label: 'Fulfilled', tone: 'primary' }]} />
          {timeline.length ? <AreaChart points={timeline} series={[{ key: 'opened', label: 'Positions opened', tone: 'muted' }, { key: 'fulfilled', label: 'Fulfilled', tone: 'primary' }]} />
            : <p className="panel-empty">No dated requirements for these filters.</p>}
          <p className="panel-note">Fulfilled is dated by the requirement&apos;s last update; the day it was fulfilled is not recorded.</p>
        </section>
      </div>

      <section className="panel" aria-labelledby="rp-all">
        <div className="panel-head">
          <h2 id="rp-all">All requirements</h2>
          <input className="input-field search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by ID, title or client" aria-label="Search requirements" />
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c.key} scope="col" className={c.numeric ? 'num' : undefined} aria-sort={sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    <button type="button" className="sort" onClick={() => toggleSort(c)}>
                      {c.label}
                      {sort.key === c.key && (sort.dir === 'asc' ? <ArrowUp size={13} aria-hidden="true" /> : <ArrowDown size={13} aria-hidden="true" />)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {listed.map((r) => {
                const counted = isCounted(r, rules);
                const done = fulfilledPositions(r, rules);
                return (
                  <tr key={r.id} className={counted ? undefined : 'is-cancelled'}>
                    <td><span className="slug">{r.display_id || '—'}</span><span className="row-title">{r.title}</span></td>
                    <td>{r.client_name || <span className="text-subtle">—</span>}</td>
                    <td className="num" title={`Opened ${formatDate(r.created_at)}`}>{openDays(r, now)}</td>
                    <td className="cell-progress">
                      {counted ? <><Progress done={done} total={r.no_of_positions} label={`${r.display_id}: ${done} of ${r.no_of_positions} positions fulfilled`} />
                        <span className="cell-progress-text">{done} of {r.no_of_positions}</span></> : <span className="text-subtle">—</span>}
                    </td>
                    <td className="num">{sumStages(r)}</td>
                    {rules.progressed.map((stage) => <td key={stage} className="num">{r.stages[stage] || 0}</td>)}
                    <td><StatusCell status={r.status} rules={rules} /></td>
                  </tr>
                );
              })}
              {listed.length === 0 && <tr><td colSpan={columns.length} className="panel-empty">No requirement matches.</td></tr>}
            </tbody>
          </table>
        </div>
        {excluded && <p className="panel-note">{excluded} requirements are listed but not counted in the totals above.</p>}
      </section>
    </div>
  );
}
