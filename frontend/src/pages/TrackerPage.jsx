import { Navigate, useParams } from 'react-router-dom';
import SectionTabs from '../components/SectionTabs';
import TrackerSheet from '../components/tracker/TrackerSheet';
import MetaGate from '../components/ui/MetaGate';
import Notice from '../components/ui/Notice';
import { sectionPath } from '../config/pages';
import { useMeta } from '../context/MetaContext';
import '../components/tracker/tracker-sheet.css';

function Tracker() {
  const { kind } = useParams();
  const { tracker_kinds: kinds } = useMeta();
  const tracker = kinds.find((k) => k.key === kind);
  if (!kinds.length) return <div className="page-body"><Notice type="error">No trackers are available.</Notice></div>;
  if (!tracker) return <Navigate to={sectionPath('tracker', kinds[0].key)} replace />;

  return (
    <div className="page-body">
      <div className="page-header">
        <div>
          <h1>Tracker</h1>
          <p className="dek">{tracker.description}</p>
        </div>
      </div>
      <SectionTabs page="tracker" kinds={kinds} label="Trackers" />
      <TrackerSheet key={kind} kind={kind} exportName={tracker.key} />
    </div>
  );
}

// A tracker page: its tabs, titles and descriptions come from the server, so this file names no tracker.
export default function TrackerPage() {
  return <MetaGate><Tracker /></MetaGate>;
}
