import { defineConfig } from '@playwright/test'

const PORT = 8123

// Uses a browser that is already on the laptop, so nothing is downloaded.
// Edge is on every Windows 10 and 11; set E2E_BROWSER=chrome for Chrome.
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: process.env['E2E_BROWSER'] ?? 'msedge',
    locale: 'ru-RU',
    trace: 'off',
  },
  webServer: {
    command: `python run.py --offline --port ${PORT}`,
    cwd: '..',
    url: `http://127.0.0.1:${PORT}/api/status`,
    reuseExistingServer: false,
    env: { BOTHSIDES_STAFF_PASSWORD: 'local-e2e-password' },
  },
})
