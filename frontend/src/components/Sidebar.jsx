import React from 'react';
import { NavLink } from 'react-router-dom';
import { UploadCloud, FileText, Search, BarChart3, Mail, ShieldCheck, Users, ClipboardList, CalendarClock, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { isAdmin } from '../lib/review';
import { MENU_PAGES } from '../config/pages';
import Logo from './Logo';

// The menu entries (name, path, which are sections with sub-pages, who may see them) come from config/pages.js.
// Only the drawing of each icon is decided here.
// A section (Tracker, Interviews) stays highlighted on its sub-pages, so only plain pages match exactly.
const ICONS = {
  ingestion: UploadCloud, requirements: FileText, search: Search, candidateHistory: Users, tracker: ClipboardList,
  interviews: CalendarClock, email: Mail, analytics: BarChart3, aiAudit: ShieldCheck,
};

export default function Sidebar({ collapsed = false, onToggle }) {
  const { user } = useAuth();
  const items = MENU_PAGES.filter((item) => !item.adminOnly || isAdmin(user));
  return (
    <aside
      id="app-sidebar"
      className={`sidebar${collapsed ? ' collapsed' : ''}`}
      aria-label="Main navigation"
    >
      <div className="sidebar-head">
        <Logo />
        <button
          type="button"
          onClick={onToggle}
          className="icon-btn sidebar-collapse-btn"
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          aria-controls="app-sidebar"
          aria-expanded={!collapsed}
          title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
        >
          {collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
        </button>
      </div>
      <nav className="sidebar-nav">
        {items.map((item) => {
          const Icon = ICONS[item.key];
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={!item.section}
              aria-label={item.name}
              data-tooltip={item.name}
              className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
            >
              <Icon size={18} className="sidebar-icon" />
              <span className="sidebar-label">{item.name}</span>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
