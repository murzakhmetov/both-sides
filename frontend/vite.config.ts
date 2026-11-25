import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const PAGES = /^\/(?:start|receiver|sender|stage|console|demo|login)(?:[/?]|$)/

/** For `npm run dev` only: every page of the app is the same file. */
function appPages(): Plugin {
  return {
    name: 'app-pages',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        if (request.url && PAGES.test(request.url)) request.url = '/app.html'
        next()
      })
    },
  }
}

// The Python server serves the built files from ../web, so the demo needs no Node.
export default defineConfig({
  plugins: [react(), tailwindcss(), appPages()],
  base: '/',
  build: {
    outDir: resolve(import.meta.dirname, '../web'),
    emptyOutDir: true,
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    rolldownOptions: {
      input: { app: resolve(import.meta.dirname, 'app.html') },
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
