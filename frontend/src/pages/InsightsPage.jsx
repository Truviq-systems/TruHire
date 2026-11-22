import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { insightsApi, jdApi } from '../lib/api';
import { analyticsRules, normalizeRows } from '../lib/insights';
import { errorText } from '../lib/errors';
import { useMeta } from '../context/MetaContext';
import MetaGate from '../components/ui/MetaGate';
import Notice from '../components/ui/Notice';
import RequirementsReport from '../components/insights/RequirementsReport';
import TalentPoolReport from '../components/insights/TalentPoolReport';
import '../components/insights/insights.css';

// The views of this page. Their data and rules come from the server; the first one is the default.
const VIEWS = [
  { key: 'requirements', label: 'Requirements', dek: 'Progress against open positions, what needs attention and where candidates stand.' },
  { key: 'pool', label: 'Talent pool', dek: 'Who is in the pool, how well they match and how fast resumes are arriving.' },
];
const [DEFAULT_VIEW] = VIEWS;

function Skeleton() {
  return (
    <div className="report" role="status" aria-label="Loading analytics">
      <div className="skeleton skeleton-line" />
      <div className="grid-2"><div className="skeleton skeleton-block" /><div className="skeleton skeleton-block" /></div>
      <div className="grid-2"><div className="skeleton skeleton-block" /><div className="skeleton skeleton-block" /></div>
    </div>
  );
}

function Analytics() {
  const meta = useMeta();
  const rules = useMemo(() => analyticsRules(meta), [meta]);
  const [params, setParams] = useSearchParams();
  const view = VIEWS.find((v) => v.key === params.get('view')) || DEFAULT_VIEW;
  const [report, setReport] = useState(null);     // { requirements, stages } from /api/insights/requirements
  const [pool, setPool] = useState(null);
  const [jds, setJds] = useState([]);
  const [jdId, setJdId] = useState('');
  const [error, setError] = useState('');

  const loadRequirements = useCallback(async () => {
    try {
      const data = (await insightsApi.getRequirements()).data;
      setReport({ rows: normalizeRows(data?.requirements, rules), stages: data?.stages || [] });
      setError('');
    } catch (err) {
      setError(errorText(err, 'Could not load the requirements report. Please try again.'));
    }
  }, [rules]);

  const loadPool = useCallback(async (id) => {
    try {
      setPool((await insightsApi.getOverview(id || null)).data);
      setError('');
    } catch (err) {
      setError(errorText(err, 'Could not load the talent pool report. Please try again.'));
    }
  }, []);

  // Each view loads the first time it is shown, so opening Analytics costs one request.
  useEffect(() => {
    if (view === DEFAULT_VIEW && report === null) loadRequirements();
    if (view !== DEFAULT_VIEW && pool === null) {
      loadPool('');
      jdApi.list().then((res) => setJds(res.data)).catch(() => setJds([]));   // the filter just stays short
    }
  }, [view, report, pool, loadRequirements, loadPool]);

  const ready = view === DEFAULT_VIEW ? report : pool;

  return (
    <div className="page-body page">
      <div className="an-head">
        <div>
          <h1>Analytics</h1>
          <p className="dek">{view.dek}</p>
        </div>
        <div className="view-tabs" role="tablist" aria-label="Analytics views">
          {VIEWS.map((v) => (
            <button key={v.key} type="button" role="tab" aria-selected={view === v} className="view-tab"
              onClick={() => setParams(v === DEFAULT_VIEW ? {} : { view: v.key })}>{v.label}</button>
          ))}
        </div>
      </div>

      {error && <Notice type="error" onDismiss={() => setError('')}>{error}</Notice>}
      {ready === null ? (error
        ? <button type="button" className="btn btn-secondary" onClick={() => (view === DEFAULT_VIEW ? loadRequirements() : loadPool(jdId))}>Try again</button>
        : <Skeleton />)
        : view === DEFAULT_VIEW ? <RequirementsReport rows={report.rows} stages={report.stages} rules={rules} />
          : <TalentPoolReport data={pool} jds={jds} jdId={jdId} onJdChange={(id) => { setJdId(id); loadPool(id); }} />}
    </div>
  );
}

export default function InsightsPage() {
  return <MetaGate><Analytics /></MetaGate>;
}
