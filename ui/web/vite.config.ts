import { defineConfig } from 'vite';

// Canonical ports/URLs: see ui/ARCHITECTURE.md §"Ports & URLs".
// Dev server: http://127.0.0.1:5173 — the Electron shell (ui/desktop) loads
// this URL in dev. base: './' so the prod build works from file:// in Electron.
export default defineConfig({
  base: './',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    target: 'es2022',
  },
});
