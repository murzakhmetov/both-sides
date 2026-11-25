import { Component, type ReactNode } from 'react'
import { useLang } from '../lang'

interface Props {
  readonly children: ReactNode
}

function Broken() {
  const { t } = useLang()
  return (
    <main className="shell flex min-h-svh flex-col justify-center gap-8">
      <h1 className="display display-lg">{t('hero.title')}</h1>
      <p className="max-w-[33rem] text-[1.15rem]">{t('hero.sub')}</p>
      <p>
        <a className="button button-gold" href="/start">
          {t('nav.demo')}
        </a>
      </p>
      <p className="caption">{t('footer.note')}</p>
    </main>
  )
}

/** If the page breaks, the visitor still gets the idea and the way to the app. */
export class ErrorBoundary extends Component<Props, { readonly broken: boolean }> {
  override state = { broken: false }

  static getDerivedStateFromError() {
    return { broken: true }
  }

  override render() {
    return this.state.broken ? <Broken /> : this.props.children
  }
}
