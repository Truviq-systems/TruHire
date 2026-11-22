import assert from 'node:assert/strict';
import { formatIst, timeAgo } from '../src/lib/ingestion.js';

const now = Date.parse('2026-11-04T12:00:00Z');
const ago = (ms) => new Date(now - ms).toISOString();
const S = 1000, M = 60 * S, H = 60 * M, D = 24 * H;

assert.equal(timeAgo(ago(59 * S), now), 'just now');
assert.equal(timeAgo(ago(1 * M), now), '1 minute ago');
assert.equal(timeAgo(ago(59 * M), now), '59 minutes ago');
assert.equal(timeAgo(ago(1 * H), now), '1 hour ago');
assert.equal(timeAgo(ago(23 * H), now), '23 hours ago');
assert.equal(timeAgo(ago(1 * D), now), '1 day ago');
assert.equal(timeAgo(ago(29 * D), now), '29 days ago');
assert.equal(timeAgo(ago(30 * D), now), '1 month ago');
assert.equal(timeAgo(ago(75 * D), now), '2 months ago');
assert.equal(timeAgo(ago(400 * D), now), '1 year ago');
assert.equal(timeAgo(new Date(now + 5 * M).toISOString(), now), 'just now'); // clock skew: future date
// Naive-UTC stamps (no Z) are read as UTC, like the rest of the ingestion helpers.
assert.equal(timeAgo('2026-11-04T10:00:00', now), '2 hours ago');
assert.equal(timeAgo(null, now), '');
assert.equal(timeAgo('garbage', now), '');

// Upload times are always shown in Indian Standard Time (UTC+5:30), whatever the browser's timezone.
assert.equal(formatIst('2026-10-12T12:31:23Z'), '12 Oct 2026, 6:01 PM IST');
assert.equal(formatIst('2026-10-12T12:31:23'), '12 Oct 2026, 6:01 PM IST'); // naive-UTC stamp from the API
assert.equal(formatIst('2026-11-02T18:45:00Z'), '3 Nov 2026, 12:15 AM IST'); // crosses midnight into the next IST day
assert.equal(formatIst(null), '—');
assert.equal(formatIst('garbage'), '—');

console.log('ingestion tests passed');

// ── Live upload card: everything it shows comes from the server's settings ─────────────────────────
import { summarizeUpload, formatSeconds } from '../src/lib/ingestion.js';
const run = (name, fn) => { try { fn(); console.log(`PASS ${name}`); } catch (e) { console.error(`FAIL ${name}
`, e); process.exitCode = 1; } };

const cfg = {
  stages: [{ key: 'one', label: 'One' }, { key: 'two', label: 'Two' }, { key: 'end', label: 'End' }],
  file_status_weights: { waiting: 0, busy: 0.5, ok: 1, dup: 1, bad: 1 },
  file_outcomes: { processed: ['ok'], duplicates: ['dup'], failed: ['bad'] },
  finished_batch_statuses: ['over'], slow_after_seconds: 20,
};
const T0 = Date.parse('2026-11-22T10:00:00Z');
const batch = (o) => ({ status: 'running', stage: 'one', created_at: '2026-11-22T10:00:00', updated_at: '2026-11-22T10:00:05', total_files: 2,
  file_status: [{ filename: 'a', status: 'busy' }, { filename: 'b', status: 'waiting' }], ...o });

run('upload progress weighs each file by the server weights and counts outcomes by the server lists', () => {
  const s = summarizeUpload(batch({ file_status: [{ status: 'ok' }, { status: 'dup' }, { status: 'bad' }, { status: 'busy' }] }), cfg, T0 + 6000);
  assert.deepEqual([s.pct, s.processed, s.duplicates, s.failed], [88, 1, 1, 1]);   // (1+1+1+0.5)/4
});

run('upload progress without per-file rows falls back to the batch counters', () => {
  const s = summarizeUpload({ status: 'running', total_files: 4, processed_count: 1, duplicate_count: 1, failed_count: 0, file_status: [] }, cfg, T0);
  assert.deepEqual([s.pct, s.processed, s.duplicates], [50, 1, 1]);
  assert.equal(summarizeUpload(null, cfg, T0).pct, 0);
});

run('upload progress knows the stage, whether it finished, and says a silent step is slow only past the server limit', () => {
  assert.equal(summarizeUpload(batch({ stage: 'two' }), cfg, T0 + 6000).stageIndex, 2 - 1);
  assert.equal(summarizeUpload(batch({ stage: 'nope' }), cfg, T0 + 6000).stageIndex, 0);
  const quiet = summarizeUpload(batch(), cfg, T0 + 5000 + 19_000);
  const stuck = summarizeUpload(batch(), cfg, T0 + 5000 + 20_000);
  assert.deepEqual([quiet.slow, stuck.slow, stuck.secondsSinceUpdate, stuck.elapsedSeconds], [false, true, 20, 25]);
  assert.equal(summarizeUpload(batch({ status: 'over' }), cfg, T0 + 999_000).slow, false);   // a finished batch is never "slow"
  assert.equal(summarizeUpload(batch({ status: 'over' }), cfg, T0).finished, true);
  assert.equal(summarizeUpload(batch(), { ...cfg, slow_after_seconds: 0 }, T0 + 999_000).slow, false);  // setting not loaded: no guess
});

run('formatSeconds reads as seconds, then minutes', () => {
  assert.deepEqual([formatSeconds(18), formatSeconds(65), formatSeconds(120), formatSeconds(null)], ['18s', '1m 05s', '2m 00s', '']);
});
