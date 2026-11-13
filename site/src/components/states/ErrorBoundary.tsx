import { Component, type ReactNode } from "react";
import { ErrorState } from "./States";

/**
 * W4-03: a page that fails while rendering shows the unified error state instead of a blank screen.
 * `resetKey` (the route) clears the error when the user navigates elsewhere.
 */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidUpdate(prev: { resetKey?: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }
  render() {
    return this.state.error ? <div data-testid="page-error"><ErrorState detail={this.state.error.message} /></div> : this.props.children;
  }
}
