import { useRef, useState } from 'react'
import { errorCode, post } from '../api/client'
import type { SceneList, StageView } from '../api/types'
import { DemoPhone, type PhoneLook } from '../components/DemoPhone'
import { BetaNote, Button, Problem, TOP_LINK, TopBar, choiceClass } from '../components/ui'
import { useNotice } from '../hooks/useNotice'
import { REFRESH_MESSAGE, usePoll } from '../hooks/usePoll'
import { useStaffOnly } from '../hooks/useStaffOnly'
import { hasKey, useI18n, useTitle } from '../i18n'

const POLL_MS = 2000
const LOOK_STORAGE = 'bothsides.demo.look'

/** The framed phones get smaller with the window; the plain ones keep the width of a phone. */
const COLUMNS: Readonly<Record<PhoneLook, string>> = {
  framed: 'xl:grid-cols-[minmax(300px,25%)_1fr_minmax(300px,25%)]',
  plain: 'xl:grid-cols-[360px_1fr_360px] min-[1800px]:grid-cols-[420px_1fr_420px]',
}

function refreshFrames(): void {
  for (let index = 0; index < window.frames.length; index += 1) {
    window.frames[index]?.postMessage(REFRESH_MESSAGE, window.location.origin)
  }
}

function readLook(): PhoneLook {
  try {
    return window.localStorage.getItem(LOOK_STORAGE) === 'plain' ? 'plain' : 'framed'
  } catch {
    return 'framed'
  }
}

function usePhoneLook() {
  const [look, setLook] = useState<PhoneLook>(readLook)
  const choose = (next: PhoneLook) => {
    try {
      window.localStorage.setItem(LOOK_STORAGE, next)
    } catch {
      // Storage may be blocked; the choice then lasts for this page only.
    }
    setLook(next)
  }
  return { look, choose }
}

function LookSwitch({ look, choose }: { look: PhoneLook; choose: (look: PhoneLook) => void }) {
  const { t } = useI18n()
  return (
    <div aria-label={t('demo.view')} className="flex rounded-full bg-sunken" role="group">
      {(['framed', 'plain'] as const).map((item) => (
        <button
          aria-pressed={item === look}
          className={`min-h-11 rounded-full px-4 text-sm font-bold transition-colors duration-150 ${choiceClass(item === look)}`}
          key={item}
          onClick={() => choose(item)}
          type="button"
        >
          {t(item === 'framed' ? 'demo.framed' : 'demo.plain')}
        </button>
      ))}
    </div>
  )
}

function SceneChooser({ list, busy, onStart }: { list: SceneList; busy: boolean; onStart: (id: string) => void }) {
  const { t } = useI18n()
  const text = `scene.${list.active ?? ''}.text`
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div aria-label={t('demo.scene')} className="flex flex-wrap gap-2" role="group">
        {list.scenes.map((scene, index) => {
          const name = `scene.${scene.id}.name`
          const pressed = scene.id === list.active
          return (
            <button
              aria-disabled={busy || undefined}
              aria-pressed={pressed}
              className={`min-h-11 rounded-full px-5 font-bold transition-colors duration-150 ${
                pressed ? 'bg-text text-surface' : 'bg-surface hover:bg-line'
              }`}
              key={scene.id}
              onClick={() => onStart(scene.id)}
              type="button"
            >
              {index + 1}. {hasKey(name) ? t(name) : scene.id}
            </button>
          )
        })}
      </div>
      {hasKey(text) && <p className="text-muted">{t(text)}</p>}
    </div>
  )
}

/** Scene changes run one at a time; afterwards every frame asks the server at once. */
function useBoard(onDone: () => void) {
  const [notice, setNotice] = useNotice()
  const [busy, setBusy] = useState(false)
  const guard = useRef(false)
  const run = async (path: string) => {
    if (guard.current) return
    guard.current = true
    setBusy(true)
    setNotice('')
    try {
      await post<StageView>(path)
    } catch (failure) {
      setNotice(errorCode(failure))
    } finally {
      guard.current = false
      setBusy(false)
      onDone()
      refreshFrames()
    }
  }
  return { notice, busy, run }
}

export function DemoPage() {
  const { t } = useI18n()
  useTitle(t('demo.title'))
  const { look, choose } = usePhoneLook()
  const list = usePoll<SceneList>('/api/scenes', POLL_MS)
  const { notice, busy, run } = useBoard(list.refresh)
  useStaffOnly(notice || list.errorCode)

  const scene = list.data?.scenes.find((item) => item.id === list.data?.active) ?? null
  const caseId = list.data?.case_id ?? ''
  return (
    <div className={`flex min-h-dvh flex-col ${look === 'framed' ? 'xl:h-dvh xl:min-h-[700px]' : ''}`}>
      <TopBar>
        <a className={TOP_LINK} href="/console">
          {t('demo.open_console')}
        </a>
        <a className={TOP_LINK} href="/stage" rel="noopener" target="_blank">
          {t('demo.open_stage')}
        </a>
        <LookSwitch choose={choose} look={look} />
        <Button inactive={busy || !scene} onClick={() => scene && void run(`/api/scenes/${scene.id}/start`)} size="desk" variant="tonal">
          {t('demo.restart')}
        </Button>
        <Button inactive={busy} onClick={() => void run('/api/reset')} size="desk" variant="tonal">
          {t('demo.reset')}
        </Button>
      </TopBar>
      <Problem code={notice || list.errorCode} />
      <main className="flex min-h-0 flex-1 flex-col gap-2 p-2.5 sm:px-5">
        <h1 className="sr-only">{t('demo.title')}</h1>
        {list.data && <SceneChooser busy={busy} list={list.data} onStart={(id) => void run(`/api/scenes/${id}/start`)} />}
        <div className={`grid min-h-0 flex-1 gap-4 md:grid-cols-2 ${COLUMNS[look]}`}>
          <DemoPhone caseId={caseId} look={look} scene={scene} side="receiver" />
          <iframe
            className="order-last min-h-[700px] w-full border-0 bg-bg md:col-span-2 xl:order-none xl:col-span-1 xl:h-full xl:min-h-0"
            src="/stage?embed=1"
            title={t('stage.document')}
          />
          <DemoPhone caseId={caseId} look={look} scene={scene} side="sender" />
        </div>
        <BetaNote />
      </main>
    </div>
  )
}
