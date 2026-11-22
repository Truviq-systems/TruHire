import { useEffect, useState } from 'react';
import { useMeta } from '../../context/MetaContext';
import { formatSeconds, summarizeUpload } from '../../lib/ingestion';
import './ingestion.css';

// Live card for the upload in progress. Stage names, per-file weights, outcome lists and the "slow" limit all
// come from the server's ingestion settings (GET /api/meta), so this names no status.
export default function UploadProgress({ progress }) {
  const { ingestion } = useMeta();
  const [now, setNow] = useState(() => Date.now());
  const finished = ingestion.finished_batch_statuses.includes(progress?.status);

  // A one-second clock so "working for 18s" and "last update 6s ago" keep moving between server updates.
  useEffect(() => {
    if (!progress || finished) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [progress, finished]);

  const s = summarizeUpload(progress, ingestion, now);
  const tone = !s.finished ? 'warning' : (s.failed > 0 && s.processed === 0 ? 'danger' : (s.processed > 0 ? 'success' : 'neutral'));
  const notices = progress.error_log || [];

  return (
    <div className="up-card">
      <div className="up-top">
        <span className="up-pct">{s.pct}%</span>
        <span className={`badge badge-${tone}`}>{progress.status}</span>
      </div>

      <ol className="up-stages" aria-label="Upload stages">
        {ingestion.stages.map((stage, i) => {
          const state = s.finished || i < s.stageIndex ? 'done' : (i === s.stageIndex ? 'current' : 'todo');
          return <li key={stage.key} className={`up-stage is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>{stage.label}</li>;
        })}
      </ol>

      <div className="progress-bar-bg" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={s.pct} aria-label="Upload progress">
        <div className="progress-bar-fill up-fill" style={{ width: `${s.pct}%` }} />
      </div>

      {!s.finished && (
        <p className={`up-live${s.slow ? ' is-slow' : ''}`} role="status">
          Working for {formatSeconds(s.elapsedSeconds)}
          {s.secondsSinceUpdate !== null && <> · last update {formatSeconds(s.secondsSinceUpdate)} ago</>}
          {s.slow && <> · this step is taking longer than usual, but it is still running</>}
        </p>
      )}

      <dl className="up-metrics">
        <div className="up-metric"><dt>Total</dt><dd>{progress.total_files}</dd></div>
        <div className="up-metric tone-success"><dt>Processed</dt><dd>{s.processed}</dd></div>
        <div className="up-metric tone-warning"><dt>Duplicates</dt><dd>{s.duplicates}</dd></div>
        <div className="up-metric tone-danger"><dt>Failed</dt><dd>{s.failed}</dd></div>
      </dl>

      {notices.length > 0 && (
        <div className="up-notices">
          <h4>Notices ({notices.length})</h4>
          <ul>
            {notices.map((n, i) => <li key={i}><strong>{n.filename}:</strong> {n.error}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
