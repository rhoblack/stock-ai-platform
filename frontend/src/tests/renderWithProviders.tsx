import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/components/theme/ThemeProvider'

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: string[]
  client?: QueryClient
}

export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {},
) {
  const {
    initialEntries = ['/'],
    client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    }),
    ...rest
  } = options

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    )
  }

  return { client, ...render(ui, { wrapper: Wrapper, ...rest }) }
}
