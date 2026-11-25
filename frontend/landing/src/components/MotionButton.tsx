import { useReducedMotion } from '../hooks/useMediaQuery'
import { useLang } from '../lang'
import { useSceneState } from '../scene'

/** Stops and starts all moving pictures. Not needed when the system already asks for less motion. */
export function MotionButton() {
  const { t } = useLang()
  const { paused, togglePaused } = useSceneState()
  if (useReducedMotion()) return null
  const label = t(paused ? 'motion.play' : 'motion.pause')
  return (
    <button
      aria-label={label}
      className="flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-[14px] border border-white/15 bg-ink/60 transition-colors hover:border-white/50"
      onClick={togglePaused}
      title={label}
      type="button"
    >
      <svg aria-hidden="true" className="h-4 w-4 fill-current" viewBox="0 0 16 16">
        {paused ? <path d="M4 2.5v11l9-5.5z" /> : <path d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z" />}
      </svg>
    </button>
  )
}
