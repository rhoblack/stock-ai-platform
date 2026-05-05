/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Backend (v0.1-backend-final) runs on http://127.0.0.1:8000.
// /api and /health are proxied so the frontend can call them with
// same-origin URLs and avoid CORS in dev. Production deployment goes
// through a separate web container — FastAPI does NOT serve the
// frontend bundle (v0.1 backend is frozen).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Phase F: 무거운 vendor 라이브러리를 별도 청크로 분리해 첫 진입
        // 번들 크기를 줄인다. recharts 가 가장 크므로 우선 분리.
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-table': ['@tanstack/react-table'],
          'vendor-charts': ['recharts'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    css: true,
    restoreMocks: true,
    // Playwright e2e 파일 (e2e/**/*.spec.ts) 은 별도 runner (`npm run e2e`)
    // 에서 실행되므로 vitest 의 기본 glob 에서 제외한다.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', '.vite', 'e2e/**'],
  },
})
