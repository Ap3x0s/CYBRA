import { useMemo, useState } from 'react'
import { api } from '../api'
import { ErrorBox, Meter, Pill, pct } from '../components'
import { BlockSkeleton, PageSkeleton } from '../components/Skeletons'
import Select from '../components/Select'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

/** Charts are hand-drawn SVG: no chart dependency, and the semantics stay ours. */

function shortTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 16)
  return date.toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

/* Палитра для линий. Янтарь — основной акцент, остальные подобраны так, чтобы
   различаться и на тёмном фоне, и в оттенках серого (печать отчёта). */
const SERIES_COLORS = [
  'var(--accent)',
  '#6AA8D8',
  '#3ECF8E',
  '#B98BE0',
  '#E6835B',
  '#8FA6B8',
]

/**
 * График динамики: одна линия на модель.
 *
 * Раньше все точки шли одной ломаной, хотя принадлежали разным моделям:
 * series() сортирует по id прогона и не группирует. Получался ряд, где
 * значения прыгали 0% → 64% → 0% — это был не тренд одной модели, а
 * переключение между qwen, gpt-4o и deepseek.
 *
 * Группировка — по паре «модель × инструмент». Только по модели нельзя:
 * в одном прогоне у модели несколько инструментов с разными значениями
 * (run#1 gpt-4o-demo: harmbench 0.375, jailbreakbench 0.625), и точки на
 * одном X складывались в вертикальную иглу — это не тренд, а разные метрики.
 * Сравнивать корректно внутри одного инструмента, поэтому линия — это
 * конкретная модель на конкретном инструменте.
 *
 * Ось X — порядковый номер прогона (общий для всех линий), поэтому точки
 * сопоставимы по времени между линиями.
 */
/**
 * Короткое имя модели для узких мест (бокс, легенда).
 *
 * В данных модель хранится с префиксом провайдера:
 * "deepseek/deepseek-v4.1-flash". В боксе шириной 208 px это занимает всю
 * строку. Убираем префикс только если после слеша осталось осмысленное имя,
 * иначе оставляем как есть — иначе "openai/gpt-4o-demo" превратится в
 * непонятное "gpt-4o-demo", а "qwen-demo" без префикса вообще не
 * встретится.
 */
function shortModel(model) {
  if (!model) return '—'
  const slash = model.lastIndexOf('/')
  if (slash > 0 && slash < model.length - 1) return model.slice(slash + 1)
  return model
}

function LineChart({ series, definition, width = 760, height = 240 }) {
  // LineChart — отдельный компонент, поэтому хук нужен свой: он не наследует
  // t() из Metrics, и без этой строки страница падала с "t is not defined".
  const { t } = useI18n()
  // Наведение подсвечивает один ряд, клик — фильтрует. Пустой selected
  // означает «показаны все»: так пользователь видит полную картину, пока сам
  // не решил сузить.
  const [hovered, setHovered] = useState(null)
  // Точка под курсором — для направляющей-уголка и мини-бокса. Нужны обе
  // координаты для линий, а также модель, инструмент и значение для подписи.
  const [hoveredPoint, setHoveredPoint] = useState(null)
  const [selected, setSelected] = useState(() => new Set())
  if (!series.length) return <div className="empty">{t("Нет точек для графика.")}</div>

  // Группируем по паре «модель × инструмент»: только по модели нельзя,
  // потому что в одном прогоне у модели бывает несколько инструментов с
  // разными значениями, и точки на одном X образуют вертикальную иглу.
  const groups = useMemo(() => {
    const map = new Map()
    for (const point of series) {
      const key = `${point.model || '—'} · ${point.tool || '—'}`
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(point)
    }
    return [...map.entries()]
  }, [series])

  /* Видимость ряда.
     Приоритет: наведение важнее выбора — пользователь может вести курсор по
     легенде, не сбрасывая фильтр. Приглушённые линии остаются на месте (не
     исчезают), чтобы сохранялась опора для сравнения: видно, что ряд есть и
     какой у него уровень. Полностью скрываются только те, что отфильтрованы
     кликом. */
  const hasSelection = selected.size > 0
  const isDimmed = (key) => {
    if (hovered) return hovered !== key
    if (hasSelection) return !selected.has(key)
    return false
  }
  // Скрываем только при активном фильтре и без наведения. Наведение
  // временно «показывает» ряд, чтобы его можно было рассмотреть перед
  // выбором, но после клика подсветка снимается — иначе выбранный ряд
  // выглядел бы скрытым.
  const isHidden = (key) => hasSelection && !selected.has(key) && hovered !== key

  function toggleSelected(key) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    // Снимаем наведение: после клика состояние определяется только фильтром,
    // иначе курсор, оставшийся на пункте, «возвращал» бы скрытые ряды.
    setHovered(null)
  }

  // Общая ось X: порядковый номер уникального прогона.
  const runOrder = useMemo(() => {
    const seen = []
    const index = new Map()
    for (const point of series) {
      if (!index.has(point.run_pk)) {
        index.set(point.run_pk, seen.length)
        seen.push(point)
      }
    }
    return { index, count: seen.length, points: seen }
  }, [series])

  // Верх увеличен: над осью теперь стоит название метрики.
  const padding = { top: 26, right: 16, bottom: 34, left: 42 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom
  // Шкала всегда 0-100 %, а не «максимум данных». Метрики в каталоге —
  // доли, и при авто-масштабе значение 75 % упиралось в верх, читаясь как
  // предел. Фиксированная шкала честнее: половина высоты всегда половина.
  const min = 0
  const max = 1

  const xAt = (runPk) => {
    const slot = runOrder.index.get(runPk) ?? 0
    if (runOrder.count <= 1) return padding.left + innerW / 2
    return padding.left + (slot / (runOrder.count - 1)) * innerW
  }
  const y = (value) =>
    padding.top + innerH - ((value - min) / (max - min || 1)) * innerH

  // Подписи оси X: первый, последний и, если есть место, середина.
  const ticks = runOrder.count <= 1
    ? [runOrder.points[0]]
    : runOrder.count <= 4
      ? runOrder.points
      : [runOrder.points[0],
         runOrder.points[Math.floor((runOrder.count - 1) / 2)],
         runOrder.points[runOrder.count - 1]]

  return (
    // position:relative — якорь для плашки, которая позиционируется
    // абсолютно уже в пикселях экрана, а не в единицах viewBox.
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto' }}
        role="img"
        onMouseMove={(event) => {
          // Координаты курсора приводим к системе viewBox: SVG растянут по
          // ширине карточки, а расчёты ведутся в исходных единицах.
          const box = event.currentTarget.getBoundingClientRect()
          if (!box.width) return
          const localX = ((event.clientX - box.left) / box.width) * width
          const localY = ((event.clientY - box.top) / box.height) * height
          if (localX < padding.left || localX > width - padding.right) {
            setHoveredPoint(null)
            return
          }
          // Ближайший прогон по горизонтали — попадать в маркер не нужно.
          let nearest = null
          let bestDist = Infinity
          for (const p of runOrder.points) {
            const dist = Math.abs(xAt(p.run_pk) - localX)
            if (dist < bestDist) { bestDist = dist; nearest = p }
          }
          if (!nearest) { setHoveredPoint(null); return }
          // Ряд выбираем по близости к курсору по вертикали: раньше брался
          // самый высокий, и уголок «прилипал» к пику, даже когда мышь вела
          // по нижней линии. Подсвеченный в легенде ряд имеет приоритет.
          const candidates = groups
            .filter(([key]) => !isHidden(key))
            .flatMap(([, pts]) => pts
              .filter((pt) => pt.run_pk === nearest.run_pk)
              .map((pt) => ({ pt, key: `${pt.model || '—'} · ${pt.tool || '—'}` })))
          if (!candidates.length) { setHoveredPoint(null); return }
          const preferred = hovered
            ? candidates.find((c) => c.key === hovered)
            : null
          const chosen = preferred
            ? preferred
            : candidates.reduce((a, b) => (
                Math.abs(y(b.pt.value) - localY) < Math.abs(y(a.pt.value) - localY)
                  ? b : a
              ))
          const pick = chosen.pt
          setHoveredPoint({
            runPk: pick.run_pk,
            value: pick.value,
            model: pick.model,
            tool: pick.tool,
            at: pick.at,
            color: SERIES_COLORS[groups.findIndex(([k]) => k === chosen.key)
              % SERIES_COLORS.length],
          })
        }}
        onMouseLeave={() => setHoveredPoint(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((fraction, i) => {
          const value = min + (max - min) * fraction
          return (
            <g key={fraction}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={y(value)}
                y2={y(value)}
                stroke="var(--edge-soft)"
                strokeWidth="1"
                // Базовая линия (0 %) чуть заметнее остальных: она задаёт
                // отсчёт и без неё сетка выглядит «плавающей».
                opacity={i === 0 ? 0.9 : 0.45}
              />
              <text x={padding.left - 8} y={y(value) + 3.5}
                    fill="var(--muted-dim)" fontSize="10"
                    fontFamily="var(--font-mono)" textAnchor="end">
                {(value * 100).toFixed(0)}
              </text>
            </g>
          )
        })}
        {/* Единица измерения вынесена в строку подписи под графиком: над
            осью она налезала на верхнюю отметку и читалась как артефакт. */}

        {/* Название метрики — внутри области графика, у левого верхнего
            края. Так подпись относится к вертикальной оси, но не висит
            отдельной полосой под графиком. */}
        {definition ? (
          <text
            x={4}
            y={padding.top - 9}
            fill="var(--muted-dim)"
            fontSize="9"
            fontFamily="var(--font-body)"
            letterSpacing="0.02em"
          >
            {t(definition.label)}
          </text>
        ) : null}

        {/* Направляющая-уголок от точки: вниз до дат и влево до значений.
            Выше и правее точки линий нет — смотреть там нечего, а лишние
            штрихи мешают читать плотный график. Так за один взгляд видно и
            дату прогона, и величину. */}
        {hoveredPoint ? (
          <g pointerEvents="none" opacity="0.28">
            <line
              x1={xAt(hoveredPoint.runPk)}
              x2={xAt(hoveredPoint.runPk)}
              y1={y(hoveredPoint.value)}
              y2={padding.top + innerH}
              stroke="var(--text)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <line
              x1={padding.left}
              x2={xAt(hoveredPoint.runPk)}
              y1={y(hoveredPoint.value)}
              y2={y(hoveredPoint.value)}
              stroke="var(--text)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
          </g>
        ) : null}

        {groups.map(([key, points], groupIndex) => {
          if (isHidden(key)) return null
          const color = SERIES_COLORS[groupIndex % SERIES_COLORS.length]
          const dim = isDimmed(key)
          const active = hovered === key || (hasSelection && selected.has(key))
          const sorted = [...points].sort(
            (a, b) => (runOrder.index.get(a.run_pk) ?? 0) - (runOrder.index.get(b.run_pk) ?? 0),
          )
          const d = sorted
            .map((point, i) => `${i ? 'L' : 'M'}${xAt(point.run_pk)},${y(point.value)}`)
            .join(' ')
          return (
            <g
              key={key}
              style={{ cursor: 'pointer', transition: 'opacity 160ms ease' }}
              opacity={dim ? 0.14 : 1}
              onMouseEnter={() => setHovered(key)}
              onMouseLeave={() => { setHovered(null); setHoveredPoint(null) }}
              onClick={() => toggleSelected(key)}
            >
              {/* При наведении линия становится чуть толще и ярче: этого
                  достаточно, чтобы выделить её среди соседних, не меняя
                  палитру. */}
              {/* Заливка под активной линией: даёт объём и отделяет
                  выбранный ряд от соседних, не меняя палитру. */}
              {sorted.length > 1 && active ? (
                <path
                  d={`${d} L${xAt(sorted[sorted.length - 1].run_pk)},${y(min)} `
                     + `L${xAt(sorted[0].run_pk)},${y(min)} Z`}
                  fill={color}
                  opacity="0.07"
                />
              ) : null}
              {sorted.length > 1 ? (
                <path d={d} fill="none" stroke={color}
                      strokeWidth={active ? 3.2 : 2.2}
                      strokeLinejoin="round" strokeLinecap="round"
                      opacity={active ? 1 : 0.92} />
              ) : null}
              {sorted.map((point, i) => (
                <g key={point.run_pk + '-' + i}>
                  <circle cx={xAt(point.run_pk)} cy={y(point.value)}
                          r={active ? 4.05 : 3.15}
                          fill={color} stroke="var(--ink-800)" strokeWidth="1.5" />
                </g>
              ))}
            </g>
          )
        })}

        {ticks.map((point, i) => {
          const anchor = i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'
          const xPos = xAt(point.run_pk)
          return (
            <text key={'tick-' + point.run_pk} x={xPos} y={height - 16}
                  fill="var(--muted-dim)" fontSize="10" textAnchor={anchor}>
              {shortTime(point.at)}
            </text>
          )
        })}

        {/* Подпись горизонтальной оси — вплотную под последней датой,
            выровнена по её правому краю. Так она стоит на краю самой оси, а
            не в отдельной полосе под графиком. */}
        <text
          x={width - padding.right}
          y={height - 4}
          fill="var(--muted-dim)"
          fontSize="8.5"
          fontFamily="var(--font-body)"
          letterSpacing="0.02em"
          textAnchor="end"
          opacity="0.8"
        >
          {t('дата прогона')}
        </text>
      </svg>

      {/* Плашка живёт вне SVG: внутри foreignObject её размеры умножались на
          коэффициент растяжения viewBox, и заданные 132x44 превращались в
          235x86 на экране. Здесь px — это px. */}
      {hoveredPoint ? (
        <div
          style={{
            position: 'absolute',
            // Позиция в процентах от геометрии viewBox: так она остаётся
            // верной при любой ширине карточки.
            left: `${(xAt(hoveredPoint.runPk) / width) * 100}%`,
            top: `${(y(hoveredPoint.value) / height) * 100}%`,
            transform: (xAt(hoveredPoint.runPk) / width) > 0.72
              ? 'translate(-100%, -50%) translateX(-10px)'
              : 'translate(0, -50%) translateX(10px)',
            pointerEvents: 'none',
            zIndex: 3,
          }}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 4.3,
              padding: '7px 11px',
              borderRadius: 6,
              background: 'rgba(20, 20, 23, 0.97)',
              border: '1px solid var(--edge)',
              boxShadow: '0 5px 16px rgba(0, 0, 0, 0.5)',
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{
                width: 10, height: 10, borderRadius: '50%',
                background: hoveredPoint.color, flex: '0 0 auto',
              }} />
              <span style={{ fontSize: 13.9, color: 'var(--text)' }}>
                {shortModel(hoveredPoint.model)}
              </span>
            </div>
            <div style={{
              display: 'flex', alignItems: 'baseline',
              justifyContent: 'space-between', gap: 10,
            }}>
              <span style={{
                fontSize: 11.8, color: 'var(--muted-dim)',
                fontFamily: 'var(--font-mono)',
              }}>
                {hoveredPoint.tool}
              </span>
              <span style={{
                fontSize: 17,
                fontWeight: 600,
                color: 'var(--accent)',
                // Начертание заголовков, а не моноширинное: одно число не
                // нужно выравнивать по колонке, а body-шрифт выглядит
                // собраннее. Табличные цифры не дают числу дёргаться.
                fontFamily: 'var(--font-body)',
                fontVariantNumeric: 'tabular-nums',
                letterSpacing: '-0.02em',
              }}>
                {pct(hoveredPoint.value)}
              </span>
            </div>
            <div style={{ fontSize: 11.8, color: 'var(--muted-dim)' }}>
              {shortTime(hoveredPoint.at)}
            </div>
          </div>
        </div>
      ) : null}

      {/* Легенда — это фильтр, а не подпись: наведение подсвечивает ряд,
          клик оставляет только его (можно несколько). Подписи сохранены,
          потому что цвет не должен быть единственным носителем смысла.
          Отступ сверху меньше, чем у блока метрики: легенда относится к
          графикам, а строка выше — описание данных. Группировка отступом
          показывает, что это разные вещи. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2, marginBottom: -2 }}>
        {groups.map(([key], groupIndex) => {
          const [model, tool] = key.split(' · ')
          const color = SERIES_COLORS[groupIndex % SERIES_COLORS.length]
          const isSelected = selected.has(key)
          const isHovered = hovered === key
          const off = hasSelection && !isSelected
          return (
            <button
              key={key}
              type="button"
              className="chart-legend-item"
              aria-pressed={isSelected}
              title={isSelected ? t('Убрать из фильтра') : t('Показать только этот ряд')}
              onMouseEnter={() => setHovered(key)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(key)}
              onBlur={() => setHovered(null)}
              onClick={() => toggleSelected(key)}
              style={{
                // Янтарная подложка у выбранного — та же логика, что у чипов
                // навигации: акцент показывает активное состояние.
                background: isSelected
                  ? 'rgba(229, 169, 60, 0.13)'
                  : isHovered
                    ? 'rgba(255, 255, 255, 0.06)'
                    : 'transparent',
                borderColor: isSelected
                  ? 'rgba(229, 169, 60, 0.5)'
                  : isHovered
                    ? 'var(--edge)'
                    : 'transparent',
                opacity: off ? 0.45 : 1,
              }}
            >
              <span style={{
                width: 9, height: 9, borderRadius: 2,
                background: color,
                flex: '0 0 auto',
                // Точка у выбранного получает свечение — второй признак
                // состояния помимо рамки.
                boxShadow: isSelected ? `0 0 0 3px ${color}22` : 'none',
              }} />
              <span className="muted">{model}</span>
              <span className="dim" style={{ fontSize: 10.5 }}>{tool}</span>
            </button>
          )
        })}
        {hasSelection ? (
          <button
            type="button"
            className="chart-legend-item chart-legend-reset"
            onClick={() => setSelected(new Set())}
            title={t('Показать все ряды')}
          >
            {t('Сбросить')}
          </button>
        ) : null}
      </div>
    </div>
  )
}

export default function Metrics() {
  const { t } = useI18n()
  const catalog = useApi(() => api.metricsCatalog())
  const runs = useApi(() => api.runs(60))
  const [metric, setMetric] = useState('failed_check_rate')
  const [tool, setTool] = useState('')
  const [model, setModel] = useState('')

  const series = useApi(
    () => api.metricsSeries({ metric, tool: tool || undefined, model: model || undefined, limit: 60 }),
    [metric, tool, model],
  )

  const models = useMemo(() => {
    const set = new Set()
    for (const run of runs.data || []) {
      for (const step of run.steps || []) set.add(step.model_label)
    }
    return [...set]
  }, [runs.data])

  const tools = useMemo(() => {
    const set = new Set()
    for (const run of runs.data || []) {
      for (const step of run.steps || []) set.add(step.tool)
    }
    return [...set]
  }, [runs.data])

  const definition = (catalog.data || []).find((item) => item.id === metric)

  /** Latest value per model, for the comparison table. */
  const latest = useMemo(() => {
    const map = new Map()
    for (const point of series.data || []) {
      map.set(point.model, point)
    }
    return [...map.entries()]
  }, [series.data])

  if (catalog.loading) return <PageSkeleton variant="metrics" />
  if (catalog.error) return <ErrorBox error={catalog.error} />

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>{t("Метрики")}</h1>
          <p>
            {t("Каждое значение снабжено расшифровкой. Сравнивать инструменты между собой по одной шкале нельзя — выбирайте один инструмент и одну метрику.")}
          </p>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ marginBottom: 0 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("Метрика")}</label>
            <Select
              value={metric}
              onChange={setMetric}
              options={(catalog.data || []).map((item) => ({
                value: item.id,
                label: item.label,
              }))}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("Инструмент")}</label>
            <Select
              value={tool}
              onChange={setTool}
              options={[{ value: '', label: t('все') },
                ...tools.map((name) => ({ value: name, label: name }))]}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>{t("Модель")}</label>
            <Select
              value={model}
              onChange={setModel}
              options={[{ value: '', label: t('все') },
                ...models.map((name) => ({ value: name, label: name }))]}
            />
          </div>
        </div>

        {definition ? (
          <div className="banner" style={{ marginTop: 16, marginBottom: 0, display: 'block' }}>
            <div style={{ marginBottom: 4 }}>
              <strong>{t(definition.label)}</strong>{' '}
              <span className="mono-sm dim">{t(definition.formula)}</span>
            </div>
            <div>{t(definition.description)}</div>
            <div style={{ color: 'var(--warn)', marginTop: 6 }}>⚠ {t(definition.caveat)}</div>
          </div>
        ) : null}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Динамика")}</h2>
        </div>
        {series.loading ? <BlockSkeleton rows={5} height={220} /> : <LineChart series={series.data || []} definition={definition} />}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Последние значения по моделям")}</h2>
        </div>
        {latest.length === 0 ? (
          <div className="empty">{t("Нет данных: выполните хотя бы один прогон.")}</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t("Модель")}</th>
                <th>{t("Инструмент")}</th>
                <th>{t("Значение")}</th>
                <th>{t("Полнота")}</th>
                <th>{t("Прогон")}</th>
              </tr>
            </thead>
            <tbody>
              {latest.map(([name, point]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td className="muted">{point.tool}</td>
                  <td>
                    <Meter value={point.value} />
                  </td>
                  <td>
                    <Pill tone={point.completeness === 'COMPLETE' ? 'ok' : 'warn'}>
                      {point.completeness}
                    </Pill>
                  </td>
                  <td className="dim mono-sm">{point.run_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("Словарь метрик")}</h2>
        </div>
        <table className="data">
          <thead>
            <tr>
              <th>{t("Метрика")}</th>
              <th>{t("Формула")}</th>
              <th>{t("Ограничение")}</th>
            </tr>
          </thead>
          <tbody>
            {(catalog.data || []).map((item) => (
              <tr key={item.id}>
                <td style={{ whiteSpace: 'nowrap' }}>{t(item.label)}</td>
                <td className="mono-sm dim">{t(item.formula)}</td>
                <td className="muted" style={{ fontSize: 12 }}>
                  {t(item.caveat)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
