import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const here = import.meta.dirname

// Videos keep their names. Their addresses carry this, so a browser never shows an old clip after a new build.
const media = createHash('sha256').update(readFileSync(resolve(here, '../../landing-media/manifest.json')))

// Builds into the same folder as the app. The app build runs first, because it empties ../web (see package.json).
export default defineConfig({
  root: here,
  base: '/',
  publicDir: resolve(here, '../../landing-media/public'),
  plugins: [react(), tailwindcss()],
  define: { __MEDIA_VERSION__: JSON.stringify(media.digest('hex').slice(0, 8)) },
  resolve: { alias: { '@fonts': resolve(here, '../node_modules/@fontsource-variable') } },
  build: {
    outDir: resolve(here, '../../web'),
    emptyOutDir: false,
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    rolldownOptions: {
      input: { landing: resolve(here, 'index.html') },
      // Short names: Windows stops at 260 characters per path.
      output: {
        assetFileNames: (file) => (file.names[0]?.endsWith('.woff2') ? 'assets/f-[hash][extname]' : 'assets/[name]-[hash][extname]'),
      },
    },
  },
  server: {
    port: 5174,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
