import { Link, useLocation } from 'react-router-dom';
import { fromState } from '../../lib/navigation';

import { candidatePath } from '../../config/pages';
// Near matches for the single search box (name, email, phone number or current company).
export default function CandidateLookup({ matches }) {
  const location = useLocation();
  if (!matches.length) return null;
  return (
    <section className="candidate-lookup card" aria-labelledby="candidate-lookup-title">
      <h2 id="candidate-lookup-title">Matching candidates ({matches.length})</h2>
      <ul className="candidate-lookup-list">
        {matches.map((candidate) => <li key={candidate.id}>
          <Link to={candidatePath(candidate.id)} state={fromState(location, 'Search')}>
            <strong>{candidate.candidate_name}</strong>
            <span>{[candidate.display_id, candidate.current_company, candidate.email, candidate.phone].filter(Boolean).join(' · ')}</span>
          </Link>
        </li>)}
      </ul>
    </section>
  );
}
