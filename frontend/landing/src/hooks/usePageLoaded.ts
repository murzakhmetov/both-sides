import { useEffect, useState } from 'react'

/** True after the load event. Videos wait for it: before it they would hold it back, in Safari for a long time. */
export function usePageLoaded(): boolean {
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    if (document.readyState === 'complete') {
      setLoaded(true)
      return undefined
    }
    const onLoad = () => setLoaded(true)
    window.addEventListener('load', onLoad)
    return () => window.removeEventListener('load', onLoad)
  }, [])
  return loaded
}
