import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { POLL_MS } from '../config/env';
import { metaApi } from '../lib/api';
import { FALLBACK_META, fromServer, normalizeMeta } from '../lib/meta';
import { useAuth } from './AuthContext';

const MetaContext = createContext(normalizeMeta(FALLBACK_META));

export function MetaProvider({ children }) {
  const { token } = useAuth();
  const [meta, setMeta] = useState(() => normalizeMeta(FALLBACK_META));

  // Load the server's settings once signed in. If the server cannot be reached (it restarts, the network drops),
  // keep trying until it answers, so a page waiting on them recovers by itself instead of needing a reload.
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    let timer;
    const load = () => {
      metaApi.get()
        .then((res) => { if (!cancelled) setMeta(fromServer(res.data)); })
        .catch(() => {
          if (cancelled) return;
          setMeta((current) => (current.loaded ? current : { ...current, error: true }));
          timer = setTimeout(load, POLL_MS.metaRetry);
        });
    };
    load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [token]);

  const value = useMemo(() => meta, [meta]);
  return <MetaContext.Provider value={value}>{children}</MetaContext.Provider>;
}

export const useMeta = () => useContext(MetaContext);
