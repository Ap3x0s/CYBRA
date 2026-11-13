/** Скелетоны загрузки.
 *
 *  Раньше на месте страницы была одна строка «Загрузка…» — при медленном
 *  ответе API экран выглядел пустым. Здесь скелетон повторяет сетку боксов
 *  страницы, поэтому контент появляется на месте уже занятых блоков и ничего
 *  не прыгает. Числа и подписи не подставляются текстом: смысл скелетона —
 *  показать форму, а не выдумать данные.
 *
 *  Переливка идёт в наших тонах (тёплый серый), а не белым: белая полоса на
 *  #1f1f22 выглядела бы как артефакт. При prefers-reduced-motion анимация
 *  отключается, но блоки остаются.
 */

function Box({ w = '100%', h = 12, r = 6, style }) {
  return <span className="skel" style={{ width: w, height: h, borderRadius: r, ...style }} />
}

/** Заголовок страницы: большая строка + пояснение под ней. */
function Head({ lines = 2 }) {
  return (
    <div className="skel-head">
      <Box w={230} h={22} r={7} />
      {Array.from({ length: lines }).map((_, index) => (
        <Box key={index} w={index ? '48%' : '64%'} h={11} />
      ))}
    </div>
  )
}

function KpiRow({ count = 4 }) {
  return (
    <div className="skel-grid skel-grid-4">
      {Array.from({ length: count }).map((_, index) => (
        <div className="skel-card skel-card-kpi" key={index}>
          <Box w={110} h={10} />
          <Box w={54} h={26} r={6} style={{ marginTop: 12 }} />
          <Box w={72} h={9} style={{ marginTop: 10 }} />
        </div>
      ))}
    </div>
  )
}

function Card({ height, rows = 3, title = true }) {
  return (
    <div className="skel-card" style={{ minHeight: height }}>
      {title ? <Box w={180} h={13} /> : null}
      <div style={{ marginTop: title ? 16 : 0, display: 'grid', gap: 10 }}>
        {Array.from({ length: rows }).map((_, index) => (
          <Box key={index} w={index === rows - 1 ? '62%' : '100%'} h={10} />
        ))}
      </div>
    </div>
  )
}

function Table({ rows = 5 }) {
  return (
    <div className="skel-card" style={{ padding: 0, overflow: 'hidden' }}>
      <div className="skel-tr skel-tr-head">
        {[100, 90, 120, 60, 70, 60].map((w, index) => (
          <Box key={index} w={w} h={9} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div className="skel-tr" key={r}>
          <Box w={140} h={10} />
          <Box w={80} h={10} />
          <Box w={110} h={10} />
          <Box w={40} h={10} />
          <Box w={58} h={10} />
          <Box w={50} h={10} />
        </div>
      ))}
    </div>
  )
}

/** Форма: подпись + поле, повторённые нужное число раз, затем кнопка. */
function Form({ fields = 2, button = true, labels = true }) {
  return (
    <div style={{ display: 'grid', gap: labels ? 14 : 10 }}>
      {Array.from({ length: fields }).map((_, index) => (
        <div key={index} style={{ display: 'grid', gap: 7 }}>
          <Box w={index === 0 ? 96 : 88} h={9} />
          <Box w="100%" h={34} r={7} />
        </div>
      ))}
      {button ? <Box w={132} h={32} r={7} style={{ marginTop: 4 }} /> : null}
    </div>
  )
}

/** Таблица: шапка с несколькими ячейками и строки под неё. */
function Rows({ rows = 8, cols = [120, 60, 70, 80] }) {
  return (
    <div style={{ display: 'grid', gap: 0 }}>
      <div
        style={{
          display: 'flex', gap: 18, paddingBottom: 10,
          borderBottom: '1px solid var(--edge)',
        }}
      >
        {cols.map((w, index) => (
          <Box key={index} w={w} h={8} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          style={{
            display: 'flex', gap: 18, alignItems: 'center',
            padding: '13px 0', borderBottom: '1px solid var(--edge-soft)',
          }}
        >
          {cols.map((w, index) => (
            <Box key={index} w={index === 0 ? w : w - 10} h={9} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function PageSkeleton({ variant = 'default' }) {
  if (variant === 'dashboard') {
    return (
      <div className="fade-in">
        <Head />
        <KpiRow />
        <div className="skel-grid skel-grid-2-1">
          <Card height={300} rows={4} />
          <Card height={300} rows={5} />
        </div>
        <Table rows={4} />
      </div>
    )
  }

  if (variant === 'runs') {
    return (
      <div className="fade-in">
        <Head lines={1} />
        <Table rows={7} />
      </div>
    )
  }

  if (variant === 'detail') {
    return (
      <div className="fade-in">
        <Head lines={1} />
        <KpiRow count={3} />
        <Table rows={6} />
      </div>
    )
  }

  if (variant === 'datasets') {
    return (
      <div className="fade-in">
        <Head />
        <div className="skel-grid skel-grid-1-2">
          <Card height={420} rows={7} />
          <Card height={420} rows={5} />
        </div>
      </div>
    )
  }

  if (variant === 'metrics') {
    return (
      <div className="fade-in">
        <Head lines={1} />
        <Card height={240} rows={2} />
        <KpiRow count={3} />
        <Card height={200} rows={3} />
      </div>
    )
  }

  if (variant === 'settings') {
    // Повторяет реальную раскладку страницы настроек: сверху равные колонки
    // (форма пароля слева, таблица окружения справа), ниже — форма нового
    // пользователя и таблица пользователей. Равные колонки, а не 1fr/320px
    // как в skel-grid-1-2: в настройках сетка именно grid-2.
    return (
      <div className="fade-in">
        <Head lines={1} />

        <div className="skel-grid skel-grid-2">
          <div className="skel-card">
            <Box w={150} h={13} />
            <div style={{ marginTop: 18 }}>
              <Form fields={2} />
            </div>
          </div>
          <div className="skel-card">
            <Box w={90} h={13} />
            <div style={{ marginTop: 18 }}>
              <Rows rows={8} />
              <Box w="100%" h={46} r={7} style={{ marginTop: 16 }} />
            </div>
          </div>
        </div>

        <div className="skel-grid skel-grid-2">
          <div className="skel-card">
            <Box w={160} h={13} />
            <div style={{ marginTop: 18 }}>
              <Form fields={3} labels={false} />
            </div>
          </div>
          <div className="skel-card">
            <Box w={130} h={13} />
            <div style={{ marginTop: 18 }}>
              <Rows rows={3} cols={[110, 90, 70, 80]} />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (variant === 'form') {
    return (
      <div className="fade-in">
        <Head lines={1} />
        <div className="skel-grid skel-grid-1-2">
          <Card height={360} rows={6} />
          <Card height={360} rows={6} />
        </div>
      </div>
    )
  }

  // Фолбэк тоже через сетку: две карточки подряд без контейнера слипались,
  // потому что отступ живёт на .skel-grid, а не на .skel-card.
  return (
    <div className="fade-in">
      <Head lines={1} />
      <div className="skel-grid">
        <Card height={220} rows={4} />
        <Card height={220} rows={4} />
      </div>
    </div>
  )
}

/** Скелетон для небольшого блока внутри уже загруженной страницы
 *  (список кейсов, график, таблица шагов). */
export function BlockSkeleton({ rows = 3, height }) {
  return (
    <div className="skel-block" style={height ? { minHeight: height } : undefined}>
      {Array.from({ length: rows }).map((_, index) => (
        <Box key={index} w={index === rows - 1 ? '55%' : '100%'} h={10} />
      ))}
    </div>
  )
}
