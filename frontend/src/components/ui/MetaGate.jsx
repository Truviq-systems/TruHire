import { useMeta } from '../../context/MetaContext';
import Notice from './Notice';

// Holds a page back until the server's settings (GET /api/meta) have arrived, so it never draws from guesses.
// If the server cannot be reached the settings are retried in the background; the page appears by itself.
export default function MetaGate({ children }) {
  const meta = useMeta();
  if (meta.loaded) return children;
  return (
    <div className="page-body" role="status">
      {meta.error ? <Notice type="info">Cannot reach the TruHire server. Trying again…</Notice> : 'Loading…'}
    </div>
  );
}
