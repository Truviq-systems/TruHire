import assert from 'node:assert/strict';
import { analyticsRules, byClient, distinct, isoWeek, needsAttention, normalizeRows, openDays, totals, weeklyTimeline } from '../src/lib/insights.js';
import { FALLBACK_META, fromServer, normalizeMeta } from '../src/lib/meta.js';

const run = (name, fn) => { try { fn(); console.log(`PASS ${name}`); } catch (e) { console.error(`FAIL ${name}\n`, e); process.exitCode = 1; } };

// The rules are supplied the way the server supplies them (GET /api/meta); the test names its own statuses
// on purpose, to show the library does not depend on the product's wording.
const meta = fromServer({
  inactive_jd_statuses: ['Dropped'], fulfilled_jd_statuses: ['Done'], progressed_requirement_statuses: ['Ahead', 'Further'],
  default_jd_status: 'Live', analytics: { timeline_weeks: 26, attention_limit: 5 },
});
const rules = analyticsRules(meta);
const NOW = new Date('2026-11-22T12:00:00Z');
const row = (o) => ({ no_of_positions: 1, status: 'Live', client_name: 'Acme', stages: {}, created_at: '2026-11-01T00:00:00Z', ...o });

run('rules are read from the server meta, and are not ready before it answers', () => {
  assert.deepEqual([rules.inactive, rules.fulfilled, rules.progressed, rules.attentionLimit], [['Dropped'], ['Done'], ['Ahead', 'Further'], 5]);
  assert.equal(rules.ready, true);
  const before = analyticsRules(normalizeMeta(FALLBACK_META));   // what a page sees before the server has answered
  assert.equal(before.ready, false);
  assert.deepEqual(before.inactive, FALLBACK_META.inactive_jd_statuses);
  assert.deepEqual(before.fulfilled, []);
});

run('isoWeek follows ISO-8601 around the year boundary', () => {
  assert.deepEqual(isoWeek(new Date('2026-01-01T00:00:00Z')), { year: 2026, week: 1 });
  assert.deepEqual(isoWeek(new Date('2025-12-29T00:00:00Z')), { year: 2026, week: 1 });
  assert.deepEqual(isoWeek(new Date('2026-11-22T00:00:00Z')), { year: 2026, week: 47 });
});

run('an excluded demand is not counted; a fulfilled demand fulfils all its positions', () => {
  const rows = [row({ no_of_positions: 3 }), row({ no_of_positions: 2, status: 'Done' }), row({ no_of_positions: 9, status: 'Dropped' })];
  const t = totals(rows, rules);
  assert.deepEqual([t.positions, t.fulfilled, t.balance, t.percentFulfilled, t.demands], [5, 2, 3, 40, 2]);
});

run('totals add candidate stage counts and survive no rows', () => {
  const t = totals([row({ stages: { Ahead: 2, Out: 1 } }), row({ stages: { Ahead: 1 } })], rules);
  assert.equal(t.stages.Ahead, 3);
  assert.equal(t.considered, 4);
  assert.equal(totals([], rules).percentFulfilled, 0);
});

run('needs attention lists worked demands where nobody progressed, oldest first, up to the limit', () => {
  const rows = [
    row({ id: 'new', created_at: '2026-11-18T00:00:00Z' }),
    row({ id: 'old', created_at: '2026-08-01T00:00:00Z', stages: { Waiting: 3 } }),
    row({ id: 'moving', created_at: '2026-07-01T00:00:00Z', stages: { Further: 1 } }),
    row({ id: 'done', created_at: '2026-06-01T00:00:00Z', status: 'Done' }),
    row({ id: 'dead', created_at: '2026-06-01T00:00:00Z', status: 'Dropped' }),
  ];
  const list = needsAttention(rows, rules, NOW);
  assert.deepEqual(list.map((r) => r.id), ['old', 'new']);
  assert.equal(list[0].considered, 3);
  assert.equal(openDays(rows[1], NOW), list[0].days);
  assert.equal(needsAttention(rows, { ...rules, attentionLimit: 1 }, NOW).length, 1);
});

run('by client groups, sorts largest first and uses the label it is given for a missing client', () => {
  const rows = [row({ client_name: 'Zed', no_of_positions: 1 }), row({ client_name: 'Acme', no_of_positions: 5 }), row({ client_name: null }), row({ client_name: 'Acme', status: 'Dropped', no_of_positions: 50 })];
  assert.deepEqual(byClient(rows, rules, 'Unassigned').map((c) => [c.name, c.positions]), [['Acme', 5], ['Unassigned', 1], ['Zed', 1]]);
});

run('weekly timeline is cumulative, ends this week and fulfilled never exceeds opened', () => {
  const rows = [row({ created_at: '2026-10-05T00:00:00Z', no_of_positions: 2 }),
    row({ created_at: '2026-10-19T00:00:00Z', no_of_positions: 3, status: 'Done', updated_at: '2026-11-09T00:00:00Z' })];
  const points = weeklyTimeline(rows, rules, NOW);
  const last = points[points.length - 1];
  assert.deepEqual([last.label, last.opened, last.fulfilled, points[0].opened], ['W47|26', 5, 3, 2]);
  points.forEach((p, i) => { assert.ok(p.fulfilled <= p.opened); if (i) assert.ok(p.opened >= points[i - 1].opened); });
  assert.deepEqual(weeklyTimeline([], rules, NOW), []);
});

run('weekly timeline length follows the server setting and folds older demands into the first week', () => {
  const points = weeklyTimeline([row({ created_at: '2020-01-01T00:00:00Z', no_of_positions: 7 })], { ...rules, timelineWeeks: 4 }, NOW);
  assert.equal(points.length, 4);
  assert.equal(points[0].opened, 7);
  assert.deepEqual(weeklyTimeline([row()], { ...rules, timelineWeeks: 0 }, NOW), []);  // setting not loaded: draw nothing, guess nothing
});

run('distinct trims, drops blanks and sorts', () => {
  assert.deepEqual(distinct([{ c: ' b ' }, { c: 'a' }, { c: '' }, { c: 'b' }, {}], 'c'), ['a', 'b']);
});

run('normalizeRows fills the fields the report needs, using the server default status, and tolerates a bad response', () => {
  const [r] = normalizeRows([{ id: 'x', title: 't' }], rules);
  assert.deepEqual([r.no_of_positions, r.stages, r.status], [1, {}, 'Live']);
  assert.equal(normalizeRows([{ no_of_positions: 0 }], rules)[0].no_of_positions, 1);
  assert.deepEqual(normalizeRows(undefined, rules), []);
  assert.doesNotThrow(() => totals(normalizeRows([{ id: 'x' }], rules), rules));
});
