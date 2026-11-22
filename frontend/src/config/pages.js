// The one place that names every page of the app: its path, its label, whether it is in the menu and which
// old paths redirect to it. Routes, the sidebar, the breadcrumb labels and every link read from here, so
// renaming or moving a page is a one-line change and no component retypes a URL.
//
// Sections with tabs (Tracker, Interviews) own `<path>/:kind`; their tabs come from the server (GET /api/meta).
// Plain data on purpose (no components), so tests and config files can import it.

export const PAGES = Object.freeze({
  login: { name: 'Sign in', path: '/login' },
  ingestion: { name: 'Ingestion', path: '/ingestion', menu: true, section: true },
  ingestionHistory: { name: 'Ingestion History', path: '/ingestion/history' },
  requirements: { name: 'Requirements', path: '/requirements', menu: true, aliases: ['/job-descriptions', '/positions', '/demands'] },
  search: { name: 'Search', path: '/search', menu: true },
  candidateHistory: { name: 'Candidate History', path: '/candidate-history', menu: true },
  candidate: { name: 'Candidate', path: '/candidates' },
  tracker: { name: 'Tracker', path: '/tracker', menu: true, section: true, kinds: 'tracker_kinds' },
  interviews: { name: 'Interviews', path: '/interviews', menu: true, section: true, kinds: 'interview_kinds' },
  email: { name: 'Email', path: '/email', menu: true },
  analytics: { name: 'Analytics', path: '/insights', menu: true, aliases: ['/analytics'] },  // no "analytics" in any fetched URL: content blockers refuse them
  aiAudit: { name: 'AI Audit', path: '/ai-audit', menu: true, adminOnly: true, aliases: ['/audit'] },
  assistant: { name: 'Assistant', path: '/assistant' },
});

// Where signed-in people land, and where "/" goes.
export const DEFAULT_ROUTE = PAGES.ingestion.path;

export const MENU_PAGES = Object.freeze(Object.entries(PAGES).filter(([, page]) => page.menu).map(([key, page]) => ({ key, ...page })));

export const candidatePath = (id) => `${PAGES.candidate.path}/${id}`;
export const sectionPath = (page, kind) => `${PAGES[page].path}/${kind}`;
export function searchPath(params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString();
  return `${PAGES.search.path}${query ? `?${query}` : ''}`;
}

// The page a URL path belongs to (longest matching path or alias wins), or null. Used for "Back to <page>" labels.
export function pageForPath(path) {
  if (!path) return null;
  const clean = path.split(/[?#]/)[0];
  let best = null;
  let bestLength = -1;
  Object.values(PAGES).forEach((page) => {
    [page.path, ...(page.aliases || [])].forEach((candidate) => {
      const matches = clean === candidate || clean.startsWith(`${candidate}/`);
      if (matches && candidate.length > bestLength) { best = page; bestLength = candidate.length; }
    });
  });
  return best;
}
