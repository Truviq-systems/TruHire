// Server-provided enums and limits (GET /api/meta). Pure helpers so they can be unit-tested without React.

// Only used until the first response arrives or if a field is missing; the backend stays the source of truth.
export const FALLBACK_META = Object.freeze({
  roles: ['admin', 'recruiter'],
  jd_statuses: ['Open', 'Cancelled', 'Fulfilled', 'Mapped'],
  default_jd_status: 'Open',
  resume_linked_jd_statuses: ['Mapped', 'Fulfilled'],
  client_names: ['Cretera', 'Infosys', 'Coforge', 'Aaseya', 'NTT Data', 'Utsuk'],
  notice_period_units: ['Days', 'Weeks', 'Months'],
  requirement_statuses: ['New', 'Mapped', 'Shortlisted', 'Interviewed', 'Rejected'],
  default_requirement_status: 'New',
  candidate_statuses: ['New', 'Shortlisted', 'Interviewed', 'Rejected'],
  email_statuses: ['pending', 'sent', 'simulated', 'failed'],
  page_sizes: { history: 25, audit: 25 },
  search: { default_top_n: 20, max_top_n: 100 },
  comment_max_chars: 2000,
  accepted_jd_file_types: ['.pdf', '.docx', '.doc', '.rtf', '.odt', '.txt', '.md'],
  // Newer keys have no copy here on purpose: until the server answers they are empty, and the pages that need
  // them wait for `loaded`. A second copy of a server rule is a rule that can drift.
  inactive_jd_statuses: [],
  fulfilled_jd_statuses: [],
  progressed_requirement_statuses: [],
  availability_statuses: [],
  default_availability: '',
  demand_detail_fields: [],
  tracker_kinds: [],
  interview_kinds: [],
  analytics: { timeline_weeks: 0, attention_limit: 0 },
  ingestion: { stages: [], file_status_weights: {}, final_file_statuses: [], file_outcomes: { processed: [], duplicates: [], failed: [] }, finished_batch_statuses: [], slow_after_seconds: 0 },
  loaded: false,
  error: false,
});

export function normalizeMeta(raw) {
  const data = raw && typeof raw === 'object' ? raw : {};
  const pick = (key) => (data[key] === undefined || data[key] === null ? FALLBACK_META[key] : data[key]);
  return {
    roles: pick('roles'),
    jd_statuses: pick('jd_statuses'),
    default_jd_status: pick('default_jd_status'),
    resume_linked_jd_statuses: pick('resume_linked_jd_statuses'),
    client_names: pick('client_names'),
    notice_period_units: pick('notice_period_units'),
    requirement_statuses: pick('requirement_statuses'),
    default_requirement_status: pick('default_requirement_status'),
    candidate_statuses: pick('candidate_statuses'),
    email_statuses: pick('email_statuses'),
    page_sizes: { ...FALLBACK_META.page_sizes, ...(data.page_sizes || {}) },
    search: { ...FALLBACK_META.search, ...(data.search || {}) },
    comment_max_chars: pick('comment_max_chars'),
    accepted_jd_file_types: pick('accepted_jd_file_types'),
    inactive_jd_statuses: pick('inactive_jd_statuses'),
    fulfilled_jd_statuses: pick('fulfilled_jd_statuses'),
    progressed_requirement_statuses: pick('progressed_requirement_statuses'),
    availability_statuses: pick('availability_statuses'),
    default_availability: pick('default_availability'),
    demand_detail_fields: pick('demand_detail_fields'),
    tracker_kinds: pick('tracker_kinds'),
    interview_kinds: pick('interview_kinds'),
    analytics: { ...FALLBACK_META.analytics, ...(data.analytics || {}) },
    ingestion: { ...FALLBACK_META.ingestion, ...(data.ingestion || {}) },
    // Never true here: the fallback is not the server. See fromServer().
    loaded: false,
    error: false,
  };
}

// The settings as the server sent them. Only this sets `loaded`, so a page that needs the server's rules
// waits for a real answer instead of drawing from the empty fallback.
export const fromServer = (raw) => ({ ...normalizeMeta(raw), loaded: true });
