import { useCallback, useSyncExternalStore } from 'react'

/** Follows a media query without reading the window during the first render. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    [query],
  )
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches)
}

/** Phones and narrow windows get the 9:16 files. */
export function useTall(): boolean {
  return useMediaQuery('(max-aspect-ratio: 4/5)')
}

export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}
