import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Locally the SPA is built straight into backend/static so `python -m cybra`
// serves it. In Docker the backend image is assembled separately, so the UI
// stage builds into its own `dist` and is copied over. One env var keeps both
// paths working instead of the config assuming a single layout.
const outDir = process.env.CYBRA_UI_OUTDIR || '../backend/static'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir,
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
