import { useI18n } from './i18n-context'
// Shared presentational pieces. Kept tiny on purpose: a component earns its
// place only if it appears on more than one screen.

export function Pill({ tone = 'idle', children }) {
  return (
    <span className={`pill ${tone}`}>
      <i />
      {children}
    </span>
  )
}

const STATUS_TONE = {
  COMPLETE: 'ok',
  COMPLETED: 'ok',
  RUNNING: 'info',
  PENDING: 'idle',
  PARTIAL: 'warn',
  ERROR: 'bad',
  CANCELLED: 'warn',
  FAIL: 'bad',
  PASS: 'ok',
  UNSCORED: 'warn',
  SKIPPED: 'idle',
}

const STATUS_LABEL = {
  COMPLETE: 'полно',
  PARTIAL: 'частично',
  ERROR: 'ошибка',
  CANCELLED: 'отменён',
  RUNNING: 'идёт',
  PENDING: 'в очереди',
  PASS: 'PASS',
  FAIL: 'FAIL',
  UNSCORED: 'UNSCORED',
  SKIPPED: 'SKIPPED',
}

export function StatusPill({ status }) {
  const tone = STATUS_TONE[status] || 'idle'
  const { t } = useI18n()
  const label = STATUS_LABEL[status]
  return <Pill tone={tone}>{label ? t(label) : status}</Pill>
}

/** A number with an explanation attached. Every metric in the UI uses this. */
export function MetricTile({ label, value, hint, tone, title }) {
  return (
    <div className={`metric-tile${tone ? ' is-' + tone : ''}`} title={title}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  )
}

/** Percentage bar whose colour carries meaning, not decoration. */
export function Meter({ value, max = 1, invert = false }) {
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0
  const pct = (ratio * 100).toFixed(1)
  const bad = invert ? ratio < 0.5 : ratio > 0.5
  const tone = ratio === 0 ? 'var(--muted-dim)' : bad ? 'var(--danger)' : 'var(--accent)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 110 }}>
      <div className="progress-track" style={{ flex: 1 }}>
        <div className="progress-fill" style={{ width: pct + '%', background: tone }} />
      </div>
      <span className="mono-sm" style={{ color: tone, minWidth: 44, textAlign: 'right' }}>
        {pct}%
      </span>
    </div>
  )
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function Loading({ label }) {
  const { t } = useI18n()
  return <div className="empty">{label ? t(label) : t('Загрузка…')}</div>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="banner bad">✕ {error.message || String(error)}</div>
}

export function Banner({ tone = '', children }) {
  return <div className={`banner ${tone}`}>{children}</div>
}

export function Field({ label, help, children }) {
  return (
    <div className="field">
      {label ? <label>{label}</label> : null}
      {children}
      {help ? <span className="help">{help}</span> : null}
    </div>
  )
}

export function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRelative(value, t = (s) => s) {
  if (!value) return '—'
  const date = new Date(value)
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 60) return t('только что')
  if (diff < 3600) return t('{n} мин назад', { n: Math.floor(diff / 60) })
  if (diff < 86400) return t('{n} ч назад', { n: Math.floor(diff / 3600) })
  return t('{n} дн назад', { n: Math.floor(diff / 86400) })
}

export function pct(value) {
  if (value === null || value === undefined) return '—'
  return (value * 100).toFixed(1) + '%'
}
