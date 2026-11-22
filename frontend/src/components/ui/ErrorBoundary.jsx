import { Component } from 'react';

// Catches a crash while rendering a page, so the sidebar and top bar stay and the person sees what happened
// instead of a blank screen. A page chunk that fails to load (typically a tab left open across a deploy)
// lands here too; reloading fetches the new files. Render it with a `key` that changes per route so
// navigating away resets it.
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Page crashed:', error, info?.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const message = String(error?.message || error).slice(0, 300);
    const stale = /dynamically imported module|Importing a module script failed|Loading chunk/i.test(message);
    return (
      <div className="page-body" role="alert">
        <h1>{stale ? 'TruHire was updated' : 'This page hit a problem'}</h1>
        <p className="dek">
          {stale ? 'Reload to get the latest version.' : 'The rest of TruHire still works. Reload the page, or open another section from the menu.'}
        </p>
        <p className="slug">{message}</p>
        <p><button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>Reload</button></p>
      </div>
    );
  }
}
