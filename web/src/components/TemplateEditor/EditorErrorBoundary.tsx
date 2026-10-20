import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  title?: string;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class EditorErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('[EditorErrorBoundary] Caught error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 m-4 bg-white rounded-xl shadow border border-rose-200 text-center flex flex-col items-center justify-center">
          <div className="w-12 h-12 mb-3 text-rose-600 bg-rose-50 rounded-full flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-800 mb-1">
            {this.props.title || 'Component Encountered a Problem'}
          </h3>
          <p className="text-xs text-slate-600 mb-4 max-w-sm">
            {this.state.error?.message || 'An unexpected rendering error occurred. You can reload this component.'}
          </p>
          <button
            onClick={this.handleReset}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white font-medium text-xs rounded shadow-sm transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Try Recovering
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
