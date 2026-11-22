import './insights.css';

// Chart pieces for the Analytics page. Grey is the baseline series (positions opened) and the accent is the
// outcome (fulfilled). Widths and heights are data, so they are the only inline styles.

const pct = (value, max) => (max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0);

// Round an axis maximum up to 1, 2, 5 or 10 times a power of ten so gridlines land on whole numbers.
export function niceMax(value) {
  if (value <= 0) return 1;
  const unit = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 5, 10].map((m) => m * unit).find((n) => n >= value);
}

export function Legend({ items }) {
  return (
    <ul className="legend">
      {items.map((i) => <li key={i.label}><span className={`legend-dot tone-${i.tone}`} aria-hidden="true" />{i.label}</li>)}
    </ul>
  );
}

// One progress bar: `done` of `total`. The width is data, so it is the only inline style.
export function Progress({ done, total, label }) {
  return (
    <span className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}>
      <span className="progress-fill" style={{ width: `${pct(done, total)}%` }} />
    </span>
  );
}

// "x of y" progress per row, e.g. positions fulfilled per client.
export function ProgressList({ rows, noun }) {
  return (
    <ul className="progress-list">
      {rows.map((r) => (
        <li key={r.name} className="progress-row">
          <span className="progress-top">
            <span className="progress-name" title={r.name}>{r.name}</span>
            <span className="progress-count">{r.done} of {r.total} {noun}</span>
          </span>
          <Progress done={r.done} total={r.total} label={`${r.name}: ${r.done} of ${r.total} ${noun}`} />
        </li>
      ))}
    </ul>
  );
}

// A ranked list of single bars (skills, statuses, distributions). Each row: name, optional note, value.
export function BarList({ rows, scroll = false }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className={`barlist${scroll ? ' barlist-scroll' : ''}`}>
      {rows.map((r) => (
        <li key={r.name} className="barlist-row">
          <span className="barlist-top">
            <span className="barlist-name">{r.name}{r.note && <span className="barlist-note">{r.note}</span>}</span>
            <span className="barlist-value">{r.display ?? r.value}</span>
          </span>
          <span className="barlist-track" role="presentation">
            <span className={`barlist-fill tone-${r.tone || 'primary'}`} style={{ width: `${Math.max(pct(r.value, max), r.value > 0 ? 3 : 0)}%` }} />
          </span>
        </li>
      ))}
    </ul>
  );
}

// Area chart over weeks (or days). `series` back to front: [{ key, label, tone }]; `points` carry the labels
// and one value per key. A single point cannot form an area, so it is drawn as one bar per series.
export function AreaChart({ points, series }) {
  const max = niceMax(Math.max(...points.flatMap((p) => series.map((s) => p[s.key] || 0)), 1));
  const x = (i) => (points.length === 1 ? 50 : (i / (points.length - 1)) * 100);
  const y = (v) => 100 - pct(v, max);
  const ticks = [max, max / 2, 0];
  const every = Math.max(1, Math.ceil(points.length / 6));
  const summary = series.map((s) => `${s.label} ${points[points.length - 1][s.key] || 0}`).join(', ');
  return (
    <div className="area">
      <div className="area-y" aria-hidden="true">{ticks.map((t) => <span key={t}>{Number.isInteger(t) ? t : t.toFixed(1)}</span>)}</div>
      <div className="area-plot" role="img" aria-label={`${series.map((s) => s.label).join(' and ')} by week. Latest: ${summary}`}>
        <span className="area-grid" style={{ top: '0%' }} />
        <span className="area-grid" style={{ top: '50%' }} />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none">
          {series.map((s) => {
            if (points.length === 1) {
              const top = y(points[0][s.key] || 0);
              return <rect key={s.key} className={`area-fill tone-${s.tone}`} x="40" y={top} width="20" height={100 - top} />;
            }
            const line = points.map((p, i) => `${x(i)},${y(p[s.key] || 0)}`).join(' ');
            return (
              <g key={s.key}>
                <polygon className={`area-fill tone-${s.tone}`} points={`0,100 ${line} 100,100`} />
                <polyline className={`area-line tone-${s.tone}`} points={line} />
              </g>
            );
          })}
        </svg>
      </div>
      <div className="area-x" aria-hidden="true">
        {points.map((p, i) => <span key={p.label} className={i % every ? 'is-hidden' : undefined}>{p.label}</span>)}
      </div>
    </div>
  );
}
