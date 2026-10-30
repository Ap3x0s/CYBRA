import { useCallback, useEffect, useState } from 'react'

/** Fetch once, with a manual reload. */
export function useApi(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })

  const reload = useCallback(() => {
    let alive = true
    setState((current) => ({ ...current, loading: true, error: null }))
    Promise.resolve()
      .then(loader)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState({ data: null, error, loading: false }))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => reload(), [reload])
  return { ...state, reload }
}

/** Poll while `active` is true. Used for live run progress. */
export function usePoll(loader, active, intervalMs = 1500, deps = []) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!active) return undefined
    let alive = true
    const tick = () =>
      Promise.resolve()
        .then(loader)
        .then((value) => alive && setData(value))
        .catch(() => {})
    tick()
    const timer = setInterval(tick, intervalMs)
    return () => {
      alive = false
      clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, intervalMs, ...deps])

  return data
}
