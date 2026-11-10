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

  return (
    <div className="fade-in">
      <Head lines={1} />
      <Card height={220} rows={4} />
      <Card height={220} rows={4} />
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
