import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Optional custom fallback — overrides the default error card. */
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * React class-component error boundary.
 *
 * Catches render errors in the subtree and displays a user-friendly fallback
 * instead of crashing the entire app.  Only class components can be error
 * boundaries in React 18.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomePageComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Stack trace goes to console only — never exposed in UI or to external
    // services without explicit configuration (see app/monitoring/sentry.py).
    console.error('[ErrorBoundary]', error.message, info.componentStack)
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div
          role="alert"
          className="flex min-h-[40vh] flex-col items-center justify-center gap-4 p-8 text-center"
        >
          <div className="text-4xl">⚠️</div>
          <h2 className="text-xl font-semibold text-foreground">
            문제가 발생했습니다
          </h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            예상치 못한 오류가 발생했습니다. 페이지를 새로고침하거나 아래 버튼을 눌러
            다시 시도해 주세요.
          </p>
          <button
            onClick={this.handleReset}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            다시 시도
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
