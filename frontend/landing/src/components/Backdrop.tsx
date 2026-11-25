import { useEffect, useRef, useState } from 'react'
import { useLinger } from '../hooks/useLinger'
import { useReducedMotion, useTall } from '../hooks/useMediaQuery'
import { useParallax } from '../hooks/useParallax'
import { BACKDROPS, SCENES, isNear, posterUrl, videoSources, type Aspect, type SceneId } from '../media'
import { useSceneState } from '../scene'

/** A layer fades out for one second (backdrop.css). */
const FADE_MS = 1200

interface ClipProps {
  readonly id: SceneId
  readonly aspect: Aspect
  readonly active: boolean
  /** Waits on its poster. */
  readonly held: boolean
  /** Runs only when active and nobody stopped it. */
  readonly running: boolean
  /** The picture below shows more than the video now. */
  readonly hidden: boolean
}

/** One video. It stays invisible until its first frame is on screen, so the poster never flashes away. */
function ClipVideo({ id, aspect, active, held, running, hidden }: ClipProps) {
  const video = useRef<HTMLVideoElement>(null)
  const [visible, setVisible] = useState(false)
  const clip = SCENES[id].kind === 'clip'

  // A clip starts again from its poster every time the page comes back to it, and waits there while it is held.
  useEffect(() => {
    if (!active || !clip || !video.current) return
    video.current.currentTime = 0
    setVisible(false)
  }, [active, clip, held])

  useEffect(() => {
    const element = video.current
    if (!element) return
    if (!running) element.pause()
    // A browser may refuse to play before the first touch: then the poster stays.
    else element.play().catch(() => undefined)
  }, [running])

  return (
    <video
      className="media-fill media-video"
      data-running={visible && !hidden}
      disablePictureInPicture
      loop={!clip}
      muted
      onPlaying={() => setVisible(true)}
      playsInline
      preload="auto"
      ref={video}
      tabIndex={-1}
    >
      {videoSources(id, aspect).map((source) => (
        <source key={source.type} src={source.src} type={source.type} />
      ))}
    </video>
  )
}

interface LayerProps {
  readonly id: SceneId
  readonly aspect: Aspect
  readonly active: boolean
  readonly near: boolean
  /** Waits on the first frame. */
  readonly held?: boolean
  /** The page went on: whoever looks back sees how the clip ended. */
  readonly over?: boolean
}

/** One background: the poster early, the video only when the scene is on. */
export function MediaLayer({ id, aspect, active, near, held = false, over = false }: LayerProps) {
  const { paused, loaded } = useSceneState()
  const still = useReducedMotion()
  const seen = useLinger(active, FADE_MS)
  // Without motion a clip shows how it ends: that is the moment the words tell.
  const ended = (still || paused || over) && !held && SCENES[id].kind === 'clip'
  return (
    <div className="media-layer" data-active={active} data-scene={id}>
      {(seen || near) && <img alt="" className="media-fill" decoding="async" src={posterUrl(id, aspect, ended)} />}
      {seen && loaded && !still && SCENES[id].kind !== 'still' && (
        <ClipVideo
          active={active}
          aspect={aspect}
          held={held}
          hidden={over}
          id={id}
          key={aspect}
          running={active && !held && !paused}
        />
      )}
    </div>
  )
}

/** The fixed picture behind the whole page. One video runs at a time. */
export function Backdrop() {
  const { scene, held } = useSceneState()
  const aspect: Aspect = useTall() ? '9x16' : '16x9'
  const layers = useRef<HTMLDivElement>(null)
  useParallax(layers)
  return (
    <div aria-hidden="true" className="backdrop">
      <div className="absolute -inset-3" ref={layers}>
        {BACKDROPS.map((id) => (
          <MediaLayer
            active={scene === id}
            aspect={aspect}
            held={held && scene === id}
            id={id}
            key={id}
            near={isNear(id, scene)}
          />
        ))}
      </div>
      <div className="grain" />
    </div>
  )
}
