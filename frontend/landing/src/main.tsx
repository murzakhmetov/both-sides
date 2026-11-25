import { StrictMode, useEffect } from 'react'
import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { Backdrop } from './components/Backdrop'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Nav } from './components/Nav'
import { LangProvider, useLang } from './lang'
import { SceneProvider } from './scene'
import { ScrollTrigger, startSmoothScroll } from './scroll'
import { Deny } from './sections/Deny'
import { Example } from './sections/Example'
import { Hero } from './sections/Hero'
import { How } from './sections/How'
import { MiniDemo } from './sections/MiniDemo'
import { Closing, Status, Why } from './sections/Proof'
import { Insight, Problem } from './sections/Story'
import { Verdict } from './sections/Verdict'
import './styles/landing.css'

function Page() {
  const { lang } = useLang()

  useEffect(startSmoothScroll, [])

  // Other words have other heights, so the scroll positions are measured again.
  useEffect(() => {
    ScrollTrigger.refresh()
    void document.fonts?.ready.then(() => ScrollTrigger.refresh())
  }, [lang])

  return (
    <>
      <Backdrop />
      <Nav />
      <main className="relative z-10">
        <Hero />
        <Problem />
        <Insight key={lang} />
        <How />
        <Verdict />
        <Example />
        <Deny />
        <MiniDemo />
        <Why />
        <Status />
        <Closing />
      </main>
    </>
  )
}

const root = document.getElementById('root')
if (root) {
  const page = createRoot(root)
  // At once, before the load event: after a reload the browser then finds the place where the reader was.
  flushSync(() =>
    page.render(
      <StrictMode>
        <LangProvider>
          <ErrorBoundary>
            <SceneProvider>
              <Page />
            </SceneProvider>
          </ErrorBoundary>
        </LangProvider>
      </StrictMode>,
    ),
  )
}
