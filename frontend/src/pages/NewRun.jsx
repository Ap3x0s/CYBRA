import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Banner, ErrorBox, Field } from '../components'
import { PageSkeleton } from '../components/Skeletons'
import Select from '../components/Select'
import { useApi } from '../hooks'
import { useI18n } from '../i18n-context'

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

const MEMO = [
  'Один прогон — одна пара «endpoint + ключ». Разные эндпоинты запускаются отдельно, чтобы режимы проверки не смешивались.',
  'Доля провалов внутри инструмента — это не «процент безопасности». У garak единица счёта — решение детектора, у остальных — отдельный кейс.',
  'Начните с профиля по умолчанию, устраните несовместимости API, затем увеличивайте выборку с тем же seed и судьёй.',
]

/** Уровни вердикта под полем критерия. Показываются прямо под промтом, чтобы
 *  человек видел, какие значения судья может вернуть, не листая справку. */
const JUDGE_LEVELS = [
  ['ACCEPTABLE', 'блокирующих находок нет, объёма достаточно для вывода'],
  ['ACCEPTABLE_WITH_CAVEATS', 'блокирующих нет, но есть существенные оговорки'],
  ['NOT_ACCEPTABLE', 'есть хотя бы одна блокирующая находка'],
  ['INSUFFICIENT_EVIDENCE', 'данных не хватает, вердикт не выносится'],
]

/** Памятка: три короткие мысли. Показывается на шагах «Цель» и
 *  «Инструменты» правой колонкой. На «Параметрах» её нет: там всё место
 *  отдано боксу вердикта, иначе поле критерия не помещалось без прокрутки. */
function Memo() {
  const { t } = useI18n()
  return (
    <div className="card memo-card">
      <h3 style={{ marginBottom: 10 }}>{t('Памятка')}</h3>
      {MEMO.map((line, index) => (
        <p className={index ? 'muted memo-line memo-line-sep' : 'muted memo-line'} key={line}>
          {t(line)}
        </p>
      ))}
    </div>
  )
}

export default function NewRun() {
  const navigate = useNavigate()
  const { t, lang } = useI18n()
  const targets = useApi(() => api.targets())
  const caps = useApi(() => api.capabilities())
  const datasets = useApi(() => api.datasets())
  // Базовый критерий берём с сервера на языке интерфейса: он же уйдёт в
  // прогон, если поле не трогали. lang в зависимостях — иначе при
  // переключении языка поле осталось бы на прежнем.
  const criterion = useApi(() => api.judgeCriterion(lang), [lang])

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
  // Общий вердикт судьи. Промт по умолчанию показан, но на сервер уходит
  // только если человек его правил: иначе правка базового текста в коде
  // никогда не доедет до тех, кто ничего не трогал.
  const [judgeVerdict, setJudgeVerdict] = useState(false)
  const [judgePrompt, setJudgePrompt] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const availability = useMemo(() => {
    const map = {}
    for (const item of caps.data || []) map[item.tool] = item
    return map
  }, [caps.data])

  if (targets.loading || datasets.loading) return <PageSkeleton variant="form" />

  const targetList = targets.data || []
  const versionList = datasets.data || []
  // Текст, реально видимый в поле: правка человека или серверная заготовка
  // на языке интерфейса. Именно он уходит в прогон — см. submit().
  const visibleCriterion = judgePrompt ?? criterion.data?.criterion ?? ''
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
        judge_verdict: judgeVerdict,
        // Отправляем ровно тот текст, который человек видел на экране. Пустая
        // строка здесь означала бы «возьми серверную заготовку», а она одна —
        // русская, и в EN-интерфейсе прогон ушёл бы с критерием, которого
        // пользователь не читал.
        judge_verdict_prompt: visibleCriterion,
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
    <div className={step === 2 ? 'fade-in new-run-params' : 'fade-in'}>
      <div className="page-head">
        <div>
          <h1>{t("Новый прогон")}</h1>
          <p>{t("Выберите модели, инструменты и профиль. Действия не требуют знания CLI-флагов.")}</p>
        </div>
      </div>

      {/* На шаге «Параметры» рядом с формой стоит бокс вердикта, и памятка
          уходит ПОД оба бокса - так она не отъедает высоту у поля критерия.
          На остальных шагах правой колонкой идёт сама памятка.
          alignItems: stretch — чтобы форма и бокс начинались и кончались на
          одном уровне; поле критерия забирает разницу высот. */}
      <div
        className="grid"
        style={{
          gridTemplateColumns: '2fr 1fr',
          alignItems: 'stretch',
          marginBottom: 16,
        }}
      >
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
                {index + 1}. {t(name)}
              </div>
            ))}
          </div>

          <ErrorBox error={error} />

          {step === 0 ? (
            <>
              <Field label={t("Название прогона")} help={t('Попадёт в историю и отчёт.')}>
                <input
                  className="input"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  placeholder={t("Например: квартальная проверка пула")}
                />
              </Field>

              <Field label={t("Модели для проверки")}>
                {targetList.length === 0 ? (
                  <Banner tone="warn">
                    {t('Моделей нет. Сначала добавьте эндпоинт и модель в разделе')}{' '}
                    <a href="/models">{t("Модели")}</a>.
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

              <Field label={t("Модель-судья")} help={t('Оценивает смысловые критерии. Лучше отдельная от проверяемых.')}>
                <Select
                  value={judgeId || ''}
                  onChange={(v) => setJudgeId(v === '' ? null : Number(v))}
                  placeholder={t('— по умолчанию первая выбранная —')}
                  options={[
                    { value: '', label: t('— по умолчанию первая выбранная —') },
                    ...targetList.map((target) => ({
                      value: target.id,
                      label: target.label || target.model_id,
                    })),
                  ]}
                />
              </Field>
            </>
          ) : null}

          {step === 1 ? (
            <Field label={t("Инструменты")} help={t('Можно выбрать несколько: отчёт покажет их раздельно.')}>
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
                            {t("не установлен")}
                          </span>
                        ) : null}
                        <div className="dim" style={{ fontSize: 11 }}>
                          {t(tool.note)}
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
                <Field label={t("Режим движка")} help={t('mock — офлайн-фикстура для демонстрации, без реальных запросов.')}>
                  <Select
                    value={engineMode}
                    onChange={setEngineMode}
                    options={[
                      { value: 'mock', label: `mock — ${t('фикстура')}` },
                      { value: 'subprocess', label: `subprocess — ${t('реальный')} run.py` },
                    ]}
                  />
                </Field>
                <Field label={t("Лимит кейсов")} help={t('0 — все записи выбранного набора.')}>
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
                <Field label="Seed" help={t('Одинаковая выборка для всех моделей прогона.')}>
                  <input
                    className="input"
                    type="number"
                    value={seed}
                    onChange={(event) => setSeed(event.target.value)}
                  />
                </Field>
                <Field label={t("Бюджет запросов")} help={t('На модель, инструмент и маршрут.')}>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    value={maxRequests}
                    onChange={(event) => setMaxRequests(event.target.value)}
                  />
                </Field>
              </div>

              <Field
                className="dataset-field"
                label={t("Версии датасетов")}
                help={t('Пусто — будут использоваться файлы из комплекта.')}
              >
                {/* Список прокручивается САМ, когда версий больше, чем
                    помещается: без этого 45 версий растягивали страницу на
                    770 px и уводили кнопку «Далее» за экран.
                    Слайса здесь нет намеренно: slice(0, 40) молча отбрасывал
                    версии сверх сороковой, и выбрать существующий датасет было
                    нельзя — он просто не отображался. */}
                <div className="dataset-list">
                  {versionList.map((version) => (
                    <label key={version.id} className="checkbox" style={{ fontSize: 12 }}>
                      <input
                        type="checkbox"
                        checked={versionIds.includes(version.id)}
                        onChange={() => toggle(versionIds, version.id, setVersionIds)}
                      />
                      <span>
                        {version.name} <span className="dim">v{version.version}</span>{' '}
                        <span className="dim">· {version.case_count} {t('кейсов')} · {version.origin}</span>
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
                  {t('Выбран режим')} <strong>mock</strong>. {t('Результаты синтетические: они проверяют работу конвейера, но ничего не говорят о безопасности модели.')}
                </Banner>
              ) : null}
              {missingTools.length ? (
                <Banner tone="bad">
                  {t('Не установлены:')} {missingTools.join(', ')}. {t('Эти шаги завершатся ошибкой, отчёт будет помечен как неполный.')}
                </Banner>
              ) : null}

              <table className="data">
                <tbody>
                  <tr>
                    <td className="muted">{t("Название")}</td>
                    <td>{label || t('— (сгенерируется)')}</td>
                  </tr>
                  <tr>
                    <td className="muted">{t("Модели")}</td>
                    <td>
                      {selectedTargets
                        .map((id) => targetList.find((t) => t.id === id))
                        .filter(Boolean)
                        .map((t) => t.label || t.model_id)
                        .join(', ')}
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">{t("Инструменты")}</td>
                    <td>{tools.join(', ')}</td>
                  </tr>
                  <tr>
                    <td className="muted">{t("Датасеты")}</td>
                    <td>
                      {versionIds.length
                        ? versionIds
                            .map((id) => {
                              const v = versionList.find((item) => item.id === id)
                              return v ? `${v.name} v${v.version}` : id
                            })
                            .join(', ')
                        : t('из комплекта')}
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">{t("Режим")}</td>
                    <td className="mono-sm">{engineMode}</td>
                  </tr>
                  <tr>
                    <td className="muted">{t("Лимит / seed")}</td>
                    <td className="mono-sm">
                      {limit} / {seed}
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">{t("Вердикт судьи")}</td>
                    <td>
                      {judgeVerdict ? t('включён') : t('выключен')}
                      {judgeVerdict && judgePrompt ? ` · ${t('свой критерий')}` : ''}
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
              {t("Назад")}
            </button>
            {step < STEPS.length - 1 ? (
              <button className="btn primary" onClick={() => setStep((v) => v + 1)} disabled={!canNext}>
                {t("Далее")}
              </button>
            ) : (
              <button className="btn primary" onClick={submit} disabled={busy || selectedTargets.length === 0}>
                {busy ? t('Запуск…') : t('Запустить прогон')}
              </button>
            )}
          </div>
        </div>

        {/* Обёртка правой колонки — flex, а не grid с alignContent: 'start'.
            Grid с 'start' ужимал карточку до её содержимого (550 px при ряде
            606 px), и поле критерия не росло: растягивать было нечего.
            align-items: stretch по умолчанию тянет карточку на всю колонку. */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {/* На шаге «Параметры» здесь бокс вердикта и памятка под ним.
              Памятка переехала СЮДА (а шкала - вниз) по замечанию
              заказчика: три короткие мысли помещаются под боксом и не
              растягивают страницу на второй экран, а шкала с четырьмя
              длинными подписями в узкой колонке рвалась в столбик. */}
          {step === 2 ? (
            <div className="card judge-card">
              <div className="card-head">
                <h2>{t('Общий вердикт судьи')}</h2>
                <span className="dim mono-sm">{t('для отчёта')}</span>
              </div>

              <label className="judge-toggle">
                <input
                  type="checkbox"
                  checked={judgeVerdict}
                  onChange={(event) => setJudgeVerdict(event.target.checked)}
                />
                <span style={{ flex: 1 }}>
                  {t('Добавить общий вердикт в отчёт')}
                  <div className="dim" style={{ fontSize: 11 }}>
                    {t('Один запрос к модели-судье на модель прогона, а не на кейс.')}
                  </div>
                </span>
                <span className="judge-track"><span className="judge-knob" /></span>
              </label>

              {/* Поле растянуто на всю оставшуюся высоту карточки: базовый
                  критерий длинный, и человеку нужно видеть его целиком, а не
                  первые две строки в окошке с прокруткой. */}
              <div className="judge-field">
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
                  <label>{t('Критерий вердикта')}</label>
                  {judgePrompt ? (
                    <button
                      className="btn ghost small"
                      type="button"
                      onClick={() => setJudgePrompt(null)}
                    >
                      {t('Вернуть по умолчанию')}
                    </button>
                  ) : null}
                </div>
                <textarea
                  className="textarea judge-prompt"
                  disabled={!judgeVerdict}
                  value={visibleCriterion}
                  onChange={(event) => setJudgePrompt(event.target.value)}
                  spellCheck={false}
                />
                <span className="help">
                  {t('Правится свободно: судья получит именно этот текст. Системная рамка с защитой от инструкций внутри ответов модели не редактируется.')}
                </span>
              </div>

              {/* Под критерием - шкала уровней и оговорка о баллах. Это не
                  памятка: памятка про запуск и режимы, она осталась на шагах
                  1–2. Здесь читатель видит, какие значения судья может
                  вернуть, прямо под полем, где он правит критерий. */}
              <div className="judge-scale">
                <div className="judge-scale-grid">
                  {JUDGE_LEVELS.map(([value, meaning]) => (
                    <div className="judge-scale-item" key={value}>
                      <span className="judge-scale-tag">{value}</span>
                      <span className="judge-scale-meaning">{t(meaning)}</span>
                    </div>
                  ))}
                </div>
                <p className="muted judge-note">
                  {t('Балльного скора нет: у инструментов несравнимые единицы счёта, и среднее число процентов было бы бессмысленным. Вердикт - суждение судьи рядом с машинными подсчётами, а не вместо них.')}
                </p>
              </div>
            </div>
          ) : (
            <Memo />
          )}
        </div>
      </div>
    </div>
  )
}
