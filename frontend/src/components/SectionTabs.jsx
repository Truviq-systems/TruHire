import { NavLink } from 'react-router-dom';
import { sectionPath } from '../config/pages';
import '../components/tracker/tracker-sheet.css';

// The tab row of a section page (Tracker, Interviews). The tabs come from the server (GET /api/meta), so adding
// a tracker or an interview type there adds its tab here with no change to this file.
export default function SectionTabs({ page, kinds, label }) {
  return (
    <nav className="page-tabs" aria-label={label}>
      {kinds.map((kind) => (
        <NavLink key={kind.key} to={sectionPath(page, kind.key)} className={({ isActive }) => `page-tab${isActive ? ' active' : ''}`}>{kind.title}</NavLink>
      ))}
    </nav>
  );
}
