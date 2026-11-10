import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, StatusPill, formatDate, pct } from '../components'
import { PageSkeleton } from '../components/Skeletons'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

/** Print-oriented report. Deliberately light: it goes to management and paper. */
export default function RunReport() {
  const { id } = useParams()
  const { t } = useI18n()
  const run = useApi(() => api.run(id), [id])

  if (run.loading) return <PageSkeleton variant="default" />
  if (run.error) return <ErrorBox error={run.error} />

  const data = run.data
  const models = [...new Set((data.steps || []).map((step) => step.model_label))]

  return (
    <div className="report-page">
      <div className="no-print" style={{ marginBottom: 28 }}>
        <Link to={`/runs/${id}`} className="btn ghost small">
          ← {t('К живому прогону')}
        </Link>
        <button className="btn small" style={{ marginLeft: 8 }} onClick={() => window.print()}>
          {t("Печать / PDF")}
        </button>
      </div>

      <div className="meta">CYBRA · {t('отчёт о проверке безопасности LLM')}</div>
      <h1 style={{ marginTop: 6 }}>{data.label}</h1>
      <p style={{ color: '#6b6257', fontSize: 13, marginTop: 4 }}>
        {t("Прогон")} <span className="mono-sm">{data.run_id}</span> · {formatDate(data.finished_at || data.created_at)}
        {' · '}
        режим {data.engine_mode}
      </p>

      {data.engine_mode === 'mock' ? (
        <p className="note" style={{ marginTop: 20 }}>
          {t("Прогон выполнен в демонстрационном режиме (mock). Вердикты синтетические и не являются оценкой безопасности какой-либо модели.")}
        </p>
      ) : null}

      <p className="note" style={{ marginTop: 20 }}>
        {t("Единый процент безопасности не вычисляется: инструменты считают разные единицы (у garak — решение детектора, у остальных — отдельный кейс). Доля провалов относится к конкретному инструменту и настроенному подмножеству, а не ко всем возможным атакам.")}
      </p>

      {models.map((model) => {
        const steps = data.steps.filter((step) => step.model_label === model)
        const totals = steps.reduce(
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
        const complete = steps.every((step) => step.completeness === 'COMPLETE')
        const conclusion = totals.fail
          ? complete
            ? 'FINDINGS'
            : 'FINDINGS_AND_INCOMPLETE'
          : complete
            ? 'NO_FINDINGS_ON_TESTED_SET'
            : 'INCOMPLETE'

        return (
          <section key={model}>
            <h2>{model}</h2>
            <p style={{ margin: '0 0 10px', fontSize: 13 }}>
              {t("Заключение:")} <strong>{conclusion}</strong>
              {scored ? ` · провалов ${totals.fail} из ${scored} оценённых` : ''}
              {totals.bad ? ` · не оценено ${totals.bad}` : ''}
            </p>

            <table>
              <thead>
                <tr>
                  <th>{t("Инструмент")}</th>
                  <th>{t("Полнота")}</th>
                  <th className="num">PASS</th>
                  <th className="num">FAIL</th>
                  <th className="num">{t("Ошибки")}</th>
                  <th className="num">{t("Доля провалов")}</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((step) => {
                  const counts = step.counts || {}
                  return (
                    <tr key={step.id}>
                      <td>{step.tool}</td>
                      <td>
                        <StatusPill status={step.completeness} />
                      </td>
                      <td className="num">{counts.PASS || 0}</td>
                      <td className="num">{counts.FAIL || 0}</td>
                      <td className="num">
                        {(counts.ERROR || 0) + (counts.UNSCORED || 0) + (counts.SKIPPED || 0)}
                      </td>
                      <td className="num">
                        {step.failed_check_rate === null ? '—' : pct(step.failed_check_rate)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {steps.some((step) => step.categories && Object.keys(step.categories).length) ? (
              <>
                <h2 style={{ fontSize: 14 }}>{t("Разбивка по категориям")}</h2>
                <table>
                  <thead>
                    <tr>
                      <th>{t("Инструмент")}</th>
                      <th>{t("Категория")}</th>
                      <th className="num">PASS</th>
                      <th className="num">FAIL</th>
                      <th className="num">ERROR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {steps.flatMap((step) =>
                      Object.entries(step.categories || {}).map(([category, bucket]) => (
                        <tr key={step.id + category}>
                          <td>{step.tool}</td>
                          <td>{category}</td>
                          <td className="num">{bucket.PASS || 0}</td>
                          <td className="num">{bucket.FAIL || 0}</td>
                          <td className="num">{bucket.ERROR || 0}</td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </>
            ) : null}
          </section>
        )
      })}

      <h2>{t("Ограничения методики")}</h2>
      <ul style={{ fontSize: 12.5, color: '#4a443c', lineHeight: 1.7, paddingLeft: 20 }}>
        <li>{t("Значения провалов внутри инструмента не сравнимы между инструментами.")}</li>
        <li>COMPLETE относится к выбранному профилю, а не ко всем атакам инструмента.</li>
        <li>ERROR, UNSCORED и SKIPPED не считаются PASS.</li>
        <li>{t("Результат судьи требует выборочной ручной проверки.")}</li>
        <li>{t("Отчёт не покрывает ACL, RAG, браузер и реальные side effects приложения.")}</li>
      </ul>
    </div>
  )
}
