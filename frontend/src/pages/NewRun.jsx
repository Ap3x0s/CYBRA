import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Banner, ErrorBox, Field, Loading } from '../components'
import { useApi } from '../hooks'

const TOOLS = [
  { id: 'harmbench', label: 'HarmBench', note: 'вредоносные behaviors, 3 обёртки' },
  { id: 'jailbreakbench', label: 'JailbreakBench', note: 'harmful + benign, отказы' },
  { id: 'bipia', label: 'BIPIA', note: 'косвенные инъекции в email/table' },
  { id: 'security-regression', label: 'Security Regression', note: 'injection, PII, утечки' },
  { id: 'promptfoo', label: 'Promptfoo', note: 'eval + корпоративные тесты' },
  { id: 'garak', label: 'garak', note: 'нативный сканер, probes/detectors' },
  { id: 'pyrit', label: 'PyRIT', note: 'многоходовые диалоги' },
  { id: 'agentdojo', label: 'AgentDojo', note: 'агентные инъекции и goal checks' },
]

const STEPS = ['Цель', 'Инструменты', 'Параметры', 'Подтверждение']

export default function NewRun() {
  const navigate = useNavigate()
  const targets = useApi(() => api.targets())
  const caps = useApi(() => api.capabilities())
  const datasets = useApi(() => api.datasets())

  const [step, setStep] = useState(0)
  const [label, setLabel] = useState('')
  const [selectedTargets, setSelectedTargets] = useState([])
  const [judgeId, setJudgeId] = useState(null)
  const [tools, setTools] = useState(['harmbench', 'jailbreakbench', 'security-regression'])
  const [versionIds, setVersionIds] = useState([])
  const [engineMode, setEngineMode] = useState('mock')
  const [limit, setLimit] = useState(10)
  const [seed, setSeed] = useState(42)
  const [maxRequests, setMaxRequests] = useState(1000)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const availability = useMemo(() => {
    const map = {}
    for (const item of caps.data || []) map[item.tool] = item
    return map
  }, [caps.data])

  if (targets.loading || datasets.loading) return <Loading />

  const targetList = targets.data || []
  const versionList = datasets.data || []
  const missingTools = tools.filter((tool) => availability[tool] && !availability[tool].available)

  function toggle(list, value, setter) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value])
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const run = await api.createRun({
        label: label || `Прогон ${new Date().toLocaleString('ru-RU')}`,
        target_ids: selectedTargets,
        judge_target_id: judgeId || selectedTargets[0],
        tools,
        dataset_version_ids: versionIds,
        engine_mode: engineMode,
        limit: Number(limit),
        seed: Number(seed),
        max_requests: Number(maxRequests),
      })
      navigate(`/runs/${run.id}`)
    } catch (problem) {
      setError(problem)
      setBusy(false)
    }
  }

  const canNext = [
    selectedTargets.length > 0,
    tools.length > 0,
    true,
    !busy,
  ][step]

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Новый прогон</h1>
          <p>Выберите модели, инструменты и профиль. Действия не требуют знания CLI-флагов.</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr', alignItems: 'start' }}>
        <div className="card">
          <div style={{ display: 'flex', gap: 6, marginBottom: 22, flexWrap: 'wrap' }}>
            {STEPS.map((name, index) => (
              <div
                key={name}
                style={{
                  padding: '5px 12px',
                  borderRadius: 999,
                  fontSize: 12,
                  border: '1px solid var(--edge)',
                  background: index === step ? 'var(--accent-dim)' : 'transparent',
                  color: index === step ? 'var(--accent)' : index < step ? 'var(--text)' : 'var(--muted-dim)',
                }}
              >
                {index + 1}. {name}
              </div>
            ))}
          </div>

          <ErrorBox error={error} />

          {step === 0 ? (
            <>
              <Field label="Название прогона" help="Попадёт в историю и отчёт.">
                <input
                  className="input"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  placeholder="Например: квартальная проверка пула"
                />
              </Field>

              <Field label="Модели для проверки">
                {targetList.length === 0 ? (
                  <Banner tone="warn">
                    Моделей нет. Сначала добавьте эндпоинт и модель в разделе{' '}
                    <a href="/models">Модели</a>.
                  </Banner>
                ) : (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {targetList.map((target) => (
                      <label
                        key={target.id}
                        className="checkbox"
                        style={{
                          padding: '10px 12px',
                          border: '1px solid var(--edge)',
                          borderRadius: 8,
                          background: selectedTargets.includes(target.id) ? 'var(--ink-600)' : 'transparent',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedTargets.includes(target.id)}
                          onChange={() => toggle(selectedTargets, target.id, setSelectedTargets)}
                        />
                        <span style={{ flex: 1 }}>
                          <span style={{ color: 'var(--text)' }}>{target.label || target.model_id}</span>
                          <span className="dim mono-sm" style={{ marginLeft: 8 }}>
                            {target.model_id}
                          </span>
                          <div className="dim" style={{ fontSize: 11 }}>
                            {target.endpoint_name}
                            {target.group_name ? ` · ${target.group_name}` : ''}
                          </div>
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </Field>

              <Field label="Модель-судья" help="Оценивает смысловые критерии. Лучше отдельная от проверяемых.">
                <select
                  className="select"
                  value={judgeId || ''}
                  onChange={(event) => setJudgeId(Number(event.target.value))}
                >
                  <option value="">— по умолчанию первая выбранная —</option>
                  {targetList.map((target) => (
                    <option key={target.id} value={target.id}>
                      {target.label || target.model_id}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          ) : null}

          {step === 1 ? (
            <Field label="Инструменты" help="Можно выбрать несколько: отчёт покажет их раздельно.">
              <div style={{ display: 'grid', gap: 8 }}>
                {TOOLS.map((tool) => {
                  const status = availability[tool.id]
                  const unavailable = status && !status.available
                  return (
                    <label
                      key={tool.id}
                      className="checkbox"
                      style={{
                        padding: '10px 12px',
                        border: '1px solid var(--edge)',
                        borderRadius: 8,
                        opacity: unavailable ? 0.72 : 1,
                        background: tools.includes(tool.id) ? 'var(--ink-600)' : 'transparent',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={tools.includes(tool.id)}
                        onChange={() => toggle(tools, tool.id, setTools)}
                      />
                      <span style={{ flex: 1 }}>
                        <span style={{ color: 'var(--text)' }}>{tool.label}</span>
                        {unavailable ? (
                          <span className="pill warn" style={{ marginLeft: 8 }}>
                            не установлен
                          </span>
                        ) : null}
                        <div className="dim" style={{ fontSize: 11 }}>
                          {tool.note}
                        </div>
                      </span>
                    </label>
                  )
                })}
              </div>
            </Field>
          ) : null}

          {step === 2 ? (
            <>
              <div className="row">
                <Field label="Режим движка" help="mock — офлайн-фикстура для демонстрации, без реальных запросов.">
                  <select className="select" value={engineMode} onChange={(event) => setEngineMode(event.target.value)}>
                    <option value="mock">mock — фикстура</option>
                    <option value="subprocess">subprocess — реальный run.py</option>
                  </select>
                </Field>
                <Field label="Лимит кейсов" help="0 — все записи выбранного набора.">
                  <input
                    className="input"
                    type="number"
                    min={0}
                    value={limit}
                    onChange={(event) => setLimit(event.target.value)}
                  />
                </Field>
              </div>

              <div className="row">
                <Field label="Seed" help="Одинаковая выборка для всех моделей прогона.">
                  <input
                    className="input"
                    type="number"
                    value={seed}
                    onChange={(event) => setSeed(event.target.value)}
                  />
                </Field>
                <Field label="Бюджет запросов" help="На модель, инструмент и маршрут.">
                  <input
                    className="input"
                    type="number"
                    min={1}
                    value={maxRequests}
                    onChange={(event) => setMaxRequests(event.target.value)}
                  />
                </Field>
              </div>

              <Field label="Версии датасетов" help="Пусто — будут использоваться файлы из комплекта.">
                <div style={{ maxHeight: 220, overflow: 'auto', display: 'grid', gap: 6 }}>
                  {versionList.slice(0, 40).map((version) => (
                    <label key={version.id} className="checkbox" style={{ fontSize: 12 }}>
                      <input
                        type="checkbox"
                        checked={versionIds.includes(version.id)}
                        onChange={() => toggle(versionIds, version.id, setVersionIds)}
                      />
                      <span>
                        {version.name} <span className="dim">v{version.version}</span>{' '}
                        <span className="dim">· {version.case_count} кейсов · {version.origin}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </Field>
            </>
          ) : null}

          {step === 3 ? (
            <>
              {engineMode === 'mock' ? (
                <Banner tone="warn">
                  Выбран режим <strong>mock</strong>. Результаты синтетические: они проверяют
                  работу конвейера, но ничего не говорят о безопасности модели.
                </Banner>
              ) : null}
              {missingTools.length ? (
                <Banner tone="bad">
                  Не установлены: {missingTools.join(', ')}. Эти шаги завершатся ошибкой, отчёт
                  будет помечен как неполный.
                </Banner>
              ) : null}

              <table className="data">
                <tbody>
                  <tr>
                    <td className="muted">Название</td>
                    <td>{label || '— (сгенерируется)'}</td>
                  </tr>
                  <tr>
                    <td className="muted">Модели</td>
                    <td>
                      {selectedTargets
                        .map((id) => targetList.find((t) => t.id === id))
                        .filter(Boolean)
                        .map((t) => t.label || t.model_id)
                        .join(', ')}
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">Инструменты</td>
                    <td>{tools.join(', ')}</td>
                  </tr>
                  <tr>
                    <td className="muted">Датасеты</td>
                    <td>
                      {versionIds.length
                        ? versionIds
                            .map((id) => {
                              const v = versionList.find((item) => item.id === id)
                              return v ? `${v.name} v${v.version}` : id
                            })
                            .join(', ')
                        : 'из комплекта'}
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">Режим</td>
                    <td className="mono-sm">{engineMode}</td>
                  </tr>
                  <tr>
                    <td className="muted">Лимит / seed</td>
                    <td className="mono-sm">
                      {limit} / {seed}
                    </td>
                  </tr>
                </tbody>
              </table>
            </>
          ) : null}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 22 }}>
            <button
              className="btn ghost"
              onClick={() => setStep((value) => Math.max(0, value - 1))}
              disabled={step === 0}
            >
              Назад
            </button>
            {step < STEPS.length - 1 ? (
              <button className="btn primary" onClick={() => setStep((v) => v + 1)} disabled={!canNext}>
                Далее
              </button>
            ) : (
              <button className="btn primary" onClick={submit} disabled={busy || selectedTargets.length === 0}>
                {busy ? 'Запуск…' : 'Запустить прогон'}
              </button>
            )}
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 12 }}>Памятка</h3>
          <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
            Один прогон — одна пара «endpoint + ключ». Разные эндпоинты запускаются отдельно,
            чтобы режимы проверки не смешивались.
          </p>
          <hr className="sep" />
          <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
            Доля провалов внутри инструмента — это не «процент безопасности». У garak единица
            счёта — решение детектора, у остальных — отдельный кейс.
          </p>
          <hr className="sep" />
          <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
            Начните с профиля по умолчанию, устраните несовместимости API, затем увеличивайте
            выборку с тем же seed и судьёй.
          </p>
        </div>
      </div>
    </div>
  )
}
