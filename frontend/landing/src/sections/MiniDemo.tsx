import { useRef } from 'react'
import { DemoForm } from '../components/DemoForm'
import { useReveal } from '../hooks/useReveal'
import { useLang } from '../lang'
import { useSceneOnScroll } from '../scene'

/** Two answers and the same verdict as the offline matcher of the app: the form asks the project server. */
export function MiniDemo() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  useSceneOnScroll(root, 'line')
  useReveal(root)
  return (
    <section
      aria-labelledby="demo-title"
      className="scrim-full relative flex min-h-svh items-center py-28"
      id="demo"
      ref={root}
      tabIndex={-1}
    >
      <div className="shell relative">
        <h2 className="display display-lg" data-reveal="0" id="demo-title">
          {t('demo.title')}
        </h2>
        <p className="mt-4 max-w-[42rem] text-bcc-green-light" data-reveal="1">
          {t('demo.label')}
        </p>
        <div className="mt-7" data-reveal="2">
          <DemoForm />
        </div>
      </div>
    </section>
  )
}
