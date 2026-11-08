import { useEffect, useRef, useState } from 'react'

/** Animated instrument background.
 *
 *  The reference the user pointed at (sdkhub.org) is not a static texture: it
 *  has a canvas streaming symbols, rotating copy, and a sound toggle. Copying
 *  that literally would be wrong for a security console, so the same grammar is
 *  applied to this domain: a slow drift of protocol tokens and hashes behind
 *  the content, like a packet capture rendered as weather.
 *
 *  Three constraints that matter more than the effect:
 *    - it renders behind everything and never intercepts clicks;
 *    - it stops drawing when the tab is hidden or the user reduced motion, and
 *      stops scheduling frames too (an idle rAF loop still costs battery);
 *    - it can be turned off, and turned back on.
 */
const GLYPHS = '0123456789ABCDEFabcdef:/._-<>=[]{}#@$%&*+'
const WORDS = [
  'eval', 'probe', 'jailbreak', 'detector', 'payload', 'verdict', 'PASS', 'FAIL',
  'inject', 'canary', 'judge', 'trace', 'sha256', 'endpoint', 'token', 'prompt',
]

export default function AnimatedBackdrop() {
  const canvasRef = useRef(null)
  const [enabled, setEnabled] = useState(true)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx = canvas.getContext('2d')
    if (!ctx) return undefined

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')
    let width = 0
    let height = 0
    let raf = 0
    let last = 0
    let columns = []
    let paused = false

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      // One stream per ~46px column, each with its own speed, so the field
      // never reads as a single scrolling block.
      const count = Math.ceil(width / 46)
      columns = Array.from({ length: count }, (_, index) => ({
        x: index * 46 + 8,
        y: Math.random() * height,
        speed: 8 + Math.random() * 16,
        chars: Array.from({ length: 6 + Math.floor(Math.random() * 10) }, () =>
          GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
        ),
        // One column in five carries a word instead of noise, so the texture
        // reads as log traffic rather than a screensaver.
        word: index % 5 === 2 ? WORDS[Math.floor(Math.random() * WORDS.length)] : null,
      }))
    }

    function effectivePause() {
      return paused || document.hidden || reduce.matches
    }

    function schedule() {
      cancelAnimationFrame(raf)
      raf = 0
      if (!effectivePause()) raf = requestAnimationFrame(frame)
    }

    function frame(now) {
      if (effectivePause()) {
        raf = 0
        return
      }
      raf = requestAnimationFrame(frame)
      // 30fps cap: this is ambient texture, not an animation showcase.
      if (now - last < 33) return
      last = now

      ctx.clearRect(0, 0, width, height)
      ctx.font = '11px ui-monospace, "JetBrains Mono", monospace'
      ctx.textAlign = 'left'

      for (const column of columns) {
        column.y += column.speed * 0.033
        if (column.y - column.chars.length * 15 > height) {
          column.y = -20
          column.chars = column.chars.map(
            () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
          )
        }

        column.chars.forEach((glyph, row) => {
          // The head of the stream is brightest and fades upstream.
          const alpha = Math.max(0.03, 0.30 - row * 0.022)
          ctx.fillStyle = `rgba(226, 163, 63, ${alpha})`
          ctx.fillText(glyph, column.x, column.y - row * 15)
        })

        if (column.word) {
          ctx.fillStyle = 'rgba(106, 168, 216, 0.16)'
          ctx.fillText(column.word, column.x, column.y + 18)
        }
      }
    }

    resize()
    window.addEventListener('resize', resize)

    function onVisibility() {
      last = 0
      schedule()
    }
    function onReduceChange() {
      schedule()
    }
    document.addEventListener('visibilitychange', onVisibility)
    reduce.addEventListener?.('change', onReduceChange)

    // Exposed so the toggle can start and stop the loop, not just hide it.
    canvas.__setPaused = (value) => {
      paused = value
      if (value) {
        cancelAnimationFrame(raf)
        raf = 0
        ctx.clearRect(0, 0, width, height)
      } else {
        last = 0
        schedule()
      }
    }

    schedule()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
      reduce.removeEventListener?.('change', onReduceChange)
    }
  }, [])

  useEffect(() => {
    canvasRef.current?.__setPaused?.(!enabled)
  }, [enabled])

  return (
    <div className="backdrop" aria-hidden="true">
      <canvas ref={canvasRef} className="backdrop-canvas" />
      <button
        className="backdrop-toggle"
        onClick={() => setEnabled((value) => !value)}
        title={enabled ? 'Остановить фоновую анимацию' : 'Включить фоновую анимацию'}
      >
        {enabled ? 'остановить фон' : 'включить фон'}
      </button>
    </div>
  )
}
