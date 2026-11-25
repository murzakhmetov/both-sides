import { createContext, useCallback, useContext, useEffect, useId, useMemo, useState, type ReactNode, type RefObject } from 'react'
import { useInView } from './hooks/useInView'
import { usePageLoaded } from './hooks/usePageLoaded'
import type { SceneId } from './media'
import { ScrollTrigger } from './scroll'
import { START, claim, release, type Shown } from './stage'

interface SceneState extends Shown {
  /** Returns how to give the claim up. */
  readonly claimScene: (section: string, shown: Shown) => () => void
  /** The visitor stopped all moving pictures. */
  readonly paused: boolean
  readonly togglePaused: () => void
  /** The page has loaded: now videos may load too. */
  readonly loaded: boolean
}

const SceneContext = createContext<SceneState | null>(null)

/** Which background the page shows right now. */
export function SceneProvider({ children }: { children: ReactNode }) {
  const [stage, setStage] = useState(START)
  const [paused, setPaused] = useState(false)
  const loaded = usePageLoaded()

  const claimScene = useCallback((section: string, shown: Shown) => {
    setStage((old) => claim(old, section, shown))
    return () => setStage((old) => release(old, section))
  }, [])
  const togglePaused = useCallback(() => setPaused((old) => !old), [])

  const { scene, held } = stage.shown
  const state = useMemo(
    () => ({ scene, held, claimScene, paused, togglePaused, loaded }),
    [scene, held, claimScene, paused, togglePaused, loaded],
  )
  return <SceneContext value={state}>{children}</SceneContext>
}

export function useSceneState(): SceneState {
  const state = useContext(SceneContext)
  if (!state) throw new Error('useSceneState needs a SceneProvider')
  return state
}

/** Shows a background while a section is on screen. The order in which sections come and go does not matter. */
export function useScene(onScreen: boolean, scene: SceneId, held = false): void {
  const { claimScene } = useSceneState()
  const section = useId()
  useEffect(() => (onScreen ? claimScene(section, { scene, held }) : undefined), [onScreen, scene, held, claimScene, section])
}

/** Shows a background while its section crosses the middle of the window. */
export function useSceneOnScroll(ref: RefObject<HTMLElement | null>, scene: SceneId): void {
  useScene(useInView(ref), scene)
}

/**
 * For a tall section with a sticky screen inside: calls back with the part that
 * is on screen, 0 to parts - 1.
 */
export function useParts(ref: RefObject<HTMLElement | null>, parts: number, onPart: (part: number) => void): void {
  useEffect(() => {
    const trigger = ScrollTrigger.create({
      trigger: ref.current,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (self) => onPart(Math.min(parts - 1, Math.floor(self.progress * parts))),
    })
    return () => trigger.kill()
  }, [ref, parts, onPart])
}
