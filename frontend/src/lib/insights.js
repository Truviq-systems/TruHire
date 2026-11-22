// Pure aggregation for the Analytics report. The page fetches one row per requirement and derives every
// number, chart and total from those rows, so the figures on screen always add up to the table below them.
//
// Nothing here knows a status name. Which statuses are excluded, which mean "fulfilled" and which review
// stages count as progress come from the server (GET /api/meta) as `rules`, built by analyticsRules().
//
// A demand has no recorded fulfilment date, so its last modification stands in for it.

const DAY_MS = 86_400_000;

// The rules the report needs, read from /api/meta. `ready` is false until the server has answered.
export const analyticsRules = (meta) => ({
  inactive: meta.inactive_jd_statuses,
  fulfilled: meta.fulfilled_jd_statuses,
  progressed: meta.progressed_requirement_statuses,
  defaultStatus: meta.default_jd_status,
  timelineWeeks: meta.analytics.timeline_weeks,
  attentionLimit: meta.analytics.attention_limit,
  ready: Boolean(meta.loaded),
});

// Rows as they arrive from the server, with the fields the report relies on always present, so a partial
// or older response cannot crash the page.
export const normalizeRows = (rows, rules) => (Array.isArray(rows) ? rows : []).map((r) => ({
  ...r, no_of_positions: Number(r.no_of_positions) > 0 ? Number(r.no_of_positions) : 1, stages: r.stages || {}, status: r.status || rules.defaultStatus,
}));

export const isCounted = (row, rules) => !rules.inactive.includes(row.status);
export const isFulfilled = (row, rules) => rules.fulfilled.includes(row.status);
export const fulfilledPositions = (row, rules) => (isFulfilled(row, rules) ? row.no_of_positions : 0);
export const progressedCandidates = (row, rules) => rules.progressed.reduce((sum, stage) => sum + (row.stages?.[stage] || 0), 0);
export const openDays = (row, now = new Date()) =>
  (row.created_at ? Math.max(0, Math.floor((now - new Date(row.created_at)) / DAY_MS)) : 0);

// ISO-8601 week of a date, as { year, week }.
export function isoWeek(date) {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return { year: d.getUTCFullYear(), week: Math.ceil(((d - yearStart) / DAY_MS + 1) / 7) };
}

const weekIndex = (date) => Math.floor(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) / (7 * DAY_MS));
const weekLabel = (index) => {
  const { year, week } = isoWeek(new Date(index * 7 * DAY_MS + 3 * DAY_MS)); // a Thursday: its ISO year is the week's
  return `W${week}|${String(year).slice(2)}`;
};

// Cumulative positions opened and fulfilled per ISO week, ending this week, at most rules.timelineWeeks long.
export function weeklyTimeline(rows, rules, now = new Date()) {
  const counted = rows.filter((r) => isCounted(r, rules) && r.created_at);
  if (!counted.length || !(rules.timelineWeeks > 0)) return [];
  const last = weekIndex(now);
  const first = Math.max(Math.min(...counted.map((r) => weekIndex(new Date(r.created_at)))), last - (rules.timelineWeeks - 1));
  const opened = new Map();
  const fulfilled = new Map();
  const add = (map, index, n) => map.set(index, (map.get(index) || 0) + n);
  counted.forEach((r) => {
    add(opened, Math.max(weekIndex(new Date(r.created_at)), first - 1), r.no_of_positions); // older ones fold into the start
    if (isFulfilled(r, rules)) add(fulfilled, Math.max(weekIndex(new Date(r.updated_at || r.created_at)), first - 1), r.no_of_positions);
  });
  let openedTotal = opened.get(first - 1) || 0;
  let fulfilledTotal = fulfilled.get(first - 1) || 0;
  const points = [];
  for (let i = first; i <= last; i += 1) {
    openedTotal += opened.get(i) || 0;
    fulfilledTotal += fulfilled.get(i) || 0;
    points.push({ label: weekLabel(i), opened: openedTotal, fulfilled: fulfilledTotal });
  }
  return points;
}

// Demands still being worked (neither excluded nor fulfilled) that no candidate has progressed on, oldest first.
export function needsAttention(rows, rules, now = new Date()) {
  return rows
    .filter((r) => isCounted(r, rules) && !isFulfilled(r, rules) && progressedCandidates(r, rules) === 0)
    .map((r) => ({ ...r, days: openDays(r, now), considered: Object.values(r.stages || {}).reduce((a, b) => a + b, 0) }))
    .sort((x, y) => y.days - x.days)
    .slice(0, rules.attentionLimit);
}

// Positions and fulfilled positions per client, largest first. `noClient` labels a demand with no client.
export function byClient(rows, rules, noClient) {
  const clients = new Map();
  rows.filter((r) => isCounted(r, rules)).forEach((r) => {
    const name = (r.client_name || '').trim() || noClient;
    const entry = clients.get(name) || { name, positions: 0, fulfilled: 0 };
    entry.positions += r.no_of_positions;
    entry.fulfilled += fulfilledPositions(r, rules);
    clients.set(name, entry);
  });
  return [...clients.values()].sort((a, b) => b.positions - a.positions || a.name.localeCompare(b.name));
}

export function totals(rows, rules) {
  const counted = rows.filter((r) => isCounted(r, rules));
  const positions = counted.reduce((sum, r) => sum + r.no_of_positions, 0);
  const fulfilled = counted.reduce((sum, r) => sum + fulfilledPositions(r, rules), 0);
  const stages = {};
  counted.forEach((r) => Object.entries(r.stages || {}).forEach(([k, v]) => { stages[k] = (stages[k] || 0) + v; }));
  return {
    demands: counted.length, positions, fulfilled, balance: positions - fulfilled,
    percentFulfilled: positions ? Math.round((fulfilled / positions) * 100) : 0,
    considered: Object.values(stages).reduce((a, b) => a + b, 0), stages,
  };
}

// Distinct non-empty values of a field, for the filter dropdowns.
export const distinct = (rows, field) => [...new Set(rows.map((r) => (r[field] || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
