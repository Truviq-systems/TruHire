import { Navigate, useParams } from 'react-router-dom';
import SectionTabs from '../components/SectionTabs';
import MetaGate from '../components/ui/MetaGate';
import Notice from '../components/ui/Notice';
import { sectionPath } from '../config/pages';
import { useMeta } from '../context/MetaContext';
import '../components/tracker/tracker-sheet.css';

function Interviews() {
  const { kind } = useParams();
  const { interview_kinds: kinds } = useMeta();
  const interview = kinds.find((k) => k.key === kind);
  if (!kinds.length) return <div className="page-body"><Notice type="error">No interview types are available.</Notice></div>;
  if (!interview) return <Navigate to={sectionPath('interviews', kinds[0].key)} replace />;

  return (
    <div className="page-body">
      <div className="page-header">
        <div>
          <h1>Interviews</h1>
          <p className="dek">{interview.description}</p>
        </div>
      </div>
      <SectionTabs page="interviews" kinds={kinds} label="Interviews" />
      <div className="coming-soon">
        <h2>{interview.title}</h2>
        <p className="dek">Scheduling and outcomes for this interview type are not set up yet. They will appear here once the workflow is defined.</p>
      </div>
    </div>
  );
}

// The Interviews page. Its tabs come from the server; each interview type's workflow is not defined yet,
// so the page says so instead of showing an empty table.
export default function InterviewsPage() {
  return <MetaGate><Interviews /></MetaGate>;
}
