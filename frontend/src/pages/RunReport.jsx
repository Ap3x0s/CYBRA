import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, formatDate, pct } from '../components'
import { PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

/**
 * Отчёт для печати.
 *
 * Вёрстка повторяет серверный report.html: тот же титул, KPI-строка,
 * карточки моделей и полосы доли провалов. Дублирование намеренное — страница
 * в приложении рисуется React'ом и должна совпадать с файлом, который уходит
 * на печать, иначе менеджер и инженер видят разные отчёты.
 *
 * Цвета заданы здесь, а не в переменных темы: отчёт печатается на бумаге, где
 * экранный янтарь #E5A93C нечитаем. Используются приглушённые бумажные
 * значения.
 */

const INK = '#14141A'
const MUTED = '#8A8580'
const BODY = '#4A453E'
const EDGE = '#E6E1D8'
const ACCENT = '#B07E22'
const BAD = '#A8321E'
const GOOD = '#1F7A4D'

/**
 * Статусы полноты по-русски.
 *
 * COMPLETE/PARTIAL — термины из нашего словаря метрик, но в отчёте для
 * руководства английские слова читаются как сбой локализации. Исходное
 * значение остаётся в title: при наведении видно точный термин из
 * контракта, аудитор не теряет однозначность.
 */
const STATUS_LABELS = {
  COMPLETE: { label: 'полно', bg: '#E4F0E9', fg: GOOD },
  PARTIAL: { label: 'частично', bg: '#F6F1E6', fg: '#8A6216' },
  ERROR: { label: 'ошибка', bg: '#FAF0ED', fg: BAD },
  CANCELLED: { label: 'отменён', bg: '#FAF0ED', fg: BAD },
}

/** Чип полноты. Текст дублирует цвет — важно для чёрно-белой печати. */
function Chip({ status }) {
  const key = String(status || '').toUpperCase()
  const entry = STATUS_LABELS[key] || { label: status, bg: '#FAF0ED', fg: BAD }
  return (
    <span
      title={status}
      style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 3,
        background: entry.bg, color: entry.fg,
        fontSize: 9.5, fontWeight: 600, letterSpacing: '.04em',
        textTransform: 'uppercase', whiteSpace: 'nowrap',
      }}
    >
      {entry.label}
    </span>
  )
}

/**
 * Полоса доли провалов с числом справа.
 *
 * Полоска показывает пропорцию, но точное значение по ней не прочесть —
 * поэтому процент стоит рядом.
 *
 * При нуле полоса нулевой ширины исчезает и читается как «нет данных»,
 * поэтому рисуется серая точка-минимум.
 *
 * known=false означает «оценивать было нечего»: тогда прочерк, а не 0.0%.
 * Ноль наблюдений не равен измеренному нулю провалов.
 */
function Bar({ value, known = true }) {
  if (!known) {
    return <span style={{ color: MUTED, fontSize: 11 }}>—</span>
  }
  const share = Math.max(0, Math.min(1, Number(value) || 0))
  const width = share <= 0 ? 6 : Math.max(3, share * 100)
  const color = share <= 0 ? '#D8D2C8' : share >= 0.5 ? BAD : ACCENT
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 118 }}>
      <div style={{ flex: 1, minWidth: 60, height: 6, background: '#EDE8DF', borderRadius: 3 }}>
        <div style={{ width: `${width}%`, height: 6, background: color, borderRadius: 3 }} />
      </div>
      <span
        style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, color: INK,
          whiteSpace: 'nowrap', minWidth: 38, textAlign: 'right',
        }}
      >
        {(share * 100).toFixed(1)}%
      </span>
    </div>
  )
}

function Kpi({ label, value, sub, bad }) {
  return (
    <div style={{ flex: 1, background: '#fff', border: `1px solid ${EDGE}`, padding: '14px 15px 12px', borderRadius: 3 }}>
      <div style={{ fontSize: 9.5, letterSpacing: '.1em', textTransform: 'uppercase', color: MUTED, fontWeight: 600, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 25, fontWeight: 650, letterSpacing: '-.02em', lineHeight: 1, color: bad ? BAD : INK }}>
        {value}
      </div>
      <div style={{ fontSize: 10.5, color: MUTED, marginTop: 5 }}>{sub}</div>
    </div>
  )
}

const TH = {
  textAlign: 'left', padding: '7px 9px', fontSize: 9, letterSpacing: '.1em',
  textTransform: 'uppercase', color: MUTED, fontWeight: 700,
  borderBottom: `1.5px solid ${INK}`, whiteSpace: 'nowrap',
}
const TD = { padding: '8px 9px', borderBottom: '1px solid #EDE8DF', verticalAlign: 'middle' }
const TD_NUM = { ...TD, textAlign: 'right', fontFamily: 'var(--font-mono)' }
const H3 = {
  fontSize: 9.5, letterSpacing: '.12em', textTransform: 'uppercase',
  color: MUTED, fontWeight: 700, margin: '20px 0 9px',
}

export default function RunReport() {
  const { id } = useParams()
  const { t } = useI18n()
  const run = useApi(() => api.run(id), [id])

  if (run.loading) return <PageSkeleton variant="default" />
  if (run.error) return <ErrorBox error={run.error} />

  const data = run.data
  const steps = data.steps || []
  const models = [...new Set(steps.map((step) => step.model_label))]

  // Итоги по всему прогону — для KPI-строки.
  const grand = steps.reduce(
    (acc, step) => {
      const c = step.counts || {}
      acc.pass += c.PASS || 0
      acc.fail += c.FAIL || 0
      return acc
    },
    { pass: 0, fail: 0 },
  )
  const grandScored = grand.pass + grand.fail
  const grandShare = grandScored ? grand.fail / grandScored : 0

  return (
    // color обязателен: без него текст наследует светлый цвет тёмной темы
    // (rgb(242,242,240)) и на белой бумаге становится почти невидимым.
    <div style={{ background: '#FBFAF7', color: INK, minHeight: '100vh', margin: '-24px -28px', padding: '40px 32px' }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <div className="no-print" style={{ marginBottom: 24 }}>
          {/* btn-paper, а не btn ghost: ghost берёт цвета тёмной темы, и на
              бумажном фоне текст становился светло-серым, а при наведении —
              белым на белом. */}
          <Link to={`/runs/${id}`} className="btn btn-paper small">
            ← {t('К живому прогону')}
          </Link>
          <button className="btn btn-paper small" style={{ marginLeft: 8 }} onClick={() => window.print()}>
            {t('Печать / PDF')}
          </button>
        </div>

        {/* Шапка: слева идентичность документа, справа метка времени в
            серой плашке. Надзаголовок — чёрный и заметный (это то, что
            объясняет документ), название прогона — серым: это техническая
            метка, читатель её знает. */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 10.5, letterSpacing: '.14em', textTransform: 'uppercase', color: INK, fontWeight: 700, marginBottom: 10 }}>
              CYBRA · {t('отчёт о проверке безопасности LLM')}
            </div>
            <h1 style={{ fontSize: 27, lineHeight: 1.25, margin: '0 0 12px', letterSpacing: '-.02em', color: INK, fontWeight: 600 }}>
              {data.label}
            </h1>
            <div style={{ fontSize: 11.5, color: '#6B6660', fontFamily: 'var(--font-mono)' }}>
              {data.run_id} · {t('режим')} {data.engine_mode}
            </div>
          </div>
          <div
            style={{
              flex: '0 0 auto', background: '#EDE8DF', color: BODY,
              padding: '5px 11px', borderRadius: 3,
              fontFamily: 'var(--font-mono)', fontSize: 10.5, whiteSpace: 'nowrap',
            }}
          >
            {formatDate(data.finished_at || data.created_at)}
          </div>
        </div>
        <div style={{ height: 2, background: INK, margin: '22px 0 26px' }} />

        {data.engine_mode === 'mock' ? (
          <div style={{ borderLeft: `3px solid ${BAD}`, background: '#FAF0ED', padding: '11px 15px', margin: '12px 0', fontSize: 12, color: BODY }}>
            {t('Прогон выполнен в демонстрационном режиме (mock). Вердикты синтетические и не являются оценкой безопасности какой-либо модели.')}
          </div>
        ) : null}

        <div style={{ borderLeft: `3px solid ${ACCENT}`, background: '#F6F1E6', padding: '11px 15px', margin: '12px 0', fontSize: 12, color: BODY }}>
          {t('Единый процент безопасности не вычисляется: инструменты считают разные единицы (у garak — решение детектора, у остальных — отдельный кейс). Доля провалов относится к конкретному инструменту и настроенному подмножеству, а не ко всем возможным атакам.')}
        </div>

        <div className="rep-kpis" style={{ display: 'flex', gap: 10, margin: '0 0 28px' }}>
          <Kpi label={t('Моделей')} value={models.length} sub={t('в прогоне')} />
          <Kpi label={t('Шагов')} value={steps.length} sub={t('модель × инструмент')} />
          <Kpi label={t('Оценено')} value={grandScored} sub={t('кейсов с вердиктом')} />
          <Kpi
            label={t('Провалов')}
            value={pct(grandShare)}
            sub={`${grand.fail} ${t('из')} ${grandScored}`}
            bad={grandShare >= 0.3}
          />
        </div>

        {models.map((model) => {
          const modelSteps = steps.filter((step) => step.model_label === model)
          const totals = modelSteps.reduce(
            (acc, step) => {
              const counts = step.counts || {}
              acc.pass += counts.PASS || 0
              acc.fail += counts.FAIL || 0
              acc.bad += (counts.ERROR || 0) + (counts.UNSCORED || 0)
              return acc
            },
            { pass: 0, fail: 0, bad: 0 },
          )
          const scored = totals.pass + totals.fail
          const complete = modelSteps.every((step) => step.completeness === 'COMPLETE')
          const conclusion = totals.fail
            ? (complete ? 'FINDINGS' : 'FINDINGS_AND_INCOMPLETE')
            : (complete ? 'NO_FINDINGS_ON_TESTED_SET' : 'INCOMPLETE')

          return (
            <div
              key={model}
              className="rep-model"
              style={{
                background: '#fff', border: `1px solid ${EDGE}`, borderRadius: 3,
                padding: '22px 24px', margin: '0 0 18px',
                // pageBreakInside: 'avoid' здесь был дефектом: контейнер
                // занимает 7.5 страницы A4, и браузер переносил его целиком,
                // оставляя предыдущую страницу пустой. Разрыв разрешён,
                // защита перенесена на строки таблиц в styles.css.
              }}
            >
              <div
                className="rep-model-id"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 600, marginBottom: 4, color: INK }}
              >
                {model}
              </div>
              <div style={{ fontSize: 12, color: BODY, marginBottom: 18 }}>
                {t('Заключение:')} <b style={{ color: INK }}>{conclusion}</b>
                {scored ? ` · ${t('провалов')} ${totals.fail} ${t('из')} ${scored} ${t('оценённых')}` : ''}
                {totals.bad ? ` · ${t('не оценено')} ${totals.bad}` : ''}
              </div>

              <div style={H3}>{t('Итоги по инструментам')}</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    <th style={TH}>{t('Инструмент')}</th>
                    <th style={TH}>{t('Полнота')}</th>
                    <th style={{ ...TH, textAlign: 'right' }}>PASS</th>
                    <th style={{ ...TH, textAlign: 'right' }}>FAIL</th>
                    <th style={{ ...TH, textAlign: 'right' }}>{t('Ошибки')}</th>
                    <th style={{ ...TH, textAlign: 'right' }}>{t('Не оценено')}</th>
                    <th style={TH}>{t('Доля провалов')}</th>
                  </tr>
                </thead>
                <tbody>
                  {modelSteps.map((step) => {
                    const counts = step.counts || {}
                    return (
                      <tr key={step.id}>
                        <td style={{ ...TD, fontWeight: 500 }}>{step.tool}</td>
                        <td style={TD}><Chip status={step.completeness} /></td>
                        <td style={TD_NUM}>{counts.PASS || 0}</td>
                        <td style={TD_NUM}>{counts.FAIL || 0}</td>
                        <td style={TD_NUM}>{counts.ERROR || 0}</td>
                        <td style={TD_NUM}>{(counts.UNSCORED || 0) + (counts.SKIPPED || 0)}</td>
                        <td style={TD}>
                          <Bar
                            value={step.failed_check_rate}
                            known={Boolean((counts.PASS || 0) + (counts.FAIL || 0))}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              {modelSteps.some((step) => step.categories && Object.keys(step.categories).length) ? (
                <>
                  <div style={H3}>{t('Разбивка по категориям')}</div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr>
                        <th style={TH}>{t('Инструмент')}</th>
                        <th style={TH}>{t('Категория')}</th>
                        <th style={{ ...TH, textAlign: 'right' }}>PASS</th>
                        <th style={{ ...TH, textAlign: 'right' }}>FAIL</th>
                        <th style={{ ...TH, textAlign: 'right' }}>ERROR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modelSteps.flatMap((step) =>
                        Object.entries(step.categories || {}).map(([category, bucket]) => (
                          <tr key={step.id + category}>
                            <td style={{ ...TD, fontWeight: 500 }}>{step.tool}</td>
                            <td style={TD}>{category}</td>
                            <td style={TD_NUM}>{bucket.PASS || 0}</td>
                            <td style={TD_NUM}>{bucket.FAIL || 0}</td>
                            <td style={TD_NUM}>{bucket.ERROR || 0}</td>
                          </tr>
                        )),
                      )}
                    </tbody>
                  </table>
                </>
              ) : null}
            </div>
          )
        })}

        <div style={{ background: '#fff', border: `1px solid ${EDGE}`, borderRadius: 3, padding: '18px 22px', marginTop: 22, pageBreakInside: 'avoid' }}>
          <div style={{ ...H3, marginTop: 0 }}>{t('Ограничения методики')}</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11.5, color: BODY }}>
            <li style={{ marginBottom: 5 }}>{t('Значения провалов внутри инструмента не сравнимы между инструментами.')}</li>
            <li style={{ marginBottom: 5 }}>{t('COMPLETE относится к выбранному профилю, а не ко всем атакам инструмента.')}</li>
            <li style={{ marginBottom: 5 }}>{t('ERROR, UNSCORED и SKIPPED не считаются PASS.')}</li>
            <li style={{ marginBottom: 5 }}>{t('Результат судьи требует выборочной ручной проверки.')}</li>
            <li style={{ marginBottom: 5 }}>{t('Отчёт не покрывает ACL, RAG, браузер и реальные side effects приложения.')}</li>
          </ul>
        </div>

        <div style={{ marginTop: 26, paddingTop: 14, borderTop: `1px solid ${EDGE}`, fontSize: 10, color: MUTED }}>
          CYBRA · Security Console. {t('Отчёт относится к настроенному подмножеству атак и не является сертификатом безопасности.')}
        </div>
      </div>
    </div>
  )
}
