import { useEffect, useRef } from 'react'
import type { Scene, Side } from '../api/types'
import { useFit } from '../hooks/useFit'
import { FILL_MESSAGE, type FillMessage } from '../hooks/usePhone'
import { useI18n } from '../i18n'
import { Button } from './ui'

export type PhoneLook = 'framed' | 'plain'

// A phone screen that shows the question and both buttons without scrolling, plus its frame.
const SCREEN = { width: 390, height: 724 }
const BORDER = 10
const DEVICE = { width: SCREEN.width + 2 * BORDER, height: SCREEN.height + 2 * BORDER }

const FRAMED =
  'absolute top-0 left-1/2 origin-top overflow-hidden rounded-[52px] border-[10px] border-device bg-hero'
const PLAIN = 'absolute inset-0 overflow-hidden rounded-card bg-surface'

function scriptOf(side: Side, scene: Scene | null): string {
  if (!scene) return ''
  return side === 'receiver' ? scene.receiver_script : scene.sender_script
}

interface DemoPhoneProps {
  readonly side: Side
  readonly look: PhoneLook
  readonly scene: Scene | null
  readonly caseId: string
}

/**
 * One phone of the demo page with its name and the button that types the scene's
 * answer. The frame element stays the same when the look changes, so nothing reloads.
 */
export function DemoPhone({ side, look, scene, caseId }: DemoPhoneProps) {
  const { t } = useI18n()
  const frame = useRef<HTMLIFrameElement>(null)
  const { container, scale } = useFit(DEVICE)
  const script = scriptOf(side, scene)
  const framed = look === 'framed'

  // A framed phone hides its scroll bar, like a real one. See index.css.
  const tellLook = () => {
    const page = frame.current?.contentDocument?.documentElement
    if (page) page.dataset['look'] = look
  }
  useEffect(tellLook)

  const fill = () => {
    const message: FillMessage = { type: FILL_MESSAGE, side, caseId, text: script }
    frame.current?.contentWindow?.postMessage(message, window.location.origin)
  }
  return (
    <section className="flex min-h-0 flex-col gap-2">
      <div className="flex min-h-11 items-center justify-between gap-3">
        <h2 className="text-lg font-bold">{t(`side.${side}`)}</h2>
        {script ? (
          <Button onClick={fill} size="small" title={t('demo.fill_hint', { text: script })} variant="outline">
            {t('demo.fill')}
          </Button>
        ) : (
          <p className="text-right text-sm leading-tight text-muted">{scene && t('demo.no_script.receiver')}</p>
        )}
      </div>
      <div
        className={`relative flex-1 overflow-hidden ${framed ? 'min-h-[520px] xl:min-h-0' : 'min-h-[820px]'}`}
        ref={container}
      >
        <div
          className={framed ? FRAMED : PLAIN}
          style={framed ? { width: DEVICE.width, height: DEVICE.height, transform: `translateX(-50%) scale(${scale})` } : {}}
        >
          <iframe
            className="block size-full border-0"
            onLoad={tellLook}
            ref={frame}
            src={`/${side}`}
            title={t(`phone.title.${side}`)}
          />
        </div>
      </div>
    </section>
  )
}
