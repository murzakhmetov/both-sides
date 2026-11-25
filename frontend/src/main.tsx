import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { TopBar } from './components/ui'
import { I18nProvider, useI18n } from './i18n'
import { ConsolePage } from './pages/ConsolePage'
import { DemoPage } from './pages/DemoPage'
import { LoginPage } from './pages/LoginPage'
import { PhonePage } from './pages/PhonePage'
import { StagePage } from './pages/StagePage'
import { StartPage } from './pages/StartPage'
import { screenOf, type Screen } from './routes'
import './styles/index.css'

function NotFound() {
  const { t } = useI18n()
  return (
    <>
      <TopBar />
      <main className="px-4 py-16 text-center">
        <h1 className="text-3xl font-bold tracking-tight">{t('notfound.title')}</h1>
      </main>
    </>
  )
}

const embedded = new URLSearchParams(window.location.search).get('embed') === '1'

function pageOf(screen: Screen): ReactNode {
  const pages: Readonly<Record<Screen, () => ReactNode>> = {
    start: () => <StartPage />,
    receiver: () => <PhonePage side="receiver" />,
    sender: () => <PhonePage side="sender" />,
    stage: () => <StagePage embedded={embedded} />,
    console: () => <ConsolePage />,
    demo: () => <DemoPage />,
    login: () => <LoginPage />,
    notfound: () => <NotFound />,
  }
  return pages[screen]()
}

// The pages inside the demo page have thin scroll bars. See index.css.
if (window.self !== window.top) document.documentElement.dataset['embedded'] = 'true'

const screen = screenOf(window.location.pathname)
const root = document.getElementById('root')
if (root) {
  createRoot(root).render(
    <StrictMode>
      <I18nProvider screen={screen === 'stage' && embedded ? 'demo' : screen}>{pageOf(screen)}</I18nProvider>
    </StrictMode>,
  )
}
